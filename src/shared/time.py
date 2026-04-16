from __future__ import annotations

import datetime as dt


nepal_tz = dt.timezone(dt.timedelta(hours=5, minutes=45))


def nepal_now() -> dt.datetime:
    return dt.datetime.now(nepal_tz)


def valid_market_time() -> bool:
    now = nepal_now()
    return now.weekday() in [6, 0, 1, 2, 3] and 9 <= now.hour < 15


def check_time_delta(last_alert_time: dt.datetime | None, delta_seconds: int) -> bool:
    if last_alert_time is None:
        return True
    if last_alert_time.tzinfo is None:
        last_alert_time = last_alert_time.replace(tzinfo=nepal_tz)
    return (nepal_now() - last_alert_time).total_seconds() >= delta_seconds

