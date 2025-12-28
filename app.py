import os
import aiohttp

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from pydantic import BaseModel

import database

# Подхват .env (опционально)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

app = FastAPI()

# Cookie-сессии (в проде: поменяй ключ на длинный случайный)
app.add_middleware(SessionMiddleware, secret_key="SECRET_KEY_CHANGE_ME")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# =========================
# Telegram settings (через ENV, БЕЗ импорта из bot.config)
# =========================
BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
CHAT_ID = (os.getenv("CHAT_ID") or "").strip()

TG_GROUP_CHAT_ID = None
if CHAT_ID:
    try:
        TG_GROUP_CHAT_ID = int(CHAT_ID)
    except ValueError:
        TG_GROUP_CHAT_ID = None


async def send_to_telegram_group(sender: str, receiver: str, text: str) -> bool:
    """
    Дублируем сообщение в Telegram-группу в формате:
    sender receiver text
    """
    if not BOT_TOKEN or TG_GROUP_CHAT_ID is None:
        return False

    out = "{} {} {}".format(sender, receiver, text)

    url = "https://api.telegram.org/bot{}/sendMessage".format(BOT_TOKEN)
    payload = {"chat_id": TG_GROUP_CHAT_ID, "text": out}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=8) as resp:
                data = await resp.json()
                return bool(data.get("ok"))
    except Exception as e:
        print("[TG SEND ERROR]", repr(e))
        return False


@app.on_event("startup")
def startup_event():
    database.init_db()


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/contacts")
    return RedirectResponse(url="/login")


@app.get("/register", response_class=HTMLResponse)
async def register_get(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/contacts")
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register", response_class=HTMLResponse)
async def register_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
):
    if request.session.get("user_id"):
        return RedirectResponse(url="/contacts")

    error = None
    if password != password2:
        error = "Введённые пароли не совпадают"
    elif database.get_user_by_username(username) is not None:
        error = "Имя пользователя уже занято"

    if error:
        return templates.TemplateResponse(
            "register.html", {"request": request, "error": error, "username": username}
        )

    user_id = database.create_user(username, password)
    if user_id is None:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Не удалось создать аккаунт", "username": username},
        )

    request.session["user_id"] = user_id
    request.session["username"] = username
    return RedirectResponse(url="/contacts", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/contacts")
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    if request.session.get("user_id"):
        return RedirectResponse(url="/contacts")

    user = database.verify_user(username, password)
    if user is None:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Неверное имя пользователя или пароль", "username": username},
        )

    request.session["user_id"] = user["id"]
    request.session["username"] = user["username"]
    return RedirectResponse(url="/contacts", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")


@app.get("/contacts", response_class=HTMLResponse)
async def contacts_page(request: Request):
    user_id = request.session.get("user_id")
    username = request.session.get("username")
    if not user_id:
        return RedirectResponse(url="/login")

    contacts = database.get_contacts(user_id)

    flash_msg = None
    flash_category = None
    if request.session.get("flash"):
        flash = request.session.pop("flash")
        if isinstance(flash, dict):
            flash_msg = flash.get("message")
            flash_category = flash.get("category")
        else:
            flash_msg = str(flash)
            flash_category = "info"

    context = {
        "request": request,
        "contacts": contacts,
        "current_user": {"id": user_id, "username": username},
        "chat_with": None,
    }
    if flash_msg:
        context["flash_msg"] = flash_msg
        context["flash_category"] = flash_category

    return templates.TemplateResponse("chat.html", context)


@app.post("/contacts", response_class=HTMLResponse)
async def add_contact_post(request: Request, username: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login")

    username_to_add = username.strip()
    msg = None
    category = "error"

    target_user = database.get_user_by_username(username_to_add)
    if target_user is None:
        msg = "Пользователь не найден"
    elif target_user["id"] == user_id:
        msg = "Нельзя добавить себя в контакты"
    else:
        contacts = database.get_contacts(user_id)
        if any(c["id"] == target_user["id"] for c in contacts):
            msg = "Контакт уже добавлен"
        else:
            success = database.add_contact(user_id, username_to_add)
            if success:
                msg = "Контакт успешно добавлен"
                category = "success"
            else:
                msg = "Не удалось добавить контакт"

    request.session["flash"] = {"message": msg, "category": category}
    return RedirectResponse(url="/contacts", status_code=303)


@app.get("/chat/{username}", response_class=HTMLResponse)
async def chat_with_user(request: Request, username: str):
    user_id = request.session.get("user_id")
    current_username = request.session.get("username")
    if not user_id:
        return RedirectResponse(url="/login")

    target_user = database.get_user_by_username(username)
    if target_user is None:
        request.session["flash"] = {"message": "Пользователь не найден", "category": "error"}
        return RedirectResponse(url="/contacts", status_code=303)

    contacts = database.get_contacts(user_id)
    if not any(c["id"] == target_user["id"] for c in contacts):
        request.session["flash"] = {"message": "Добавьте пользователя в контакты, чтобы начать чат", "category": "error"}
        return RedirectResponse(url="/contacts", status_code=303)

    messages = database.get_messages(user_id, target_user["id"])

    context = {
        "request": request,
        "contacts": contacts,
        "current_user": {"id": user_id, "username": current_username},
        "chat_with": username,
        "messages": messages,
    }
    return templates.TemplateResponse("chat.html", context)


@app.post("/chat/{username}", response_class=HTMLResponse)
async def send_message(request: Request, username: str, content: str = Form(...)):
    """
    Web -> SQLite + дублирование в Telegram-группу:
    sender receiver text
    """
    user_id = request.session.get("user_id")
    sender_username = request.session.get("username")
    if not user_id:
        return RedirectResponse(url="/login")

    target_user = database.get_user_by_username(username)
    if target_user is None:
        request.session["flash"] = {"message": "Пользователь не найден", "category": "error"}
        return RedirectResponse(url="/contacts", status_code=303)

    contacts = database.get_contacts(user_id)
    if not any(c["id"] == target_user["id"] for c in contacts):
        request.session["flash"] = {"message": "Нет доступа к чату с данным пользователем", "category": "error"}
        return RedirectResponse(url="/contacts", status_code=303)

    text = (content or "").strip()
    if not text:
        return RedirectResponse(url="/chat/{}".format(username), status_code=303)

    ok = database.add_message(sender_id=user_id, receiver_username=username, content=text)
    if not ok:
        request.session["flash"] = {"message": "Не удалось отправить сообщение", "category": "error"}
        return RedirectResponse(url="/contacts", status_code=303)

    tg_ok = await send_to_telegram_group(sender_username, username, text)
    if not tg_ok:
        print("[TG] Not sent (token/chat_id not set or send failed)")

    return RedirectResponse(url="/chat/{}".format(username), status_code=303)


# =========================
# API для Telegram-бота (сохранение из TG в Web/DB)
# =========================
class BotMessage(BaseModel):
    sender: str
    receiver: str
    text: str
    source: str = "telegram"


@app.post("/api/bot/message")
async def receive_message_from_bot(data: BotMessage):
    sender = database.get_user_by_username(data.sender)
    receiver = database.get_user_by_username(data.receiver)

    if not sender or not receiver:
        return {"status": "error", "reason": "user_not_found"}

    text = (data.text or "").strip()
    if not text:
        return {"status": "error", "reason": "empty_message"}

    ok = database.add_message(sender_id=sender["id"], receiver_username=receiver["username"], content=text)
    if not ok:
        return {"status": "error", "reason": "db_write_failed"}

    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
