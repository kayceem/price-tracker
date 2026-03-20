# Migration Guide

## Upgrading from Old Structure to New Structure

This guide helps you migrate from the old flat project structure to the new modular `src/` layout.

## What Changed?

### Directory Structure

**Old Structure:**
```
price-tracker/
├── portfolio_analyzer.py      # Core logic
├── portfolio_app.py            # Web app
├── server/                     # API routes
├── nepse/                      # NEPSE modules
├── database/                   # Database
├── services/                   # Services
├── utils/                      # Utils
├── templates/                  # Templates
├── static/                     # Static files
└── csv/                        # CSV data
```

**New Structure:**
```
price-tracker/
├── src/                        # All source code
│   ├── config/                 # Configuration
│   ├── core/                   # Business logic
│   │   ├── portfolio/          # Portfolio analyzer
│   │   └── nepse/              # NEPSE modules
│   ├── api/                    # API app & routes
│   ├── web/                    # Web app & assets
│   │   ├── templates/          # HTML templates
│   │   └── static/             # CSS/JS/images
│   ├── services/               # External services
│   ├── database/               # Database
│   └── utils/                  # Utilities
├── data/csv/                   # CSV data files
├── scripts/                    # Standalone scripts
├── notebooks/                  # Jupyter notebooks
└── run_portfolio_viewer.py    # Entry point
```

## Import Changes

### Configuration

**Old:**
```python
from dotenv import load_dotenv
import os

load_dotenv()
INTEREST_RATE = float(os.getenv('INTEREST_RATE', '24'))
```

**New:**
```python
from src.config.settings import config, INTEREST_RATE

# Access configuration
user_dir = config.get_user_csv_dir()
db_url = config.database_url
```

### Portfolio Analyzer

**Old:**
```python
from portfolio_analyzer import PortfolioAnalyzer

analyzer = PortfolioAnalyzer("3522757")
```

**New:**
```python
from src.core.portfolio.analyzer import PortfolioAnalyzer
from src.config.settings import config

analyzer = PortfolioAnalyzer(config.username)
```

### NEPSE Modules

**Old:**
```python
from nepse import get_script_ltp, refresh_script_details
```

**New:**
```python
from src.core.nepse import get_script_ltp, refresh_script_details
```

### Database

**Old:**
```python
from database import Scripts, get_db
```

**New:**
```python
from src.database import Scripts, get_db
```

### Utilities

**Old:**
```python
from utils import get_dir_path, check_time_delta
```

**New:**
```python
from src.config.settings import config  # For paths
from src.utils import check_time_delta   # For utilities
```

## Running the Application

### Web Application

**Old:**
```bash
python portfolio_app.py
```

**New:**
```bash
python run_portfolio_viewer.py
```
or
```bash
python -m src.web.app
```

### API Server

**Old:**
```bash
python server/main.py
```

**New:**
```bash
python -m src.api.main
```

## Data Files Migration

Your CSV data files need to be moved:

**Old Location:**
```
csv/{username}/
├── transactions.csv
├── Wacc Rates.csv
└── ...
```

**New Location:**
```
data/csv/{username}/
├── transactions.csv
├── Wacc Rates.csv
└── ...
```

### Migration Command

```bash
# If you have data in the old location
mv csv/* data/csv/
```

## Configuration File

The application now uses centralized configuration in `src/config/settings.py`.

Create a `.env` file in the project root:

```env
# Portfolio Settings
PORTFOLIO_USERNAME=your_username
INTEREST_RATE=24.0

# Web App Settings
WEB_HOST=0.0.0.0
WEB_PORT=8001
WEB_RELOAD=True

# API Settings
API_HOST=0.0.0.0
API_PORT=8000

# Database
DATABASE_URL=sqlite:///db.sqlite3
```

## Custom Scripts

If you have custom scripts that import from the old structure, update them:

```python
# Old imports
from portfolio_analyzer import PortfolioAnalyzer
from nepse import fetch_script_details
from utils import get_dir_path

# New imports
from src.core.portfolio.analyzer import PortfolioAnalyzer
from src.core.nepse import fetch_script_details
from src.config.settings import config
```

## Jupyter Notebooks

Update your notebook imports:

```python
# Add at the top of your notebook
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path.cwd()))

# Then use new imports
from src.core.portfolio.analyzer import PortfolioAnalyzer
from src.config.settings import config
```

## Benefits of New Structure

1. **Clear Separation** - Business logic, API, and web presentation are separate
2. **Standard Layout** - Follows Python best practices (src/ layout)
3. **Easy Testing** - Each module can be tested independently
4. **Better Organization** - Related code is grouped together
5. **Scalable** - Easy to add new features in the right place

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError`:
1. Make sure you're running from the project root
2. Install dependencies: `uv sync` or `pip install -r requirements.txt`
3. Use `uv run python` instead of `python` if using uv

### Path Errors

If CSV files aren't found:
1. Check that files are in `data/csv/{username}/`
2. Verify `PORTFOLIO_USERNAME` in `.env` matches your folder name
3. Use `config.get_user_csv_dir()` to get the correct path

### Template Errors

If templates aren't loading:
1. Templates should be in `src/web/templates/portfolio/`
2. Static files should be in `src/web/static/`
3. Check that `config.templates_dir` and `config.static_dir` point correctly

## Getting Help

- Check [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for detailed structure info
- Review [README.md](../README.md) for usage instructions
- Open an issue on GitHub for bugs or questions

## Rollback

If you need to rollback to the old structure, the old files are still in place:
- `portfolio_analyzer.py`
- `portfolio_app.py`
- `server/`
- `nepse/`

However, we recommend migrating to the new structure for better maintainability.
