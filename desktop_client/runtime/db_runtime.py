from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator

import aiomysql

import db_config
import db_manager
from desktop_client.models import DatabaseConfig

DB_KEYS = ("host", "port", "user", "password", "database", "charset")


def snapshot_db_config() -> Dict[str, Any]:
    return {key: db_config.DB_CONFIG.get(key) for key in DB_KEYS}


def apply_db_config(config: DatabaseConfig) -> Dict[str, Any]:
    previous = snapshot_db_config()
    updated = config.to_dict(include_password=True)
    for key in DB_KEYS:
        if key in updated:
            db_config.DB_CONFIG[key] = updated[key]
            db_manager.DB_CONFIG[key] = updated[key]
    return previous


def restore_db_config(snapshot: Dict[str, Any]) -> None:
    for key in DB_KEYS:
        if key in snapshot:
            db_config.DB_CONFIG[key] = snapshot[key]
            db_manager.DB_CONFIG[key] = snapshot[key]


@contextmanager
def runtime_db_config(config: DatabaseConfig) -> Iterator[None]:
    previous = apply_db_config(config)
    try:
        yield
    finally:
        restore_db_config(previous)


async def test_db_connection(config: DatabaseConfig) -> tuple[bool, str]:
    if not config.host or not config.user or not config.database:
        return False, "数据库配置不完整。"

    pool = None
    try:
        pool = await aiomysql.create_pool(
            host=config.host,
            port=config.port,
            user=config.user,
            password=config.password,
            db=config.database,
            charset=config.charset,
            autocommit=True,
            minsize=1,
            maxsize=1,
        )
        return True, f"连接成功：{config.host}:{config.port}/{config.database}"
    except Exception as exc:
        return False, f"连接失败：{exc}"
    finally:
        if pool is not None:
            pool.close()
            await pool.wait_closed()
