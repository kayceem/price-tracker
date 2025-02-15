import os
import datetime
from enum import Enum, auto
from functools import partial
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters
from telegram.ext._contexttypes import ContextTypes

from database import User, get_db
from database import Scripts, Tracker

from nepse import get_script_ltp

from utils import check_time_delta, is_price_in_range, valid_day_time, nepal_tz

load_dotenv()

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
    with get_db() as db:
        script = db.query(Scripts).filter(Scripts.ticker == ticker).first()
        if not script:
            message = await update.message.reply_text(f"Script with ticker {ticker} not found.\nPlease enter the valid stock ticker (e.g., AHPC):")
            context.user_data["message_ids"].extend([update.message.message_id, message.message_id])
            return TICKER
        context.user_data["script_id"] = script.id
        context.user_data["ticker"] = script.ticker
    ltp = await get_script_ltp(script.ticker)
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
        with get_db() as db:
            ticker, script_id, price, delta = context.user_data["ticker"],context.user_data["script_id"], context.user_data["price"], context.user_data["delta"]
            user = db.query(User).filter(User.chat_id == update.effective_user.id).first()
            tracker = Tracker(user_id=user.id, script_id=script_id, price=price, price_delta=delta)
            db.add(tracker)
            db.commit()
        await update.message.reply_text(f"Tracker set for {ticker}: Target {price:,.2f}, Δ {delta}%")
        context.user_data["message_ids"].extend([update.message.message_id])
    except Exception as e:
        print(f"Failed to add tracker: {e}")
    try:
        await context.bot.delete_messages(chat_id=update.effective_chat.id, message_ids=context.user_data["message_ids"])
    except Exception as e:
        print(f"Failed to delete messages: {e}")  # Log any issues
    context.bot_data["paused_users"].remove(update.effective_user.id)
    return ConversationHandler.END
 
async def check_trackers(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    chat_id = user_id
    while chat_id in context.bot_data.get("paused_users", set()):
        return
        
    with get_db() as db:
        trackers = db.query(Tracker).join(User).filter(User.chat_id == chat_id).all()
        for tracker in trackers:
            ltp = await get_script_ltp(tracker.script.ticker)
            alert_price = tracker.price
            price_delta = tracker.price_delta
            last_alert_time = tracker.triggerd_at
            last_alert_message_id = tracker.alert_message_id

            if check_time_delta(last_alert_time, 300) and is_price_in_range(alert_price, ltp, price_delta):
                if tracker.alert_message_id:
                    try:
                        await ptb.bot.delete_message(chat_id, last_alert_message_id)
                    except Exception as e:
                        print(f"Failed to delete message: {e}")
                alert_message = (
                        f"<b>Price Alert: <code>{tracker.script.ticker}</code></b>\n\n"
                        f"<b>LTP:</b> <code>{ltp:,.2f}</code>\n"
                        f"<b>Target:</b> <code>{tracker.price:,.2f}</code>\n"
                    )
                message = await ptb.bot.send_message(chat_id, alert_message, parse_mode="HTML")
                tracker.alert_message_id = message.message_id
                tracker.triggerd_at = datetime.datetime.now(nepal_tz)
                db.commit()

async def manage_tracker_jobs(context: ContextTypes.DEFAULT_TYPE):
     with get_db() as db:
        users = db.query(User).join(Tracker).distinct().all()
        if valid_day_time():
            for user in users:
                job_name = f"tracker_job_{user.id}"
                if not context.job_queue.get_jobs_by_name(job_name):
                    context.job_queue.run_repeating(
                        partial(check_trackers, user_id=user.id),
                        interval=60,
                        first=1,
                        name=job_name,
                    )
        else:
            for job in context.job_queue.jobs():
                if job.name.startswith("tracker_job_"):
                    job.schedule_removal()
 

async def start(update, _: ContextTypes.DEFAULT_TYPE):
    with get_db() as db:
        user = db.query(User).filter(User.chat_id == update.effective_user.id).first()
        try:
            await ptb.bot.delete_message(update.effective_user.id, update.message.message_id)
        except Exception as e:
            print(f"Failed to delete message: {e}") 
        if user:
            return await update.message.reply_text(f"You are already registered.")
        user = User(chat_id=update.effective_user.id, username=update.effective_user.first_name)
        db.add(user)
        db.commit()
        await update.message.reply_text(f"Welcome to NEPSE Price Tracker {update.effective_user.first_name}!")

async def add_tracker(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with get_db() as db:
        user = db.query(User).filter(User.chat_id == user_id).first()
        if not user:
            user = User(chat_id=user_id, username=update.effective_user.first_name)
            db.add(user)
            db.commit()
    if "paused_users" not in context.bot_data:
        context.bot_data["paused_users"] = set()
    context.bot_data["paused_users"].add(user_id)

    message= await update.message.reply_text("Please enter the stock ticker (e.g., AHPC):")
    context.user_data["message_ids"] = [update.message.message_id, message.message_id]
    return TrackerStates.TICKER

async def get_trackers(update, context: ContextTypes.DEFAULT_TYPE):
    with get_db() as db:
        user = db.query(User).filter(User.chat_id == update.effective_user.id).first()
        trackers = db.query(Tracker).filter(Tracker.user_id == user.id).all()
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
        context.bot_data["paused_users"].remove(update.effective_user.id)
        return ConversationHandler.END

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticker = update.message.text.split()[0].upper()
    with get_db() as db:
        script = db.query(Scripts).filter(Scripts.ticker == ticker).first()
        if not script:
            return await update.message.reply_text(f"Ask me a stock price")
        ltp = await get_script_ltp(script.ticker)
        if not ltp:
            return await update.message.reply_text(f"Failed to fetch LTP for {script.ticker}. Please try again later.")
        return await update.message.reply_text(f"{script.ticker}\n LTP: {ltp:,.2f}")

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
