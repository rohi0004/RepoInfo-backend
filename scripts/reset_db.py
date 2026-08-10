"""Drops all tables and recreates the schema. Destructive: dev-only."""

import asyncio

from app.database.session import engine
from app.models import Base


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("Database reset complete.")


if __name__ == "__main__":
    asyncio.run(main())
