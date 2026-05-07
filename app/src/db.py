import asyncio
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.config import Settings
from src.utils.logging import get_logger

log = get_logger("db")

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def connect(settings: Settings) -> None:
    global _client, _db

    _client = AsyncIOMotorClient(
        settings.mongo_uri,
        serverSelectionTimeoutMS=settings.mongo_timeout_ms,
        connectTimeoutMS=settings.mongo_timeout_ms,
        socketTimeoutMS=settings.mongo_timeout_ms,
        appname=f"{settings.app_name}/{settings.region_id}",
        retryWrites=True,
    )

    db_name = settings.mongo_uri.rsplit("/", 1)[-1].split("?", 1)[0] or "dr_demo"
    _db = _client[db_name]

    try:
        await asyncio.wait_for(_client.admin.command("ping"), timeout=2.0)
        log.info("mongo_connected", db=db_name)
    except Exception as exc:
        log.warning("mongo_initial_ping_failed", error=str(exc))


async def disconnect() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None


def db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("DB not initialised. Call connect() in lifespan.")
    return _db


async def ping(timeout: float = 1.5) -> bool:
    if _client is None:
        return False
    try:
        await asyncio.wait_for(_client.admin.command("ping"), timeout=timeout)
        return True
    except Exception:
        return False
