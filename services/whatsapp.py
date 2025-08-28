
import os
from database import Scripts
from database import get_db
from nepse import get_script_ltp
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from twilio.rest import Client

async def whatsapp_message_handler(message: dict):
    ticker = message['Body'].split()[0].upper()
    async with get_db() as db:
        script = (await db.execute(select(Scripts).filter(Scripts.ticker == ticker).options(selectinload(Scripts.script_details)))).scalars().first()
        if not script:
            reply = f"Script with ticker {ticker} not found.\nPlease enter the valid stock ticker (e.g., AHPC):"
        else:
            ltp = await get_script_ltp(db, script)
            updated_at = script.script_details.updated_at
            open_price = script.script_details.open_price
            high_price_low_price = script.script_details.high_price_low_price
            reply = (
                f"{script.ticker}\n"
                f"{'-'*30}\n"
                f"📌 LTP: {ltp:,.2f}\n"
                f"📌 Open: {open_price:,.2f}\n"
                f"📌 High - Low: {high_price_low_price}\n"
                f"📌 Time: {updated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    client = Client(account_sid, auth_token)

    message_reply = client.messages.create(
        to=message['From'],
        from_=message['To'],
        body=reply,
    )