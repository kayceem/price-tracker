#!/usr/bin/env python3
"""
Entry point for running the web application (Portfolio Viewer & Floorsheet Viewer)
"""
import logging

from src.shared.logging import configure_logging

if __name__ == "__main__":
    import uvicorn
    from src.config.settings import WEB_HOST, WEB_PORT, WEB_RELOAD

    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Portfolio Viewer: http://localhost:%s/portfolio", WEB_PORT)
    logger.info("Floorsheet Viewer: http://localhost:%s/floorsheet", WEB_PORT)

    uvicorn.run(
        "src.web.app:app",
        host=WEB_HOST,
        port=WEB_PORT,
        reload=WEB_RELOAD
    )
