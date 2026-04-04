from pydantic import BaseModel, Field, field_validator
from typing import Any, Literal, Optional, Union
from datetime import datetime

class ScriptDetailsSchema(BaseModel):
    script_id: Any
    instrument_type: str = Field(..., alias="Instrument Type")
    listing_date: str = Field(..., alias="Listing Date")
    last_traded_price: float = Field(..., alias="Last Traded Price")
    total_traded_quantity: int = Field(..., alias="Total Traded Quantity")
    total_trades: int = Field(..., alias="Total Trades")
    previous_day_close_price: float = Field(..., alias="Previous Day Close Price")
    high_price_low_price: str = Field(..., alias="High Price - Low Price")
    week_52_high_low: str = Field(..., alias="52 Week High - 52 Week Low")
    open_price: float = Field(..., alias="Open Price")
    close_price: float = Field(..., alias="Close Price*")
    total_listed_shares: Optional[int] = Field(..., alias="Total Listed Shares")
    total_paid_up_value: Optional[float] = Field(..., alias="Total Paid up Value")

    @field_validator("total_listed_shares","last_traded_price", mode="after")
    def check_value(cls, value):
        if value <= 0:
            raise ValueError("Value should be greater than 0")
        return value

    @field_validator("last_traded_price", mode="before")
    def split_differences(cls, value):
        return float(value.split()[0].replace(',','')) if isinstance(value, str) else value

    @field_validator("total_traded_quantity","total_trades","previous_day_close_price","open_price","close_price","total_listed_shares","total_paid_up_value", mode="before")
    def remove_commas(cls, value):
        return float(value.replace(",", "")) if isinstance(value, str) else value

    class Config:
        populate_by_name = True

class TrackerInputSchema(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10, description="Stock ticker symbol")
    price: float = Field(..., gt=0, description="Target price for alert")
    delta: float = Field(..., ge=0, description="Allowed price fluctuation percentage")
    script_id: Optional[int] 
    user_id: Optional[int] 
    @classmethod
    def from_message(cls, message_text: str) -> Union["TrackerInputSchema", None]:
        """Parses the message text and validates the extracted fields."""
        try:
            parts = message_text.split(" ")
            if len(parts) != 4:
                return None  # Invalid input format

            return cls(ticker=parts[1], price=float(parts[2]), delta=float(parts[3]))
        except (ValueError, IndexError):
            return None  # Handle conversion errors or missing fields
class WhatsAppMessageSchema(BaseModel):
    SmsMessageSid: str = Field(..., description="The unique identifier for the SMS message")
    NumMedia: int = Field(..., description="Number of media attachments")
    ProfileName: str = Field(..., description="The sender's WhatsApp profile name")
    MessageType: Literal["text"] = Field(..., description="Type of the message")
    SmsSid: str = Field(..., description="The unique identifier for the SMS")
    WaId: str = Field(..., description="WhatsApp ID of the sender")
    SmsStatus: str = Field(..., description="Status of the SMS message")
    Body: str = Field(..., description="Content of the message")
    To: str = Field(..., description="Recipient's WhatsApp number with whatsapp: prefix")
    NumSegments: int = Field(..., description="Number of message segments")
    ReferralNumMedia: int = Field(..., description="Number of media in referral")
    MessageSid: str = Field(..., description="The unique identifier for the message")
    AccountSid: str = Field(..., description="The Twilio Account SID")
    From: str = Field(..., description="Sender's WhatsApp number with whatsapp: prefix")
    ApiVersion: str = Field(..., description="Twilio API version")

    class Config:
        from_attributes = True

class BrokerSchema(BaseModel):
    member_id: str
    name: str

    class Config:
        from_attributes = True

class FloorsheetSchema(BaseModel):
    contract_id: int = Field(..., alias="contractId")
    stock_symbol: str = Field(..., alias="stockSymbol")
    stock_id: int = Field(..., alias="stockId")
    buyer_member_id: str = Field(..., alias="buyerMemberId")
    seller_member_id: str = Field(..., alias="sellerMemberId")
    buyer_broker_name: Optional[str] = Field(None, alias="buyerBrokerName")
    seller_broker_name: Optional[str] = Field(None, alias="sellerBrokerName")
    contract_quantity: int = Field(..., alias="contractQuantity")
    contract_rate: float = Field(..., alias="contractRate")
    contract_amount: float = Field(..., alias="contractAmount")
    trade_book_id: int = Field(..., alias="tradeBookId")
    trade_date: str = Field(default="", alias="tradeTime")
    trade_time: str = Field(default="", alias="tradeTime")
    security_name: Optional[str] = Field(None, alias="securityName")

    # These will be populated during processing, not from API
    script_id: Optional[int] = None
    buyer_broker_id: Optional[int] = None
    seller_broker_id: Optional[int] = None

    @field_validator("trade_date", mode="before")
    def parse_trade_date(cls, value):
        """Extract date from ISO format datetime string"""
        if isinstance(value, str):
            # Handle ISO format: 2026-04-02T11:00:33.197375
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d')
        return value

    @field_validator("trade_time", mode="before")
    def parse_trade_time(cls, value):
        """Extract time from ISO format datetime string"""
        if isinstance(value, str):
            # Handle ISO format: 2026-04-02T11:00:33.197375
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return dt.strftime('%H:%M:%S.%f')
        return value

    class Config:
        populate_by_name = True

class FetchListItemSchema(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    force: bool = Field(default=False, description="Force refetch even if data exists")