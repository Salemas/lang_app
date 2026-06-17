import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./lang_app.db")

engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.begin() as conn:

        def _migrate(conn):
            from sqlalchemy import inspect

            inspector = inspect(conn)
            cols = [c["name"] for c in inspector.get_columns("pricelist_items")]
            if "upload_id" not in cols:
                conn.execute(
                    __import__("sqlalchemy").text(
                        "ALTER TABLE pricelist_items ADD COLUMN upload_id UUID"
                    )
                )

        await conn.run_sync(_migrate)
