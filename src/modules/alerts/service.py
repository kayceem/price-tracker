from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.repositories import ScriptRepository, TrackerRepository, UserRepository
from src.shared.exceptions import NotFoundError, ValidationError
from src.shared.time import check_time_delta, nepal_now


def is_price_in_range(target: float, current: float, delta_percent: float) -> bool:
    delta = current * (delta_percent / 100)
    return current - delta <= target <= current + delta


@dataclass
class AlertDecision:
    should_alert: bool
    reason: str


class AlertEvaluator:
    def should_alert(self, *, target_price: float, current_price: float, delta_percent: float, last_alert_time) -> AlertDecision:
        if last_alert_time and not check_time_delta(last_alert_time, 300):
            return AlertDecision(False, "cooldown")
        if is_price_in_range(target_price, current_price, delta_percent) or (
            current_price >= target_price and target_price > 100
        ):
            return AlertDecision(True, "matched")
        return AlertDecision(False, "out_of_range")


class TrackerService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)
        self.scripts = ScriptRepository(db)
        self.trackers = TrackerRepository(db)

    async def ensure_user(self, chat_id: int, username: str):
        user = await self.users.get_by_chat_id(chat_id)
        if user is None:
            user = await self.users.create(chat_id=chat_id, username=username)
            await self.db.commit()
        return user

    async def create_tracker(self, *, chat_id: int, username: str, ticker: str, price: float, delta: float):
        if price <= 0:
            raise ValidationError("Price must be greater than 0")
        if delta < 0:
            raise ValidationError("Delta must be 0 or greater")
        user = await self.ensure_user(chat_id=chat_id, username=username)
        script = await self.scripts.get_by_ticker(ticker.upper())
        if script is None:
            raise NotFoundError(f"Script with ticker {ticker.upper()} not found")
        tracker = await self.trackers.create(user_id=user.id, script_id=script.id, price=price, delta=delta)
        await self.db.commit()
        return tracker, script, user

    async def list_trackers(self, chat_id: int):
        user = await self.users.get_by_chat_id(chat_id)
        if user is None:
            return []
        return await self.trackers.list_for_user(user.id)

    async def mark_alert_sent(self, tracker, message_id: str | None):
        tracker.alert_message_id = message_id
        tracker.triggerd_at = nepal_now()
        await self.db.commit()

