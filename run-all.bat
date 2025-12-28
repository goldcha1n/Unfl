@echo off
chcp 65001 >nul
setlocal

echo ===============================
echo Unfl_Message launcher
echo ===============================

REM ---- Проверка Python ----
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python не найден в PATH
    pause
    exit /b 1
)

REM ---- Проверка venv ----
if not exist ".venv\" (
    echo [INFO] Виртуальная среда не найдена. Создаю .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Не удалось создать виртуальную среду
        pause
        exit /b 1
    )
)

REM ---- Активация venv ----
call .venv\Scripts\activate
if errorlevel 1 (
    echo [ERROR] Не удалось активировать виртуальную среду
    pause
    exit /b 1
)

REM ---- Проверка pip ----
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Устанавливаю pip...
    python -m ensurepip
)

REM ---- Установка зависимостей ----
if exist "requirements.txt" (
    echo [INFO] Устанавливаю зависимости...
    pip install -r requirements.txt
) else (
    echo [WARN] requirements.txt не найден
)

REM ---- Проверка .env ----
if not exist ".env" (
    echo.
    echo [ERROR] Файл .env не найден в корне проекта
    echo Создай файл .env со следующим содержимым:
    echo ----------------------------------
    echo BOT_TOKEN=YOUR_BOT_TOKEN
    echo API_URL=http://127.0.0.1:8000/api/bot/message
    echo CHAT_ID=-100XXXXXXXXXX
    echo ----------------------------------
    pause
    exit /b 1
)

REM ---- Запуск FastAPI ----
echo [INFO] Запуск FastAPI (app.py)
start "FastAPI server" cmd /k "call .venv\Scripts\activate && python app.py"

REM ---- Пауза, чтобы сервер успел стартовать ----
timeout /t 2 >nul

REM ---- Запуск Telegram-бота ----
echo [INFO] Запуск Telegram бота
start "Telegram bot" cmd /k "call .venv\Scripts\activate && python bot\bot.py"

echo.
echo ===============================
echo Проект запущен
echo ===============================
echo FastAPI: http://127.0.0.1:8000
echo Для остановки закрой окна серверов
echo.

exit /b 0
