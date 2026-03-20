# Project Structure Documentation

## Overview
This document explains the reorganized structure of the Price Tracker / Portfolio Viewer application.

## Directory Structure

```
price-tracker/
├── src/                              # Main application source code
│   ├── config/                       # Configuration management
│   │   ├── __init__.py
│   │   └── settings.py              # Centralized application settings
│   │
│   ├── core/                         # Core business logic
│   │   ├── portfolio/               # Portfolio analysis engine
│   │   │   ├── __init__.py
│   │   │   └── analyzer.py         # FIFO calculation & interest analysis
│   │   │
│   │   └── nepse/                   # NEPSE data fetching modules
│   │       ├── __init__.py
│   │       ├── meroshare.py        # Meroshare integration
│   │       ├── tms.py              # TMS integration
│   │       ├── npstocks.py         # NPStocks integration
│   │       ├── fetch.py            # Data fetching utilities
│   │       └── script.py           # Script management
│   │
│   ├── api/                          # FastAPI REST API layer
│   │   ├── __init__.py
│   │   ├── main.py                  # Main API application
│   │   ├── routes/                  # API route modules
│   │   │   ├── __init__.py
│   │   │   └── portfolio.py        # Portfolio endpoints
│   │   │
│   │   └── middleware/              # Custom middleware
│   │       └── __init__.py
│   │
│   ├── web/                          # Web application layer
│   │   ├── __init__.py
│   │   ├── app.py                   # FastAPI web app with template rendering
│   │   │
│   │   ├── templates/               # Jinja2 templates
│   │   │   ├── base.html           # Base template with layout
│   │   │   ├── components/         # Reusable template components
│   │   │   │   └── (future components)
│   │   │   │
│   │   │   └── portfolio/          # Portfolio-specific pages
│   │   │       ├── dashboard.html
│   │   │       ├── holdings.html
│   │   │       ├── transactions.html
│   │   │       ├── lots.html
│   │   │       ├── script_detail.html
│   │   │       ├── interest.html
│   │   │       ├── sold_interest.html
│   │   │       └── reports.html
│   │   │
│   │   └── static/                  # Static assets
│   │       ├── css/                # Custom CSS
│   │       ├── js/                 # Custom JavaScript
│   │       └── images/             # Images and icons
│   │
│   ├── services/                     # External service integrations
│   │   ├── __init__.py
│   │   ├── telegram_bot.py         # Telegram bot service
│   │   └── whatsapp.py             # WhatsApp integration
│   │
│   ├── database/                     # Database layer
│   │   ├── __init__.py
│   │   ├── models.py               # SQLAlchemy models
│   │   ├── schemas.py              # Pydantic schemas
│   │   └── session.py              # Database session management
│   │
│   └── utils/                        # Utility functions
│       ├── __init__.py
│       └── utils.py                # General utilities
│
├── scripts/                          # Standalone executable scripts
│   └── __init__.py
│
├── notebooks/                        # Jupyter notebooks for analysis
│   └── *.ipynb
│
├── tests/                            # Test suite
│   ├── __init__.py
│   ├── test_portfolio/
│   ├── test_api/
│   └── test_utils/
│
├── data/                             # Data directory
│   └── csv/                         # CSV data files
│       └── {username}/              # User-specific CSV files
│
├── docs/                             # Documentation
│   ├── PROJECT_STRUCTURE.md        # This file
│   └── API.md                      # API documentation (future)
│
├── alembic/                          # Database migration tools
│
├── run_portfolio_viewer.py          # Entry point to run web app
├── .env                              # Environment variables
├── .env_example                      # Example environment file
├── .gitignore
├── pyproject.toml                    # Project dependencies (uv)
├── uv.lock
├── README.md                         # Main project README
└── db.sqlite3                        # SQLite database

```

## Module Descriptions

### src/config/
- **settings.py**: Centralized configuration for all settings (paths, API keys, database URLs, etc.)
- Uses environment variables with sensible defaults
- Provides a `config` singleton for easy access throughout the app

### src/core/portfolio/
- **analyzer.py**: Core portfolio analysis engine
  - FIFO (First In, First Out) calculation
  - Interest cost calculation
  - P&L analysis (realized and unrealized)
  - Lot tracking

### src/core/nepse/
- Modules for fetching data from NEPSE sources
- **meroshare.py**: Meroshare API integration
- **tms.py**: TMS integration
- **npstocks.py**: NPStocks data fetching
- **fetch.py**: Common fetching utilities
- **script.py**: Script data management

### src/api/
- **main.py**: Main FastAPI application for REST API
- **routes/portfolio.py**: Portfolio-related API endpoints
  - `/api/portfolio/summary` - Portfolio summary
  - `/api/portfolio/holdings` - Current holdings
  - `/api/portfolio/transactions` - Transaction history
  - `/api/portfolio/script/{symbol}` - Script details
  - `/api/portfolio/stats` - Portfolio statistics
  - And more...

### src/web/
- **app.py**: Web application that serves HTML pages
- **templates/**: Jinja2 HTML templates
  - `base.html`: Base template with sidebar and navigation
  - `portfolio/*.html`: Portfolio-specific pages
- **static/**: CSS, JavaScript, and image assets

### src/services/
- External service integrations (Telegram, WhatsApp, etc.)
- Isolated from core business logic

### src/database/
- Database models, schemas, and session management
- Uses SQLAlchemy for ORM

### src/utils/
- General utility functions
- Formatters, helpers, etc.

## Import Patterns

### Importing Configuration
```python
from src.config.settings import config, INTEREST_RATE

# Access configuration
user_dir = config.get_user_csv_dir()
db_url = config.database_url
```

### Importing Core Logic
```python
from src.core.portfolio.analyzer import PortfolioAnalyzer

analyzer = PortfolioAnalyzer(username="3522757")
```

### Importing in API Routes
```python
from src.core.portfolio.analyzer import PortfolioAnalyzer
from src.config.settings import config

analyzer = PortfolioAnalyzer(config.username)
```

## Running the Application

### Portfolio Viewer (Web App)
```bash
python run_portfolio_viewer.py
```
or
```bash
python -m src.web.app
```

### API Server
```bash
python -m src.api.main
```

## Benefits of This Structure

1. **Clear Separation of Concerns**
   - Business logic (core) separate from API routes
   - Web presentation separate from API
   - Services isolated

2. **Easy to Test**
   - Each module can be tested independently
   - Mock dependencies easily

3. **Scalable**
   - Easy to add new features
   - Clear where new code belongs

4. **Standard Python Structure**
   - Follows Python best practices
   - Familiar to other developers

5. **Maintainable**
   - Related code is grouped together
   - Easy to navigate
   - Clear dependencies

## Configuration

All configuration is centralized in `src/config/settings.py` and can be overridden with environment variables in `.env`:

```env
# Portfolio
PORTFOLIO_USERNAME=3522757
INTEREST_RATE=24.0

# API
API_HOST=0.0.0.0
API_PORT=8000

# Web App
WEB_HOST=0.0.0.0
WEB_PORT=8001

# Database
DATABASE_URL=sqlite:///db.sqlite3
```
