from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from src.config.settings import config
from src.core.nepse import TradeBookFetcher, WaccReportGenerator

from .service import PortfolioQueryService


logger = logging.getLogger(__name__)


@dataclass
class PortfolioPipelineResult:
    base_dir: Path
    trade_book_csv: Path | None
    wacc_csv: Path
    pnl_xlsx: Path
    reports_dir: Path
    report_files: dict[str, Path]


class PortfolioPipeline:
    def __init__(self, username: str, headless: bool = True, tms_headless: bool = False):
        self.username = username
        self.headless = headless
        self.tms_headless = tms_headless

    async def run(self) -> PortfolioPipelineResult:
        logger.info("Starting portfolio pipeline for user=%s", self.username)
        base_dir = config.get_user_csv_dir(self.username)

        logger.info("Step 1/3: syncing MeroShare CSVs and generating WACC/P&L outputs")
        wacc_result = await WaccReportGenerator(username=self.username, headless=self.headless).generate()

        logger.info("Step 2/3: fetching TMS trade book")
        trade_book_path = base_dir / "history" / "Trade Book Details.csv"
        trade_book_result = await TradeBookFetcher(headless=self.tms_headless).fetch_and_save_async(
            save_path=trade_book_path
        )
        if trade_book_result is None:
            logger.warning("TMS trade book fetch failed; analyzer will use existing trade book data if present")
        else:
            logger.info("Trade book saved to %s", trade_book_result)

        logger.info("Step 3/3: running portfolio analyzer report generation")
        portfolio_service = PortfolioQueryService(username=self.username)
        report_files = portfolio_service.generate_reports()
        reports_dir = base_dir / "reports"
        logger.info("Portfolio analyzer reports written to %s", reports_dir)

        return PortfolioPipelineResult(
            base_dir=base_dir,
            trade_book_csv=trade_book_result,
            wacc_csv=wacc_result["wacc_csv"],
            pnl_xlsx=wacc_result["pnl_xlsx"],
            reports_dir=reports_dir,
            report_files=report_files,
        )
