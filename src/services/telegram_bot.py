import asyncio
import os
from enum import Enum, auto
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters
from telegram.ext._contexttypes import ContextTypes

from src.core.nepse import get_script_ltp
from src.infrastructure.db.session import get_db
from src.modules.alerts import AlertEvaluator, TrackerService
from src.modules.messaging import MarketMessageService
from src.infrastructure.db.repositories import ScriptRepository, TrackerRepository, UserRepository
import logging

load_dotenv()

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
    if os.getenv("TELEGRAM_BOT_TOKEN")
    else None
)


async def process_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticker = update.message.text.strip().upper()
    async with get_db() as db:
        script = await ScriptRepository(db).get_by_ticker(ticker)
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
            tracker_service = TrackerService(db)
            tracker, _, user = await tracker_service.create_tracker(
                chat_id=update.effective_user.id,
                username=update.effective_user.first_name,
                ticker=ticker,
                price=price,
                delta=delta,
            )
        await update.message.reply_text(f"Tracker set for {ticker}: Target {price:,.2f}, Δ {delta}%")
        context.user_data["message_ids"].extend([update.message.message_id])
    except Exception as e:
        logger.exception("Failed to add tracker")
    try:
        await context.bot.delete_messages(chat_id=update.effective_chat.id, message_ids=context.user_data["message_ids"])
    except Exception as e:
        logger.warning("Failed to delete tracker setup messages: %s", e)
    context.bot_data["paused_users"].remove(user.id)
    return ConversationHandler.END
    
async def send_tracker_alert(tracker_id: int , chat_id: int):
    if ptb is None:
        return
    async with get_db() as db:
        tracker_repo = TrackerRepository(db)
        tracker = await tracker_repo.get_by_id(tracker_id)
        ltp = tracker.script.script_details.last_traded_price
        updated_at = tracker.script.script_details.updated_at
        last_alert_message_id = tracker.alert_message_id
        decision = AlertEvaluator().should_alert(
            target_price=tracker.price,
            current_price=ltp,
            delta_percent=tracker.price_delta,
            last_alert_time=tracker.triggerd_at,
        )
        if decision.should_alert:
            if last_alert_message_id:
                try:
                    await ptb.bot.delete_message(chat_id, last_alert_message_id)
                except Exception as e:
                    logger.warning("Failed to delete previous tracker alert message: %s", e)
            alert_message = (
                    f"<b>Price Alert: <code>{tracker.script.ticker}</code></b>\n\n"
                    f"<b>LTP:</b> <code>{ltp:,.2f}</code>\n"
                    f"<b>Target:</b> <code>{tracker.price:,.2f}</code>\n"
                    f"<b>Time:</b> <code>{updated_at.strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
                )
            message = await ptb.bot.send_message(chat_id, alert_message, parse_mode="HTML")
            await TrackerService(db).mark_alert_sent(tracker, message.message_id)

async def check_trackers(context: ContextTypes.DEFAULT_TYPE):
    async with get_db() as db:
        users = await UserRepository(db).list_with_trackers()
        for user in users:
            if user.id in context.bot_data.get("paused_users", set()):
                continue
            for tracker in user.trackers:
                asyncio.create_task(send_tracker_alert(tracker.id, user.chat_id))

 

async def start(update, _: ContextTypes.DEFAULT_TYPE):
    if ptb is None:
        return
    async with get_db() as db:
        tracker_service = TrackerService(db)
        user = await UserRepository(db).get_by_chat_id(update.effective_user.id)
        try:
            await ptb.bot.delete_message(update.effective_user.id, update.message.message_id)
        except Exception as e:
            logger.warning("Failed to delete /start message: %s", e)
        if user:
            return await update.message.reply_text(f"You are already registered.")
        await tracker_service.ensure_user(update.effective_user.id, update.effective_user.first_name)
        await update.message.reply_text(f"Welcome to NEPSE Price Tracker {update.effective_user.first_name}!")

async def add_tracker(update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with get_db() as db:
        user = await TrackerService(db).ensure_user(user_id, update.effective_user.first_name)
    if "paused_users" not in context.bot_data:
        context.bot_data["paused_users"] = set()
    context.bot_data["paused_users"].add(user.id)

    message= await update.message.reply_text("Please enter the stock ticker (e.g., AHPC):")
    context.user_data["message_ids"] = [update.message.message_id, message.message_id]
    return TrackerStates.TICKER

async def get_trackers(update, context: ContextTypes.DEFAULT_TYPE):
    async with get_db() as db:
        user = await UserRepository(db).get_by_chat_id(update.effective_user.id)
        trackers = await TrackerService(db).list_trackers(update.effective_user.id)
        try:
            await ptb.bot.delete_message(user.chat_id, update.message.message_id)
        except Exception as e:
            logger.warning("Failed to delete /trackers message: %s", e)
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
        logger.warning("Failed to delete cancelled tracker messages: %s", e)
    async with get_db() as db:
        user = await UserRepository(db).get_by_chat_id(update.effective_user.id)
        if user:
            context.bot_data["paused_users"].remove(user.id)
    return ConversationHandler.END

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ticker = update.message.text.split()[0].upper()
    try:
        async with get_db() as db:
            script = await ScriptRepository(db).get_by_ticker(ticker, with_details=True)
            if not script:
                return await update.message.reply_text(f"Script with ticker {ticker} not found.")
            ltp = await get_script_ltp(db, script)
            if not ltp:
                return await update.message.reply_text(f"Failed to fetch LTP for {script.ticker}. Please try again later.")
    except Exception as e:
        return await update.message.reply_text(f"Failed to fetch LTP: {e}")
    message = MarketMessageService().format_telegram_snapshot(script, ltp)
    return await context.bot.send_message(update.effective_chat.id, message, parse_mode="HTML")

TICKER, PRICE, DELTA, CANCEL = TrackerStates.TICKER, TrackerStates.PRICE, TrackerStates.DELTA, TrackerStates.CANCEL
if ptb is not None:
    ptb.add_handler(CommandHandler("start", start))
    ptb.add_handler(CommandHandler("trackers", get_trackers))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("add_tracker", add_tracker)],
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
