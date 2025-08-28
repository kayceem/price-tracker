import asyncio
import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from .session import Base, engine
from sqlalchemy.orm import relationship
from datetime import timezone, timedelta
from utils import encrypt_password, decrypt_password

nepal_tz = timezone(timedelta(hours=5, minutes=45))

class Scripts(Base):
    __tablename__ = 'script'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(255), nullable=False)
    name = Column(String(500), nullable=True)
    href = Column(String(500), nullable=False)
    script_details = relationship("ScriptDetails", back_populates="script", uselist=False, cascade="all, delete-orphan")
    trackers = relationship("Tracker", back_populates="script", cascade="all, delete-orphan")

class ScriptDetails(Base):
    __tablename__ = 'script_details'

    id = Column(Integer, primary_key=True, autoincrement=True)
    script_id = Column(Integer, ForeignKey(Scripts.id), nullable=False)
    instrument_type = Column(String, nullable=False)
    listing_date = Column(String, nullable=False)
    last_traded_price = Column(Float, nullable=False)
    total_traded_quantity = Column(Integer, nullable=False)
    total_trades = Column(Integer, nullable=False)
    previous_day_close_price = Column(Float, nullable=False)
    high_price_low_price = Column(String, nullable=False)
    week_52_high_low = Column(String, nullable=False)
    open_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    total_listed_shares = Column(Integer, nullable=True)
    total_paid_up_value = Column(Float, nullable=True)
    market_capitalization = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda : datetime.datetime.now(nepal_tz), nullable=False)
    updated_at = Column(DateTime, default=lambda : datetime.datetime.now(nepal_tz), onupdate=lambda : datetime.datetime.now(nepal_tz), nullable=False)

    script = relationship("Scripts", back_populates="script_details")
    def __repr__(self):
        return f"<ScriptDetails(Script={self.script.ticker}, listing_date={self.listing_date}, last_traded_price={self.last_traded_price}, total_traded_quantity={self.total_traded_quantity}, total_trades={self.total_trades}, previous_day_close_price={self.previous_day_close_price}, high_price_low_price={self.high_price_low_price}, week_52_high_low={self.week_52_high_low}, open_price={self.open_price}, close_price={self.close_price}, total_listed_shares={self.total_listed_shares}, total_paid_up_value={self.total_paid_up_value}, market_capitalization={self.market_capitalization})>"

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

# async def create_tables_if_not_exists():
#         async with engine.begin() as conn:
#             await conn.run_sync(lambda conn: Base.metadata.create_all(conn, checkfirst=True))

# asyncio.run(create_tables_if_not_exists())