import asyncio
import uvicorn

# FastAPI app
from app import app

# Aiogram bot
from bot.bot import dp, bot


async def run_api():
    """
    Запуск FastAPI через uvicorn программно.
    """
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",  # ВАЖНО
        port=5000,
        reload=False,
        log_level="info"
    )

    server = uvicorn.Server(config)
    await server.serve()


async def run_bot():
    """
    Запуск aiogram polling.
    """
    await dp.start_polling(bot)


async def main():
    # Запускаем оба сервиса параллельно
    await asyncio.gather(
        run_api(),
        run_bot(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
