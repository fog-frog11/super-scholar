from __future__ import annotations

from alembic import command
from alembic.config import Config

from .config import BASE_DIR, get_settings


def upgrade_database() -> None:
    settings = get_settings()
    config = Config(str(BASE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BASE_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.upgrade(config, "head")
