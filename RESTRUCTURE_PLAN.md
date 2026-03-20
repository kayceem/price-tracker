# Project Restructuring Plan

## Current Structure Issues
1. `portfolio_analyzer.py` and `portfolio_app.py` are in root (should be organized)
2. Templates have no separation (portfolio vs general)
3. No clear separation between business logic and API layer
4. Static assets not properly organized
5. Configuration scattered across files
6. No clear structure for scripts vs library code

## Proposed New Structure

```
price-tracker/
├── src/                          # Main application source code
│   ├── __init__.py
│   ├── config/                   # Configuration management
│   │   ├── __init__.py
│   │   └── settings.py          # Centralized settings
│   │
│   ├── core/                     # Core business logic
│   │   ├── __init__.py
│   │   ├── portfolio/           # Portfolio analysis engine
│   │   │   ├── __init__.py
│   │   │   ├── analyzer.py      # Main portfolio analyzer (from portfolio_analyzer.py)
│   │   │   ├── fifo.py          # FIFO calculation logic
│   │   │   └── interest.py      # Interest calculation logic
│   │   │
│   │   └── nepse/               # NEPSE data fetching (moved from root)
│   │       ├── __init__.py
│   │       ├── meroshare.py
│   │       ├── tms.py
│   │       ├── npstocks.py
│   │       ├── fetch.py
│   │       └── script.py
│   │
│   ├── api/                      # API layer (FastAPI)
│   │   ├── __init__.py
│   │   ├── main.py              # Main FastAPI app (from server/main.py)
│   │   ├── dependencies.py      # Shared dependencies
│   │   │
│   │   ├── routes/              # API route modules
│   │   │   ├── __init__.py
│   │   │   ├── portfolio.py     # Portfolio endpoints (from server/portfolio_routes.py)
│   │   │   └── health.py        # Health check endpoints
│   │   │
│   │   └── middleware/          # Custom middleware
│   │       └── __init__.py
│   │
│   ├── web/                      # Web application (templates & static)
│   │   ├── __init__.py
│   │   ├── app.py               # Web app entry point (from portfolio_app.py)
│   │   │
│   │   ├── templates/           # Jinja2 templates
│   │   │   ├── base.html
│   │   │   ├── components/      # Reusable template components
│   │   │   │   ├── nav.html
│   │   │   │   └── footer.html
│   │   │   │
│   │   │   └── portfolio/       # Portfolio-specific templates
│   │   │       ├── dashboard.html
│   │   │       ├── holdings.html
│   │   │       ├── transactions.html
│   │   │       ├── lots.html
│   │   │       ├── script_detail.html
│   │   │       ├── interest.html
│   │   │       ├── sold_interest.html
│   │   │       └── reports.html
│   │   │
│   │   └── static/              # Static assets
│   │       ├── css/
│   │       │   └── custom.css
│   │       ├── js/
│   │       │   ├── portfolio.js
│   │       │   └── charts.js
│   │       └── images/
│   │
│   ├── services/                 # External services
│   │   ├── __init__.py
│   │   ├── telegram_bot.py
│   │   └── whatsapp.py
│   │
│   ├── database/                 # Database layer
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── session.py
│   │
│   └── utils/                    # Utility functions
│       ├── __init__.py
│       ├── formatters.py        # Data formatting utilities
│       └── helpers.py           # General helper functions
│
├── scripts/                      # Standalone scripts
│   ├── __init__.py
│   └── generate_reports.py      # Script to generate CSV reports
│
├── notebooks/                    # Jupyter notebooks (keep as is)
│   ├── __init__.py
│   └── *.ipynb
│
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── test_portfolio/
│   ├── test_api/
│   └── test_utils/
│
├── data/                         # Data directory
│   └── csv/                     # CSV files (moved from root)
│       └── {username}/
│
├── docs/                         # Documentation
│   ├── README.md
│   ├── API.md
│   └── SETUP.md
│
├── alembic/                      # Database migrations (keep as is)
│
├── .env                          # Environment variables
├── .env_example
├── .gitignore
├── pyproject.toml               # Project dependencies
├── uv.lock
├── README.md                    # Main README
└── db.sqlite3                   # Database file

```

## Migration Steps

### Phase 1: Create New Structure (No Breaking Changes)
1. Create all new directories
2. Copy files to new locations (don't delete old ones yet)
3. Update imports in copied files

### Phase 2: Update Entry Points
1. Update `portfolio_app.py` to point to new locations
2. Update API main.py to use new structure
3. Test that everything still works

### Phase 3: Clean Up
1. Delete old files
2. Update documentation
3. Add __init__.py files with proper exports

## Benefits
1. **Clear Separation of Concerns**: API, business logic, web app, services are separate
2. **Easier Navigation**: Related code is grouped together
3. **Better Testing**: Can test modules independently
4. **Scalability**: Easy to add new features
5. **Standard Python Structure**: Follows Python best practices
6. **Maintainability**: New developers can understand structure quickly

## Breaking Changes
- Import paths will change (e.g., `from portfolio_analyzer import` → `from src.core.portfolio.analyzer import`)
- Template paths will change (e.g., `templates/dashboard.html` → `src/web/templates/portfolio/dashboard.html`)
- Static file paths will change
