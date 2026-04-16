"""Backward-compatible settings exports."""

from src.shared.config import settings


BASE_DIR = settings.base_dir
DATA_DIR = settings.data_dir
CSV_DIR = settings.csv_dir
DATABASE_URL = settings.database_url
INTEREST_RATE = settings.interest_rate
USERNAME = settings.default_username
API_HOST = settings.api_host
API_PORT = settings.api_port
API_RELOAD = settings.api_reload
WEB_HOST = settings.web_host
WEB_PORT = settings.web_port
WEB_RELOAD = settings.web_reload
TEMPLATES_DIR = settings.templates_dir
STATIC_DIR = settings.static_dir
TELEGRAM_BOT_TOKEN = settings.telegram_bot_token
TELEGRAM_CHAT_ID = settings.telegram_chat_id
LOG_LEVEL = settings.log_level
NEPSE_CACHE_TTL = settings.nepse_cache_ttl
config = settings
