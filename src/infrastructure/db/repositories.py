from __future__ import annotations

from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from .models import Broker, Floorsheet, MeroShareUser, ScriptDetails, Scripts, Tracker, User


class ScriptRepository:
    def __init__(self, db):
        self.db = db

    async def list_all(self) -> list[Scripts]:
        return (await self.db.execute(select(Scripts))).scalars().all()

    async def get_by_ticker(self, ticker: str, with_details: bool = False) -> Scripts | None:
        query = select(Scripts).filter(Scripts.ticker == ticker)
        if with_details:
            query = query.options(selectinload(Scripts.script_details))
        return (await self.db.execute(query)).scalars().first()

    async def get_by_id(self, script_id: int) -> Scripts | None:
        return (await self.db.execute(select(Scripts).filter(Scripts.id == script_id))).scalars().first()

    async def get_by_nepse_id(self, nepse_id: int) -> Scripts | None:
        return (await self.db.execute(select(Scripts).filter(Scripts.nepse_id == nepse_id))).scalars().first()

    async def create(self, **kwargs) -> Scripts:
        script = Scripts(**kwargs)
        self.db.add(script)
        await self.db.flush()
        return script


class ScriptDetailsRepository:
    def __init__(self, db):
        self.db = db

    async def get_by_script_id(self, script_id: int) -> ScriptDetails | None:
        return (
            await self.db.execute(select(ScriptDetails).filter(ScriptDetails.script_id == script_id))
        ).scalars().first()

    async def list_all(self) -> list[ScriptDetails]:
        return (await self.db.execute(select(ScriptDetails))).scalars().all()


class UserRepository:
    def __init__(self, db):
        self.db = db

    async def get_by_chat_id(self, chat_id: int) -> User | None:
        return (await self.db.execute(select(User).filter(User.chat_id == chat_id))).scalars().first()

    async def list_with_trackers(self) -> list[User]:
        query = select(User).join(Tracker).distinct().options(selectinload(User.trackers))
        return (await self.db.execute(query)).scalars().all()

    async def create(self, chat_id: int, username: str) -> User:
        user = User(chat_id=chat_id, username=username)
        self.db.add(user)
        await self.db.flush()
        return user


class TrackerRepository:
    def __init__(self, db):
        self.db = db

    async def list_for_user(self, user_id: int) -> list[Tracker]:
        query = select(Tracker).filter(Tracker.user_id == user_id).options(selectinload(Tracker.script))
        return (await self.db.execute(query)).scalars().all()

    async def list_with_scripts_for_user_ids(self) -> list[User]:
        query = select(User).join(Tracker).distinct().options(selectinload(User.trackers).selectinload(Tracker.script))
        return (await self.db.execute(query)).scalars().all()

    async def get_by_id(self, tracker_id: int) -> Tracker | None:
        query = (
            select(Tracker)
            .filter(Tracker.id == tracker_id)
            .options(selectinload(Tracker.script).selectinload(Scripts.script_details))
        )
        return (await self.db.execute(query)).scalars().first()

    async def list_tracked_scripts(self) -> list[Scripts]:
        query = select(Scripts).join(Tracker).distinct()
        return (await self.db.execute(query)).scalars().all()

    async def create(self, user_id: int, script_id: int, price: float, delta: float) -> Tracker:
        tracker = Tracker(user_id=user_id, script_id=script_id, price=price, price_delta=delta)
        self.db.add(tracker)
        await self.db.flush()
        return tracker


class BrokerRepository:
    def __init__(self, db):
        self.db = db

    async def get_by_member_id(self, member_id: str) -> Broker | None:
        return (await self.db.execute(select(Broker).filter(Broker.member_id == member_id))).scalars().first()

    async def get_or_create(self, member_id: str, name: str) -> Broker:
        broker = await self.get_by_member_id(member_id)
        if broker is None:
            broker = Broker(member_id=member_id, name=name)
            self.db.add(broker)
            await self.db.flush()
            return broker
        if broker.name != name:
            broker.name = name
        return broker


class FloorsheetRepository:
    def __init__(self, db):
        self.db = db

    async def list_available_dates(self) -> list[str]:
        result = await self.db.execute(select(Floorsheet.trade_date).distinct().order_by(Floorsheet.trade_date.desc()))
        return [row[0] for row in result.all()]

    async def exists_for_script_and_date(self, script_id: int, trade_date: str) -> bool:
        result = await self.db.execute(
            select(Floorsheet).filter(Floorsheet.script_id == script_id, Floorsheet.trade_date == trade_date)
        )
        return result.scalars().first() is not None

    async def get_by_contract_id(self, contract_id: int) -> Floorsheet | None:
        return (await self.db.execute(select(Floorsheet).filter(Floorsheet.contract_id == contract_id))).scalars().first()

    async def query_rows(self, date: str | None = None, ticker: str | None = None):
        buyer_broker = Broker.__table__.alias("buyer_broker")
        seller_broker = Broker.__table__.alias("seller_broker")
        query = (
            select(
                Floorsheet,
                Scripts.ticker.label("stock_symbol"),
                buyer_broker.c.member_id.label("buyer_member_id"),
                seller_broker.c.member_id.label("seller_member_id"),
                buyer_broker.c.name.label("buyer_broker_name"),
                seller_broker.c.name.label("seller_broker_name"),
            )
            .join(Scripts, Floorsheet.script_id == Scripts.id)
            .outerjoin(buyer_broker, Floorsheet.buyer_broker_id == buyer_broker.c.id)
            .outerjoin(seller_broker, Floorsheet.seller_broker_id == seller_broker.c.id)
        )
        filters = []
        if date:
            filters.append(Floorsheet.trade_date == date)
        if ticker:
            filters.append(Scripts.ticker == ticker)
        if filters:
            query = query.filter(and_(*filters))
        query = query.order_by(Floorsheet.trade_time.asc())
        return (await self.db.execute(query)).all()


class MeroShareUserRepository:
    def __init__(self, db):
        self.db = db

    async def get_by_username(self, username: str) -> MeroShareUser | None:
        return (await self.db.execute(select(MeroShareUser).filter(MeroShareUser.username == username))).scalars().first()

