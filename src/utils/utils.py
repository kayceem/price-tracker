from pathlib import Path

from src.modules.alerts.service import is_price_in_range
from src.shared.security import decrypt_password, encrypt_password
from src.shared.time import check_time_delta, nepal_tz, valid_market_time


def get_dir_path() -> Path:
    return Path(__file__).resolve().parent.parent


def valid_day_time() -> bool:
    return valid_market_time()
