# 📈 Price Tracker / Portfolio Viewer

A comprehensive stock portfolio analyzer and viewer for NEPSE (Nepal Stock Exchange) with FIFO P&L calculation, interest cost analysis, and beautiful web interface.

## ✨ Features

- 📊 **FIFO Portfolio Analysis** - First In, First Out calculation for accurate P&L
- 💰 **Interest Cost Tracking** - Calculate opportunity cost of capital
- 📈 **Performance Analytics** - Track realized and unrealized P&L
- 🎯 **52-Week High/Low Analysis** - Identify momentum stocks
- 📱 **Beautiful Web Interface** - Modern, responsive design with charts
- 📉 **Transaction History** - Complete audit trail of all trades
- 📦 **Lot Tracking** - Detailed view of purchase lots
- 📊 **Interactive Charts** - Visualize portfolio composition and performance
- 🔍 **Script Search** - Quick search with autocomplete (Ctrl+K)
- 💡 **Interest Toggle** - Show/hide interest analysis dynamically

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd price-tracker
```

2. Install dependencies using uv:
```bash
uv sync
```

Or using pip:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env_example .env
# Edit .env with your configuration
```

4. Add your transaction CSV files to `data/csv/{username}/`

### Running the Application

**Portfolio Viewer (Web Interface):**
```bash
python run_portfolio_viewer.py
```

Then open your browser to: http://localhost:8001/portfolio

**API Server Only:**
```bash
python -m src.api.main
```

## 📁 Project Structure

```
price-tracker/
├── src/                    # Application source code
│   ├── config/            # Configuration management
│   ├── core/              # Business logic (portfolio, NEPSE)
│   ├── api/               # REST API endpoints
│   ├── web/               # Web app (templates, static)
│   ├── services/          # External services (Telegram, WhatsApp)
│   ├── database/          # Database models
│   └── utils/             # Utilities
├── data/                   # Data files (CSV)
├── scripts/                # Standalone scripts
├── notebooks/              # Jupyter notebooks
├── tests/                  # Test suite
└── docs/                   # Documentation
```

See [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) for detailed structure documentation.

## 💻 Usage

### Portfolio Dashboard
- View overall portfolio performance
- See top/bottom performers
- Track stocks close to 52-week high
- View portfolio composition

### Holdings Page
- Current holdings with unrealized P&L
- Sortable table with all metrics
- Click on any stock for details

### Transaction History
- Complete transaction log
- Filter by script, type, date range
- Export to CSV

### Script Detail Page
- Detailed analysis for individual stocks
- Transaction history for that stock
- Lot-level details with FIFO tracking
- 52-week high/low analysis
- Direct links to TMS and NEPSE Alpha

### Interest Analysis
- See opportunity cost on all holdings
- What-if calculator for different interest rates
- Scripts with high interest cost warning
- Sold stocks interest analysis

## ⚙️ Configuration

Configure the application via environment variables in `.env`:

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

## 📊 Data Format

Place your transaction CSV files in `data/csv/{username}/`:

- `transactions.csv` - All buy/sell transactions
- `Wacc Rates.csv` - Current prices and 52-week data
- `current_holdings.csv` - Current holdings summary

## 🛠️ Development

### Running Tests
```bash
pytest tests/
```

### Code Structure
- **src/core/portfolio/** - Portfolio calculation engine
- **src/api/routes/** - API endpoint definitions
- **src/web/templates/** - HTML templates
- **src/config/settings.py** - Centralized configuration

### Adding New Features
1. Business logic goes in `src/core/`
2. API endpoints go in `src/api/routes/`
3. Web pages go in `src/web/templates/portfolio/`
4. Configuration in `src/config/settings.py`

## 📚 Documentation

- [Project Structure](docs/PROJECT_STRUCTURE.md) - Detailed structure documentation
- [API Documentation](docs/API.md) - API endpoint reference (TODO)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Charts powered by [Chart.js](https://www.chartjs.org/)
- UI components with [Tailwind CSS](https://tailwindcss.com/)
- Interactive tables with [DataTables](https://datatables.net/)
- Reactivity with [Alpine.js](https://alpinejs.dev/)

## 📧 Contact

For questions or support, please open an issue on GitHub.

---

Made with ❤️ for NEPSE traders
