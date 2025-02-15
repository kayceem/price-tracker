import os
from contextlib import asynccontextmanager
from http import HTTPStatus
from fastapi import FastAPI, Request, Response
import uvicorn
from  dotenv import load_dotenv

from database.schemas import  WhatsAppMessageSchema

from services import ptb, manage_tracker_jobs, whatsapp_message_handler, Update

from nepse.script import  refresh_script_details
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
load_dotenv()                   

scheduler = BackgroundScheduler()

def run_refresh():
    asyncio.run(refresh_script_details())

@asynccontextmanager
async def lifespan(_: FastAPI):
    scheduler.add_job(run_refresh, 'cron', minute='*/5', hour='8-15', day_of_week='0-6', max_instances=1)
    scheduler.start()
    await ptb.bot.setWebhook(os.getenv("WEBHOOK_URL"))
    async with ptb:
        await ptb.start()
        ptb.job_queue.run_repeating(
            manage_tracker_jobs,
            interval=300,
            first=1,
            name="market_hours_manager",
        )
        yield
        await ptb.stop()
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/")
async def process_update(request: Request):
    req = await request.json()
    update = Update.de_json(req, ptb.bot)
    await ptb.process_update(update)
    return Response(status_code=HTTPStatus.OK)


@app.route("/webhook", methods=["GET", "POST"])
async def webhook_handler(request: Request):
    if request.method == "GET":
        return Response(status_code=HTTPStatus.OK)  
    form_data = await request.form()
    try:
        message = WhatsAppMessageSchema(**form_data)
        asyncio.create_task(whatsapp_message_handler(message.model_dump()))
    except:
        pass
    return Response(status_code=HTTPStatus.OK)  

if __name__ == "__main__":
    uvicorn.run("main:app", port=8000)