"""Alembic environment. Uses the app's async engine so one DATABASE_URL drives everything."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

from app import models  # noqa: F401  (register tables on Base.metadata)
from app.config import get_settings
from app.db import Base, make_engine, run_async

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    return config.attributes.get("database_url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _do_run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    settings = get_settings().model_copy(update={"database_url": _url()})
    engine = make_engine(settings)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_async(run_migrations_online())
