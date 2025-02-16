
import os
from database import Scripts
from database import get_db
from nepse import get_script_ltp


async def whatsapp_message_handler(message: dict):
    ticker = message['Body'].split()[0].upper()
    async with get_db() as db:
        script = db.execute(Scripts).filter(Scripts.ticker == ticker).first()
        if not script:
            reply = f"Script with ticker {ticker} not found.\nPlease enter the valid stock ticker (e.g., AHPC):"
        else:
            reply = f"{script.ticker}\n LTP: {await get_script_ltp(script.ticker):,.2f}"
    from twilio.rest import Client
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    client = Client(account_sid, auth_token)

    message_reply = client.messages.create(
        to=message['From'],
        from_=message['To'],
        body=reply,
    )
    print(f"Sent message to {message['From']}: {reply}")