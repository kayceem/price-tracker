import asyncio
import datetime
import sqlalchemy
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from .session import Base, engine
from sqlalchemy.orm import relationship
from datetime import timezone, timedelta
from src.utils import encrypt_password, decrypt_password

nepal_tz = timezone(timedelta(hours=5, minutes=45))

class Scripts(Base):
    __tablename__ = 'script'

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(500), nullable=True)
    href = Column(String(500), nullable=False)
    nepse_id = Column(Integer, nullable=True, unique=True, index=True)  # Stock ID from NEPSE API
    script_details = relationship("ScriptDetails", back_populates="script", uselist=False, cascade="all, delete-orphan")
    trackers = relationship("Tracker", back_populates="script", cascade="all, delete-orphan")
    floorsheets = relationship("Floorsheet", back_populates="script", cascade="all, delete-orphan")

class ScriptDetails(Base):
    __tablename__ = 'script_details'

    id = Column(Integer, primary_key=True, autoincrement=True)
    script_id = Column(Integer, ForeignKey(Scripts.id), nullable=False)
    last_traded_price = Column(Float, nullable=False)
    total_traded_quantity = Column(Integer, nullable=False)
    total_trades = Column(Integer, nullable=False)
    previous_day_close_price = Column(Float, nullable=False)
    high_price_low_price = Column(String, nullable=False)
    week_52_high_low = Column(String, nullable=False)
    open_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    market_capitalization = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda : datetime.datetime.now(nepal_tz), nullable=False)
    updated_at = Column(DateTime, default=lambda : datetime.datetime.now(nepal_tz), onupdate=lambda : datetime.datetime.now(nepal_tz), nullable=False)

    script = relationship("Scripts", back_populates="script_details")
    def __repr__(self):
        return f"<ScriptDetails(Script={self.script.ticker})>"

class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, nullable=False)
    username = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda : datetime.datetime.now(nepal_tz), nullable=False)


    trackers = relationship("Tracker", back_populates="user",  cascade="all, delete-orphan")

class MeroShareUser(Base):
    __tablename__ = 'meroshare-user'
    id = Column(Integer, primary_key=True, autoincrement=True)
    dp = Column(Integer, nullable=False)
    username = Column(String(255), nullable=False)
    _password = Column('password', String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(), nullable=False)

    def __init__(self, username, dp, password):
        self.username = username
        self.dp = dp
        self.set_password(password)

    def set_password(self, password: str):
        self._password = encrypt_password(password)

    def get_password(self):
        return decrypt_password(self._password)

    def to_dict(self):
        return {
            'id': self.id,
            'dp': self.dp,
            'username': self.username,
            'created_at': self.created_at,
            'password': self.get_password()
            }

class Tracker(Base):
    __tablename__ = 'tracker'

    id = Column(Integer, primary_key=True, autoincrement=True)
    script_id = Column(Integer, ForeignKey(Scripts.id), nullable=False)
    user_id = Column(Integer, ForeignKey(User.id), nullable=False)
    price = Column(Float, nullable=False)
    price_delta = Column(Float, nullable=False, default=0.5)
    triggerd_at = Column(DateTime, nullable=True)
    alert_message_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda : datetime.datetime.now(nepal_tz), nullable=False)

    user = relationship("User", back_populates="trackers")
    script = relationship("Scripts", back_populates="trackers")

class Broker(Base):
    __tablename__ = 'broker'

    id = Column(Integer, primary_key=True, autoincrement=True)
    member_id = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=lambda : datetime.datetime.now(nepal_tz), nullable=False)

    # Relationships
    floorsheets_as_buyer = relationship("Floorsheet", foreign_keys="Floorsheet.buyer_broker_id", back_populates="buyer_broker")
    floorsheets_as_seller = relationship("Floorsheet", foreign_keys="Floorsheet.seller_broker_id", back_populates="seller_broker")

    def __repr__(self):
        return f"<Broker(id={self.member_id}, name={self.name})>"

class Floorsheet(Base):
    __tablename__ = 'floorsheet'
    __table_args__ = (
        # Unique constraint on contract_id + trade_date combination
        sqlalchemy.UniqueConstraint('contract_id', 'trade_date', name='uq_contract_trade_date'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(Integer, nullable=False, index=True)
    script_id = Column(Integer, ForeignKey('script.id'), nullable=False, index=True)
    buyer_broker_id = Column(Integer, ForeignKey('broker.id'), nullable=True)
    seller_broker_id = Column(Integer, ForeignKey('broker.id'), nullable=True)
    contract_quantity = Column(Integer, nullable=False)
    contract_rate = Column(Float, nullable=False)
    contract_amount = Column(Float, nullable=False)
    trade_book_id = Column(Integer, nullable=False)
    trade_date = Column(String(50), nullable=False, index=True)
    trade_time = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=lambda : datetime.datetime.now(nepal_tz), nullable=False)

    # Relationships
    script = relationship("Scripts", back_populates="floorsheets")
    buyer_broker = relationship("Broker", foreign_keys=[buyer_broker_id], back_populates="floorsheets_as_buyer")
    seller_broker = relationship("Broker", foreign_keys=[seller_broker_id], back_populates="floorsheets_as_seller")

    def __repr__(self):
        return f"<Floorsheet(contract_id={self.contract_id}, script={self.script.ticker if self.script else 'N/A'}, date={self.trade_date})>"

async def create_tables_if_not_exists():
        async with engine.begin() as conn:
            await conn.run_sync(lambda conn: Base.metadata.create_all(conn, checkfirst=True))

# asyncio.run(create_tables_if_not_exists())