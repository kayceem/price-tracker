#!/usr/bin/env python3

import argparse
import asyncio
import logging
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.modules.portfolio import PortfolioPipeline
from src.shared.logging import configure_logging


logger = logging.getLogger(__name__)


async def main(username: str, headless: bool = True, tms_headless: bool = False):
    result = await PortfolioPipeline(
        username=username,
        headless=headless,
        tms_headless=tms_headless,
    ).run()
    logger.info("Pipeline complete for %s", username)
    logger.info("Base dir: %s", result.base_dir)
    logger.info("WACC report: %s", result.wacc_csv)
    logger.info("P&L workbook: %s", result.pnl_xlsx)
    logger.info("Analyzer reports: %s", result.reports_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run MeroShare sync, TMS trade book fetch, and portfolio analyzer in one command"
    )
    parser.add_argument("username", type=str, help="MeroShare username")
    parser.add_argument("--no-headless", action="store_true", help="Run MeroShare in non-headless mode")
    parser.add_argument("--tms-headless", action="store_true", help="Run TMS browser flow in headless mode")
    args = parser.parse_args()

    configure_logging()
    asyncio.run(main(args.username, headless=not args.no_headless, tms_headless=args.tms_headless))
