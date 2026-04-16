from __future__ import annotations

from pathlib import Path

import pandas as pd


class PortfolioCsvRepository:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.history_dir = self.base_dir / "history"

    def load_wacc_rates(self) -> pd.DataFrame:
        path = self.base_dir / "Wacc Rates.csv"
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_csv(path)
        return df[df["Balance"] > 0].copy()

    def load_trade_book(self) -> pd.DataFrame:
        path = self.history_dir / "Trade Book Details.csv"
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_csv(path)
        df["Date"] = pd.to_datetime(df["EXCHANGE TRADE ID"].astype(str).str[:8], format="%Y%m%d", errors="coerce")
        return df

    def load_transaction_history(self) -> pd.DataFrame:
        path = self.history_dir / "Transaction History.csv"
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_csv(path)
        df["Transaction Date"] = pd.to_datetime(df["Transaction Date"], errors="coerce")
        return df

