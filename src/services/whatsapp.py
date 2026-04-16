import os
from sqlalchemy.orm import selectinload
from src.core.nepse import get_script_ltp
from src.infrastructure.db.repositories import ScriptRepository
from src.infrastructure.db.session import get_db
from src.modules.messaging import MarketMessageService
from twilio.rest import Client

async def whatsapp_message_handler(message: dict):
    ticker = message['Body'].split()[0].upper()
    async with get_db() as db:
        script = await ScriptRepository(db).get_by_ticker(ticker, with_details=True)
        if not script:
            reply = f"Script with ticker {ticker} not found.\nPlease enter the valid stock ticker (e.g., AHPC):"
        else:
            ltp = await get_script_ltp(db, script)
            reply = MarketMessageService().format_market_snapshot(script, ltp)
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    client = Client(account_sid, auth_token)

    message_reply = client.messages.create(
        to=message['From'],
        from_=message['To'],
        body=reply,
    )
