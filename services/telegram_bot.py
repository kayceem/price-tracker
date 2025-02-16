import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import datetime
from enum import Enum, auto
from functools import partial
from dotenv import load_dotenv

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from telegram import Update
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters
from telegram.ext._contexttypes import ContextTypes
from telegram.constants import ChatAction

from database import User, get_db
from database import Scripts, Tracker

from nepse import get_script_ltp

from utils import check_time_delta, is_price_in_range, valid_day_time, nepal_tz
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TrackerStates(Enum):
    TICKER = auto()
    PRICE = auto()
    DELTA = auto()
    CANCEL = auto()
    
ptb = (
    Application.builder()
    .updater(None)
    .token(os.getenv("TELEGRAM_BOT_TOKEN"))
    .read_timeout(7)
    .get_updates_read_timeout(42)
    .build()
)


async def process_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticker = update.message.text.strip().upper()
    async with get_db() as db:
        script = (await db.execute(select(Scripts).filter(Scripts.ticker == ticker))).scalars().first()
        if not script:
            message = await update.message.reply_text(f"Script with ticker {ticker} not found.\nPlease enter the valid stock ticker (e.g., AHPC):")
            context.user_data["message_ids"].extend([update.message.message_id, message.message_id])
            return TICKER
        context.user_data["script_id"] = script.id
        context.user_data["ticker"] = script.ticker
        ltp = await get_script_ltp(db, script)
    if not ltp:
        message = await update.message.reply_text(f"Failed to fetch LTP for {script.ticker}. Please try again later.")
        context.user_data["message_ids"].extend([update.message.message_id])
        return CANCEL
    message = await update.message.reply_text(f"Enter the target price(LTP: {ltp}):")
    context.user_data["message_ids"].extend([update.message.message_id, message.message_id])
    return PRICE

async def process_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["price"] = float(update.message.text.strip())
    except ValueError:
        message = await update.message.reply_text("Invalid price! Please enter a valid number.")
        context.user_data["message_ids"].extend([update.message.message_id, message.message_id])
        return PRICE
    message =  await update.message.reply_text("Enter the price fluctuation delta (%):")
    context.user_data["message_ids"].extend([update.message.message_id, message.message_id])
    return DELTA

async def process_delta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["delta"] = float(update.message.text.strip())
    except ValueError:
        message= await update.message.reply_text("Invalid delta! Please enter a valid percentage.")
        context.user_data["message_ids"].extend([update.message.message_id, message.message_id])
        return DELTA
    try:
        async with get_db() as db:
            ticker, script_id, price, delta = context.user_data["ticker"],context.user_data["script_id"], context.user_data["price"], context.user_data["delta"]
            user = (await db.execute(select(User).filter(User.chat_id == update.effective_user.id))).scalars().first()
            tracker = Tracker(user_id=user.id, script_id=script_id, price=price, price_delta=delta)
            await db.add(tracker)
            await db.commit()
        await update.message.reply_text(f"Tracker set for {ticker}: Target {price:,.2f}, Δ {delta}%")
        context.user_data["message_ids"].extend([update.message.message_id])
    except Exception as e:
        print(f"Failed to add tracker: {e}")
    try:
        await context.bot.delete_messages(chat_id=update.effective_chat.id, message_ids=context.user_data["message_ids"])
    except Exception as e:
        print(f"Failed to delete messages: {e}")  # Log any issues
    context.bot_data["paused_users"].remove(user.id)
    return ConversationHandler.END
    
async def send_tracker_alert(tracker_id: int , chat_id: int):
    async with get_db() as db:
        tracker = (await db.execute(select(Tracker).filter(Tracker.id == tracker_id).options(selectinload(Tracker.script).selectinload(Scripts.script_details)))).scalars().first()
        ltp = tracker.script.script_details.last_traded_price
        updated_at = tracker.script.script_details.updated_at
        alert_price = tracker.price
        price_delta = tracker.price_delta
        last_alert_message_id = tracker.alert_message_id

        if is_price_in_range(alert_price, ltp, price_delta) or (ltp>=alert_price and alert_price>100):
            if last_alert_message_id:
                try:
                    await ptb.bot.delete_message(chat_id, last_alert_message_id)
                except Exception as e:
                    print(f"Failed to delete message: {e}")
            alert_message = (
                    f"<b>Price Alert: <code>{tracker.script.ticker}</code></b>\n\n"
                    f"<b>LTP:</b> <code>{ltp:,.2f}</code>\n"
                    f"<b>Target:</b> <code>{tracker.price:,.2f}</code>\n"
                    f"<b>Time:</b> <code>{updated_at.strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
                )
            message = await ptb.bot.send_message(chat_id, alert_message, parse_mode="HTML")
            tracker.alert_message_id = message.message_id
            tracker.triggerd_at = datetime.datetime.now(nepal_tz)
        await db.commit()

async def check_trackers(context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int):
    if user_id in context.bot_data.get("paused_users", set()):
        return
        
    async with get_db() as db:
        trackers = (await db.execute(select(Tracker).join(User).filter(User.id == user_id).options(selectinload(Tracker.script)))).scalars().all()
        tasks = []
        for tracker in trackers:
            last_alert_time = tracker.triggerd_at
            if last_alert_time and not check_time_delta(last_alert_time, 300):
                continue
            tasks.append(asyncio.create_task(send_tracker_alert(tracker.id, chat_id)))

