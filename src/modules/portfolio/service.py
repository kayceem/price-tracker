from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.shared.config import settings
from src.shared.exceptions import NotFoundError

from .csv_repository import PortfolioCsvRepository


@dataclass
class PortfolioDataset:
    wacc_df: pd.DataFrame
    trade_book_df: pd.DataFrame
    transaction_history_df: pd.DataFrame


class PortfolioQueryService:
    def __init__(self, username: str | None = None, csv_base_path: str | Path | None = None):
        self.username = username or settings.default_username
        base_dir = Path(csv_base_path) if csv_base_path else settings.get_user_csv_dir(self.username)
        self.repository = PortfolioCsvRepository(base_dir)

    def _dataset(self) -> PortfolioDataset:
        return PortfolioDataset(
            wacc_df=self.repository.load_wacc_rates(),
            trade_book_df=self.repository.load_trade_book(),
            transaction_history_df=self.repository.load_transaction_history(),
        )

    def get_current_prices(self) -> dict[str, float]:
        dataset = self._dataset()
        if dataset.wacc_df.empty:
            return {}
        return {row["Scrip"]: float(row["LTP"]) for _, row in dataset.wacc_df.iterrows()}

    def get_wacc_snapshot(self) -> dict[str, dict[str, float | None]]:
        dataset = self._dataset()
        snapshot: dict[str, dict[str, float | None]] = {}
        for _, row in dataset.wacc_df.iterrows():
            snapshot[row["Scrip"]] = {
                "High": float(row.get("High", 0)) if pd.notna(row.get("High")) else None,
                "Low": float(row.get("Low", 0)) if pd.notna(row.get("Low")) else None,
            }
        return snapshot

    def _calculate_realized_pnl(self, trade_book_df: pd.DataFrame) -> dict[str, dict[str, float]]:
        if trade_book_df.empty:
            return {}
        realized_by_scrip: dict[str, dict[str, float]] = {}
        for scrip in trade_book_df["SYMBOL"].unique():
            scrip_trades = trade_book_df[trade_book_df["SYMBOL"] == scrip].sort_values("Date")
            purchase_queue: list[dict[str, float]] = []
            total_realized_pnl = 0.0
            total_sold_cost_basis = 0.0
            for _, trade in scrip_trades.iterrows():
                qty = float(trade["TRADE QTY"])
                price = float(trade["PRICE(NPR)"])
                if trade["BUY/SELL"] == "Buy":
                    purchase_queue.append({"qty": qty, "price": price})
                    continue
                remaining_to_sell = qty
                sell_proceeds = qty * price
                cost_basis = 0.0
                while remaining_to_sell > 0 and purchase_queue:
                    oldest_purchase = purchase_queue[0]
                    if oldest_purchase["qty"] <= remaining_to_sell:
                        cost_basis += oldest_purchase["qty"] * oldest_purchase["price"]
                        remaining_to_sell -= oldest_purchase["qty"]
                        purchase_queue.pop(0)
                    else:
                        cost_basis += remaining_to_sell * oldest_purchase["price"]
                        oldest_purchase["qty"] -= remaining_to_sell
                        remaining_to_sell = 0
                total_realized_pnl += sell_proceeds - cost_basis
                total_sold_cost_basis += cost_basis
            if total_realized_pnl or total_sold_cost_basis:
                realized_by_scrip[scrip] = {
                    "realized_pnl": total_realized_pnl,
                    "sold_cost_basis": total_sold_cost_basis,
                }
        return realized_by_scrip

    def get_current_holdings(self, current_prices: dict[str, float] | None = None) -> pd.DataFrame:
        dataset = self._dataset()
        if dataset.wacc_df.empty:
            return pd.DataFrame()
        holdings_data: list[dict[str, Any]] = []
        current_prices = current_prices or {}
        for _, row in dataset.wacc_df.iterrows():
            scrip = row["Scrip"]
            quantity = float(row["Balance"])
            wacc = float(row["WACC"])
            investment = float(row["Investment"])
            ltp = current_prices.get(scrip) if current_prices else float(row.get("LTP", 0))
            current_value = quantity * ltp if ltp else float(row.get("Current Value", 0))
            unrealized_pnl = float(row.get("Profit/Loss", current_value - investment))
            scrip_trades = dataset.trade_book_df[dataset.trade_book_df["SYMBOL"] == scrip]
            buy_trades = scrip_trades[scrip_trades["BUY/SELL"] == "Buy"]
            if not buy_trades.empty:
                first_purchase = buy_trades["Date"].min()
                days_held = (datetime.now() - first_purchase).days
            else:
                first_purchase = None
                days_held = 0
            interest = (investment * settings.interest_rate / 100 * days_held / 365) if days_held > 0 else 0
            holdings_data.append(
                {
                    "Scrip": scrip,
                    "Quantity": quantity,
                    "Avg Cost": round(wacc, 2),
                    "Total Cost": round(investment, 2),
                    "First Purchase": first_purchase.date() if first_purchase else None,
                    "Days Held": days_held,
                    "Interest Cost": round(interest, 2),
                    "Current Price": ltp,
                    "Current Value": round(current_value, 2),
                    "Unrealized P&L": round(unrealized_pnl, 2),
                    "Unrealized P&L %": round((unrealized_pnl / investment * 100), 2) if investment > 0 else 0,
                }
            )
        return pd.DataFrame(holdings_data)

    def get_portfolio_summary(self, current_prices: dict[str, float] | None = None) -> pd.DataFrame:
        dataset = self._dataset()
        holdings_df = self.get_current_holdings(current_prices)
        realized_pnl_by_scrip = self._calculate_realized_pnl(dataset.trade_book_df)
        all_scrips = set(holdings_df["Scrip"].tolist()) | set(realized_pnl_by_scrip.keys()) if not holdings_df.empty else set(realized_pnl_by_scrip.keys())
        summary_data = []
        for scrip in all_scrips:
            if not holdings_df.empty and scrip in holdings_df["Scrip"].values:
                holding = holdings_df[holdings_df["Scrip"] == scrip].iloc[0]
                current_qty = holding["Quantity"]
                avg_cost = holding["Avg Cost"]
                current_holdings_cost = holding["Total Cost"]
                interest_current = holding["Interest Cost"]
                current_price = holding["Current Price"]
                current_value = holding["Current Value"]
                unrealized = holding["Unrealized P&L"]
            else:
                current_qty = 0
                avg_cost = 0
                current_holdings_cost = 0
                interest_current = 0
                current_price = (current_prices or {}).get(scrip, 0)
                current_value = 0
                unrealized = 0
            realized_info = realized_pnl_by_scrip.get(scrip, {"realized_pnl": 0, "sold_cost_basis": 0})
            realized = realized_info["realized_pnl"]
            sold_cost = realized_info["sold_cost_basis"]
            total_investment = current_holdings_cost + sold_cost
            total_pnl = realized + unrealized
            net_pnl = total_pnl - interest_current
            week_52_high = None
            week_52_low = None
            if not dataset.wacc_df.empty and scrip in dataset.wacc_df["Scrip"].values:
                wacc_row = dataset.wacc_df[dataset.wacc_df["Scrip"] == scrip].iloc[0]
                week_52_high = float(wacc_row.get("High", 0)) if pd.notna(wacc_row.get("High")) else None
                week_52_low = float(wacc_row.get("Low", 0)) if pd.notna(wacc_row.get("Low")) else None
            summary_data.append(
                {
                    "Scrip": scrip,
                    "Current Holdings": current_qty,
                    "Avg Cost": round(avg_cost, 2),
                    "Total Investment": round(total_investment, 2),
                    "Current Price": current_price,
                    "Current Value": round(current_value, 2),
                    "Realized P&L": round(realized, 2),
                    "Unrealized P&L": round(unrealized, 2),
                    "Total P&L": round(total_pnl, 2),
                    "Interest Cost": round(interest_current, 2),
                    "Net P&L (After Interest)": round(net_pnl, 2),
                    "Total Return %": round((total_pnl / total_investment * 100), 2) if total_investment > 0 else 0,
                    "Net Return %": round((net_pnl / total_investment * 100), 2) if total_investment > 0 else 0,
                    "52 Week High": week_52_high,
                    "52 Week Low": week_52_low,
                }
            )
        df = pd.DataFrame(summary_data)
        if not df.empty:
            df = df.sort_values("Total Investment", ascending=False)
        return df

    def get_transaction_history(self) -> pd.DataFrame:
        dataset = self._dataset()
        transactions = []
        if not dataset.trade_book_df.empty:
            for _, row in dataset.trade_book_df.iterrows():
                transactions.append(
                    {
                        "Date": row["Date"],
                        "Scrip": row["SYMBOL"],
                        "Type": row["BUY/SELL"].upper(),
                        "Quantity": float(row["TRADE QTY"]),
                        "Price": float(row["PRICE(NPR)"]),
                        "Amount": float(row["Value(NPR)"]),
                        "Description": f"Trade Book: {row['BUY/SELL']}",
                    }
                )
        if not dataset.transaction_history_df.empty:
            for _, row in dataset.transaction_history_df.iterrows():
                desc = str(row["History Description"]).upper()
                credit = row.get("Credit Quantity")
                if not credit or credit == "-":
                    continue
                qty = float(credit)
                if "IPO" in desc or "INITIAL PUBLIC OFFERING" in desc:
                    transactions.append(
                        {
                            "Date": row["Transaction Date"],
                            "Scrip": row["Scrip"],
                            "Type": "IPO",
                            "Quantity": qty,
                            "Price": 100.0,
                            "Amount": qty * 100.0,
                            "Description": row["History Description"],
                        }
                    )
                elif "BONUS" in desc or "CA-BONUS" in desc:
                    transactions.append(
                        {
                            "Date": row["Transaction Date"],
                            "Scrip": row["Scrip"],
                            "Type": "BONUS",
                            "Quantity": qty,
                            "Price": 0.0,
                            "Amount": 0.0,
                            "Description": row["History Description"],
                        }
                    )
        df = pd.DataFrame(transactions)
        if not df.empty:
            df = df.sort_values("Date", ascending=False)
        return df

    def get_detailed_pools(self, current_prices: dict[str, float] | None = None) -> pd.DataFrame:
        return self.get_current_holdings(current_prices).rename(
            columns={
                "First Purchase": "First Purchase Date",
                "Total Cost": "Total Cost Basis",
                "Avg Cost": "Avg Purchase Price",
            }
        ).assign(
            **{
                "Last Purchase Date": lambda x: x["First Purchase Date"],
                "Net P&L (After Interest)": lambda x: x["Unrealized P&L"] - x["Interest Cost"],
            }
        )

    def get_interest_analysis(self) -> pd.DataFrame:
        holdings = self.get_current_holdings()
        if holdings.empty:
            return pd.DataFrame()
        df = pd.DataFrame(
            [
                {
                    "Scrip": row["Scrip"],
                    "Investment Amount": row["Total Cost"],
                    "Days Held": row["Days Held"],
                    "Interest Rate %": settings.interest_rate,
                    "Interest Cost": row["Interest Cost"],
                    "Interest % of Investment": round((row["Interest Cost"] / row["Total Cost"] * 100), 2)
                    if row["Total Cost"] > 0
                    else 0,
                }
                for _, row in holdings.iterrows()
            ]
        )
        return df.sort_values("Interest Cost", ascending=False) if not df.empty else df

    def get_sold_interest_analysis(self) -> pd.DataFrame:
        dataset = self._dataset()
        realized = self._calculate_realized_pnl(dataset.trade_book_df)
        sold_data = []
        for scrip, info in realized.items():
            if info["sold_cost_basis"] <= 0:
                continue
            scrip_trades = dataset.trade_book_df[dataset.trade_book_df["SYMBOL"] == scrip]
            sell_trades = scrip_trades[scrip_trades["BUY/SELL"] == "Sell"]
            buy_trades = scrip_trades[scrip_trades["BUY/SELL"] == "Buy"]
            if sell_trades.empty or buy_trades.empty:
                continue
            first_buy = buy_trades["Date"].min()
            last_sell = sell_trades["Date"].max()
            avg_days_held = (last_sell - first_buy).days
            interest = info["sold_cost_basis"] * settings.interest_rate / 100 * avg_days_held / 365
            sold_data.append(
                {
                    "Scrip": scrip,
                    "Total Sold Quantity": sell_trades["TRADE QTY"].sum(),
                    "Investment Amount": round(info["sold_cost_basis"], 2),
                    "Avg Days Held": round(avg_days_held, 1),
                    "Interest Rate %": settings.interest_rate,
                    "Interest Cost": round(interest, 2),
                    "Interest % of Investment": round((interest / info["sold_cost_basis"] * 100), 2)
                    if info["sold_cost_basis"] > 0
                    else 0,
                    "Realized P&L": round(info["realized_pnl"], 2),
                    "Net P&L (After Interest)": round(info["realized_pnl"] - interest, 2),
                }
            )
        df = pd.DataFrame(sold_data)
        return df.sort_values("Interest Cost", ascending=False) if not df.empty else df

    def get_portfolio_stats(self) -> dict[str, Any]:
        current_prices = self.get_current_prices()
        summary_df = self.get_portfolio_summary(current_prices)
        holdings_df = self.get_current_holdings(current_prices)
        trans_df = self.get_transaction_history()
        filtered_holdings = holdings_df[holdings_df["Quantity"] >= 15].copy() if not holdings_df.empty else pd.DataFrame()
        if not filtered_holdings.empty:
            filtered_holdings = filtered_holdings.dropna(subset=["Unrealized P&L %"])
        top_5 = filtered_holdings.nlargest(5, "Unrealized P&L %")[["Scrip", "Unrealized P&L", "Unrealized P&L %"]].to_dict("records") if not filtered_holdings.empty else []
        bottom_5 = filtered_holdings.nsmallest(5, "Unrealized P&L %")[["Scrip", "Unrealized P&L", "Unrealized P&L %"]].to_dict("records") if not filtered_holdings.empty else []
        close_to_high = []
        close_to_low = []
        if not summary_df.empty:
            for _, script in summary_df.iterrows():
                try:
                    if (
                        script["Current Holdings"] > 0
                        and pd.notna(script["52 Week High"])
                        and pd.notna(script["Current Price"])
                        and script["52 Week High"] != 0
                        and script["Current Price"] != 0
                    ):
                        current_price = float(script["Current Price"])
                        week_52_high = float(script["52 Week High"])
                        distance_pct = ((current_price - week_52_high) / week_52_high) * 100
                        if pd.notna(distance_pct) and not math.isinf(distance_pct):
                            close_to_high.append(
                                {
                                    "Scrip": script["Scrip"],
                                    "Current Price": current_price,
                                    "52 Week High": week_52_high,
                                    "Distance from High %": round(distance_pct, 2),
                                }
                            )
                    if (
                        script["Current Holdings"] > 0
                        and pd.notna(script["52 Week Low"])
                        and pd.notna(script["Current Price"])
                        and script["52 Week Low"] != 0
                        and script["Current Price"] != 0
                    ):
                        current_price = float(script["Current Price"])
                        week_52_low = float(script["52 Week Low"])
                        distance_pct = ((current_price - week_52_low) / week_52_low) * 100
                        if pd.notna(distance_pct) and not math.isinf(distance_pct):
                            close_to_low.append(
                                {
                                    "Scrip": script["Scrip"],
                                    "Current Price": current_price,
                                    "52 Week Low": week_52_low,
                                    "Distance from Low %": round(distance_pct, 2),
                                }
                            )
                except (ValueError, TypeError, ZeroDivisionError):
                    continue
        return {
            "top_performers": top_5,
            "bottom_performers": bottom_5,
            "close_to_high": sorted(close_to_high, key=lambda x: x["Distance from High %"], reverse=True)[:10],
            "close_to_low": sorted(close_to_low, key=lambda x: x["Distance from Low %"])[:10],
            "transaction_count": len(trans_df),
            "holding_count": len(holdings_df),
        }

    def get_script_detail(self, symbol: str) -> dict[str, Any]:
        current_prices = self.get_current_prices()
        summary_df = self.get_portfolio_summary(current_prices)
        if summary_df.empty:
            raise NotFoundError(f"Script {symbol} not found")
        script_summary = summary_df[summary_df["Scrip"] == symbol]
        if script_summary.empty:
            raise NotFoundError(f"Script {symbol} not found")
        trans_df = self.get_transaction_history()
        script_trans = trans_df[trans_df["Scrip"] == symbol].copy()
        if not script_trans.empty:
            script_trans["Date"] = script_trans["Date"].astype(str)
        pools_df = self.get_detailed_pools(current_prices)
        script_pool = pools_df[pools_df["Scrip"] == symbol].copy() if not pools_df.empty else pd.DataFrame()
        for column in ["First Purchase Date", "Last Purchase Date"]:
            if column in script_pool.columns:
                script_pool[column] = script_pool[column].astype(str)
        return {
            "summary": script_summary.fillna(0).to_dict("records")[0],
            "transactions": script_trans.fillna("").to_dict("records"),
            "pool": script_pool.fillna(0).to_dict("records")[0] if len(script_pool) > 0 else None,
            "current_price": current_prices.get(symbol, 0),
        }

    def generate_reports(self, output_dir: str | Path | None = None) -> dict[str, Path]:
        base_dir = self.repository.base_dir
        output_dir = Path(output_dir) if output_dir else base_dir / "reports"
        output_dir.mkdir(parents=True, exist_ok=True)

        current_prices = self.get_current_prices()
        report_frames = {
            "portfolio_summary": self.get_portfolio_summary(current_prices),
            "transaction_history": self.get_transaction_history(),
            "current_holdings": self.get_current_holdings(current_prices),
            "detailed_pools": self.get_detailed_pools(current_prices),
            "interest_analysis": self.get_interest_analysis(),
            "sold_interest_analysis": self.get_sold_interest_analysis(),
        }
        file_names = {
            "portfolio_summary": "portfolio_summary.csv",
            "transaction_history": "transaction_history.csv",
            "current_holdings": "current_holdings.csv",
            "detailed_pools": "detailed_holdings_pools.csv",
            "interest_analysis": "interest_analysis.csv",
            "sold_interest_analysis": "sold_interest_analysis.csv",
        }

        output_paths: dict[str, Path] = {}
        for key, frame in report_frames.items():
            path = output_dir / file_names[key]
            frame.to_csv(path, index=False)
            output_paths[key] = path

        return output_paths
