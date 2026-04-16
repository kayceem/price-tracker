from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    data_dir: Path
    csv_dir: Path
    database_url: str
    interest_rate: float
    default_username: str
    api_host: str
    api_port: int
    api_reload: bool
    web_host: str
    web_port: int
    web_reload: bool
    templates_dir: Path
    static_dir: Path
    log_level: str
    nepse_cache_ttl: int
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    webhook_url: str | None

    def get_user_csv_dir(self, username: str | None = None) -> Path:
        return self.csv_dir / (username or self.default_username)

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        self.get_user_csv_dir().mkdir(parents=True, exist_ok=True)


def _build_settings() -> Settings:
    base_dir = Path(__file__).resolve().parent.parent.parent
    data_dir = base_dir / "data"
    csv_dir = data_dir / "csv"

    return Settings(
        base_dir=base_dir,
        data_dir=data_dir,
        csv_dir=csv_dir,
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{base_dir}/db.sqlite3"),
        interest_rate=float(os.getenv("INTEREST_RATE", "24.0")),
        default_username=os.getenv("PORTFOLIO_USERNAME", "3522757"),
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=int(os.getenv("API_PORT", "8000")),
        api_reload=os.getenv("API_RELOAD", "True").lower() == "true",
        web_host=os.getenv("WEB_HOST", "0.0.0.0"),
        web_port=int(os.getenv("WEB_PORT", "8001")),
        web_reload=os.getenv("WEB_RELOAD", "True").lower() == "true",
        templates_dir=base_dir / "src" / "web" / "templates",
        static_dir=base_dir / "src" / "web" / "static",
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        nepse_cache_ttl=int(os.getenv("NEPSE_CACHE_TTL", "900")),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        webhook_url=os.getenv("WEBHOOK_URL"),
    )


settings = _build_settings()

