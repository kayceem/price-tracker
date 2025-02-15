
import datetime
from pathlib import Path

nepal_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=45))

def get_dir_path() -> Path:
    return Path(__file__).resolve().parent.parent

def valid_day_time() ->  bool:
    now = datetime.datetime.now()
    if now.weekday() in [6,0,1,2,3] and 11 <= now.hour < 15:
        return True
    return False

def is_price_in_range(target: float, current: float, delta_percent: float) -> bool:
        delta = current * (delta_percent / 100)
        return current - delta <= target <= current + delta
        
def check_time_delta(last_alert_time: datetime, delta: int) -> bool:
    if last_alert_time is None:
        return True
    return (datetime.datetime.now(nepal_tz) - last_alert_time.replace(tzinfo=nepal_tz)).seconds >= delta
    