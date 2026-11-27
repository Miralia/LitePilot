from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base
from app.db.models.transferhistory import TransferHistory


async def _enable_case_sensitive_like(db):
    """让 SQLite 在测试中暴露与 PostgreSQL 一致的 LIKE 大小写敏感问题。"""
    await db.execute(text("PRAGMA case_sensitive_like=ON"))


@pytest.mark.asyncio
async def test_transfer_history_search_is_case_insensitive(tmp_path: Path):
    """整理历史标题和路径搜索应忽略大小写。"""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'transfer_history.db'}")
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory() as db:
            await _enable_case_sensitive_like(db)
            db.add_all(
                [
                    TransferHistory(
                        src="/downloads/Avatar.Source.mkv",
                        dest="/media/Avatar/Avatar.mkv",
                        title="Avatar",
                        status=True,
                        date="2026-06-01 00:00:00",
                    ),
                    TransferHistory(
                        src="/downloads/Interstellar.mkv",
                        dest="/media/Interstellar/Interstellar.mkv",
                        title="Interstellar",
                        status=True,
                        date="2026-06-02 00:00:00",
                    ),
                ]
            )
            await db.commit()

            title_result = await TransferHistory.async_list_by_title(db, "avatar")
            src_result = await TransferHistory.async_list_by_title(db, "avatar.source")
            dest_result = await TransferHistory.async_list_by_title(db, "%avatar.mkv", wildcard=True)
            total = await TransferHistory.async_count_by_title(db, "avatar")

        assert [item.title for item in title_result] == ["Avatar"]
        assert [item.title for item in src_result] == ["Avatar"]
        assert [item.title for item in dest_result] == ["Avatar"]
        assert total == 1
    finally:
        await engine.dispose()
