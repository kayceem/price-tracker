from __future__ import annotations

from src.shared.exceptions import NotFoundError


class MarketMessageService:
    def format_market_snapshot(self, script, ltp: float) -> str:
        details = script.script_details
        if details is None:
            raise NotFoundError(f"No script details found for {script.ticker}")
        return (
            f"{script.ticker}\n"
            f"{'-'*30}\n"
            f"LTP: {ltp:,.2f}\n"
            f"Open: {details.open_price:,.2f}\n"
            f"High - Low: {details.high_price_low_price}\n"
            f"Time: {details.updated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        )

    def format_telegram_snapshot(self, script, ltp: float) -> str:
        details = script.script_details
        if details is None:
            raise NotFoundError(f"No script details found for {script.ticker}")
        return (
            f"<b>{script.ticker}</b>\n"
            f"<b>{'-'*30}</b>\n"
            f"📌 <b>LTP:</b> <code>{ltp:,.2f}</code>\n"
            f"📌 <b>Open:</b> <code>{details.open_price:,.2f}</code>\n"
            f"📌 <b>High - Low:</b> <code>{details.high_price_low_price}</code>\n"
            f"📌 <b>Time:</b> <code>{details.updated_at.strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
        )

