import os
from typing import Optional

# Подхват .env (опционально)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


def _required(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError("ENV {} is not set".format(name))
    return v


BOT_TOKEN = _required("BOT_TOKEN")
API_URL = _required("API_URL")

_CHAT_ID_RAW = (os.getenv("CHAT_ID") or "").strip()

GROUP_CHAT_ID = None  # type: Optional[int]
if _CHAT_ID_RAW:
    try:
        GROUP_CHAT_ID = int(_CHAT_ID_RAW)
    except ValueError:
        raise RuntimeError("ENV CHAT_ID must be integer (Telegram chat id)")
