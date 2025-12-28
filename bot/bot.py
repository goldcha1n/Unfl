import asyncio
import aiohttp

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from typing import Optional, Tuple

from bot.config import BOT_TOKEN, API_URL, GROUP_CHAT_ID

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

HELP_TEXT = (
    "GROUP Broker + Save.\n\n"
    "Пиши в группе:\n"
    "@username текст\n\n"
    "Бот:\n"
    "1) сохраняет в БД (через FastAPI)\n"
    "2) публикует в группе: sender receiver текст\n\n"
    "Пример:\n"
    "@name2 привет\n"
    "=> name1 name2 привет\n"
)


def parse_receiver_and_body(text: str) -> Tuple[Optional[str], Optional[str]]:
    t = (text or "").strip()
    if not t.startswith("@"):
        return None, None
    parts = t.split(" ", 1)
    if len(parts) < 2:
        return None, None
    receiver = parts[0].lstrip("@").strip()
    body = parts[1].strip()
    if not receiver or not body:
        return None, None
    return receiver, body


def get_sender_username(message: types.Message) -> Optional[str]:
    if message.from_user and message.from_user.username:
        return message.from_user.username
    return None


@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(HELP_TEXT)


@dp.message()
async def group_router(message: types.Message):
    # 1) только группы/супергруппы
    if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    # 2) если задан CHAT_ID — работаем строго в этой группе
    if GROUP_CHAT_ID is not None and message.chat.id != GROUP_CHAT_ID:
        return

    # 3) игнорируем сообщения от ботов
    if message.from_user and message.from_user.is_bot:
        return

    # 4) команды
    if message.text and message.text.strip() in ("/help", "/start"):
        await message.reply(HELP_TEXT)
        return

    # 5) парсим "@receiver текст"
    receiver, body = parse_receiver_and_body(message.text)
    if not receiver:
        return

    sender = get_sender_username(message)
    if not sender:
        await message.reply("❌ У тебя нет Telegram username. Добавь username в настройках Telegram.")
        return

    payload = {
        "sender": sender,
        "receiver": receiver,
        "text": body,
        "source": "telegram_group",
    }

    # 6) Сохраняем в БД через FastAPI
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, json=payload, timeout=8) as resp:
                data = await resp.json()
    except Exception as e:
        print("[API ERROR]", repr(e))
        await message.reply("❌ Ошибка связи с API. Проверь FastAPI, API_URL, сеть и firewall.")
        return

    if data.get("status") != "ok":
        await message.reply("❌ API отказал: {}".format(data))
        return

    # 7) Публикуем в группу: sender receiver текст
    out = "{} {} {}".format(sender, receiver, body)
    try:
        await bot.send_message(chat_id=message.chat.id, text=out)
        print("[SEND OK]")
    except Exception as e:
        print("[SEND ERROR]", repr(e))
        await message.reply("❌ Не смог отправить сообщение в группу. Проверь права бота.")


async def main():
    print("Group broker + save started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
