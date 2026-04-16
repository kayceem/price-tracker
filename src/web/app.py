from src.app.factories import create_web_app
from src.shared.logging import configure_logging


app = create_web_app()

if __name__ == "__main__":
    import uvicorn
    import logging
    from src.shared.config import settings

    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Portfolio Viewer starting")
    logger.info("Open http://localhost:%s/portfolio", settings.web_port)
    uvicorn.run(app, host=settings.web_host, port=settings.web_port, reload=settings.web_reload)
