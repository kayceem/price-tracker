#!/usr/bin/env python3
"""
Entry point for running the Portfolio Viewer web application
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    import uvicorn
    from src.config.settings import WEB_HOST, WEB_PORT, WEB_RELOAD
    from src.web.app import app

    print("="*70)
    print("Portfolio Viewer Starting...")
    print("="*70)
    print(f"Open your browser and navigate to: http://localhost:{WEB_PORT}/portfolio")
    print("="*70)

    uvicorn.run(
        "src.web.app:app",
        host=WEB_HOST,
        port=WEB_PORT,
        reload=WEB_RELOAD
    )
