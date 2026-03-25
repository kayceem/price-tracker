"""
Configuration settings for the Price Tracker application.
"""
from pathlib import Path
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Data directories
DATA_DIR = BASE_DIR / "data"
CSV_DIR = DATA_DIR / "csv"

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/db.sqlite3")

# Portfolio Analysis Configuration
INTEREST_RATE = 24.0  # Annual interest rate percentage
USERNAME = os.getenv("PORTFOLIO_USERNAME", "3522757")

# API Configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_RELOAD = os.getenv("API_RELOAD", "True").lower() == "true"

# Web App Configuration
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "8001"))
WEB_RELOAD = os.getenv("WEB_RELOAD", "True").lower() == "true"

# Template Configuration
TEMPLATES_DIR = BASE_DIR / "src" / "web" / "templates"
STATIC_DIR = BASE_DIR / "src" / "web" / "static"

# External Services
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# NEPSE Configuration
NEPSE_CACHE_TTL = int(os.getenv("NEPSE_CACHE_TTL", "900"))

class Config:
    """Application configuration class"""

    def __init__(self):
        self.base_dir = BASE_DIR
        self.data_dir = DATA_DIR
        self.csv_dir = CSV_DIR
        self.database_url = DATABASE_URL
        self.interest_rate = INTEREST_RATE
        self.username = USERNAME
        self.templates_dir = TEMPLATES_DIR
        self.static_dir = STATIC_DIR

    def get_user_csv_dir(self, username: Optional[str] = None) -> Path:
        """Get CSV directory for a specific user"""
        user = username or self.username
        return self.csv_dir / user

    def ensure_directories(self):
        """Ensure all required directories exist"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        self.get_user_csv_dir().mkdir(parents=True, exist_ok=True)

# Global config instance
config = Config()