async def manage_tracker_jobs(context: ContextTypes.DEFAULT_TYPE):
     async with get_db() as db:
        users = (await db.execute(select(User).join(Tracker).distinct())).scalars().all()
        if valid_day_time():
            for user in users:
                job_name = f"tracker_job_{user.id}"
                if not context.job_queue.get_jobs_by_name(job_name):
                    context.job_queue.run_repeating(
                        partial(check_trackers, user_id=user.id, chat_id=user.chat_id), 
                        interval=60,
                        first=1,
                        name=job_name,
                    )
        else:
            for job in context.job_queue.jobs():
                if job.name.startswith("tracker_job_"):
                    job.schedule_removal()
 

async def start(update, _: ContextTypes.DEFAULT_TYPE):
    async with get_db() as db:
        user = (await db.execute(select(User).filter(User.chat_id == update.effective_user.id))).scalars().first()
        try:
            await ptb.bot.delete_message(update.effective_user.id, update.message.message_id)
        except Exception as e:
            print(f"Failed to delete message: {e}") 
        if user:
            return await update.message.reply_text(f"You are already registered.")
        user = User(chat_id=update.effective_user.id, username=update.effective_user.first_name)
        await db.add(user)
        await db.commit()
        await update.message.reply_text(f"Welcome to NEPSE Price Tracker {update.effective_user.first_name}!")

async def add_tracker(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with get_db() as db:
        user = (await db.execute(select(User).filter(User.chat_id == user_id))).scalars().first()
        if not user:
            user = User(chat_id=user_id, username=update.effective_user.first_name)
            await db.add(user)
            await db.commit()
    if "paused_users" not in context.bot_data:
        context.bot_data["paused_users"] = set()
    context.bot_data["paused_users"].add(user.id)

    message= await update.message.reply_text("Please enter the stock ticker (e.g., AHPC):")
    context.user_data["message_ids"] = [update.message.message_id, message.message_id]
    return TrackerStates.TICKER

async def get_trackers(update, context: ContextTypes.DEFAULT_TYPE):
    async with get_db() as db:
        user = (await db.execute(select(User).filter(User.chat_id == update.effective_user.id))).scalars().first()
        trackers = (await db.execute(select(Tracker).filter(Tracker.user_id == user.id).options(selectinload(Tracker.script)))).scalars().all()
        try:
            await ptb.bot.delete_message(user.chat_id, update.message.message_id)
        except Exception as e:
            print(f"Failed to delete message: {e}") 
        if not trackers:
            return await update.message.reply_text("You don't have any trackers.")
        tracker_info = "<b>Trackers:</b>\n\n"
        tracker_info += f"<b>Ticker</b> |\t<b>Price</b> |\t<b>Delta</b>\n{'-'*30}\n"
        tracker_info += "\n".join([f"{tracker.script.ticker} |\t{tracker.price} |\t{tracker.price_delta}\n{'-'*30}\n" for tracker in trackers])
        await context.bot.send_message(user.chat_id, text=tracker_info, parse_mode="HTML")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.delete_messages(chat_id=update.effective_chat.id, message_ids=context.user_data["message_ids"])
    except Exception as e:
        print(f"Failed to delete messages: {e}")
    finally:
        async with get_db() as db:
            user = (await db.execute(select(User).filter(User.chat_id == update.effective_user.id))).scalars().first()
            if user:
                context.bot_data["paused_users"].remove(user.id)
        return ConversationHandler.END

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticker = update.message.text.split()[0].upper()
    try:
        async with get_db() as db:
            script = (await db.execute(select(Scripts).filter(Scripts.ticker == ticker).options(selectinload(Scripts.script_details)))).scalars().first()
            if not script:
                return await update.message.reply_text(f"Script with ticker {ticker} not found.")
            ltp = await get_script_ltp(db, script)
            updated_at = script.script_details.updated_at
            open_price = script.script_details.open_price
            high_price_low_price = script.script_details.high_price_low_price
            week_52_high_low = script.script_details.week_52_high_low
            if not ltp:
                return await update.message.reply_text(f"Failed to fetch LTP for {script.ticker}. Please try again later.")
    except Exception as e:
        return await update.message.reply_text(f"Failed to fetch LTP: {e}")
    message = (
        f"<b>{script.ticker}</b>\n"
        f"<b>{"-"*30}</b>\n"
        f"📌 <b>LTP:</b> <code>{ltp:,.2f}</code>\n"
        f"📌 <b>Open:</b> <code>{open_price:,.2f}</code>\n"
        f"📌 <b>High - Low:</b> <code>{high_price_low_price}</code>\n"
        f"📌 <b>Time:</b> <code>{updated_at.strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
    )
    return await context.bot.send_message(update.effective_chat.id, message, parse_mode="HTML")

TICKER, PRICE, DELTA, CANCEL = TrackerStates.TICKER, TrackerStates.PRICE, TrackerStates.DELTA, TrackerStates.CANCEL
ptb.add_handler(CommandHandler("start", start))
ptb.add_handler(CommandHandler("trackers", get_trackers))

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("add_tracker", add_tracker),],
    states={
        TICKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_ticker)],
        PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_price)],
        DELTA: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_delta)],
        CANCEL: [CommandHandler("cancel", cancel)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
ptb.add_handler(conv_handler)
