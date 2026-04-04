#!/usr/bin/env python3
"""
Entry point for running the web application (Portfolio Viewer & Floorsheet Viewer)
"""
from pathlib import Path

if __name__ == "__main__":
    import uvicorn
    from src.config.settings import WEB_HOST, WEB_PORT, WEB_RELOAD

    print(f"Portfolio Viewer: http://localhost:{WEB_PORT}/portfolio")
    print(f"Floorsheet Viewer: http://localhost:{WEB_PORT}/floorsheet")

    uvicorn.run(
        "src.web.app:app",
        host=WEB_HOST,
        port=WEB_PORT,
        reload=WEB_RELOAD
    )
