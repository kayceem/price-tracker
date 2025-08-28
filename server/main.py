import os
from contextlib import asynccontextmanager
from http import HTTPStatus
from fastapi import FastAPI, Request, Response
from  dotenv import load_dotenv

from database.schemas import  WhatsAppMessageSchema

from services import ptb, whatsapp_message_handler, Update, check_trackers

from nepse import  refresh_script_details

import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()                   

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(_: FastAPI):
    tracker_schedule = {
            'trigger': 'cron',
            'day_of_week': '0-4',
            'hour': '10-14',
            'minute': '*/10',
            'max_instances': 1,
            'timezone': 'Asia/Kathmandu'
    }
    refresh_script_schedule = {
            'trigger': 'cron',
            'day_of_week': '0-4',
            'hour': '10-14',
            'minute': '*/3',
            'max_instances': 1,
            'timezone': 'Asia/Kathmandu'
    }
        
    scheduler.add_job(refresh_script_details, **refresh_script_schedule)
    scheduler.start()
    await ptb.bot.setWebhook(os.getenv("WEBHOOK_URL"))
    async with ptb:
        await ptb.start()
        ptb.job_queue.run_custom(
            check_trackers,
            name="tracker_checker",
            job_kwargs=tracker_schedule
        )
        # for job in ptb.job_queue.jobs():
            # print(f"Job {job.name} scheduled to run at {job.next_t}")

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
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)