"""
Standalone Portfolio Viewer App
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

from src.config.settings import config, WEB_HOST, WEB_PORT, WEB_RELOAD
from src.api.routes.portfolio import router as portfolio_router

app = FastAPI(title="Portfolio Viewer")

# Mount static files and templates
app.mount("/static", StaticFiles(directory=str(config.static_dir)), name="static")
templates = Jinja2Templates(directory=str(config.templates_dir))

# Include portfolio routes
app.include_router(portfolio_router)

# Template routes
@app.get("/")
async def root():
    """Redirect to portfolio dashboard"""
    return RedirectResponse(url="/portfolio")

@app.get("/portfolio")
async def portfolio_dashboard(request: Request):
    return templates.TemplateResponse("portfolio/dashboard.html", {"request": request})

@app.get("/portfolio/holdings")
async def portfolio_holdings(request: Request):
    return templates.TemplateResponse("portfolio/holdings.html", {"request": request})

@app.get("/portfolio/transactions")
async def portfolio_transactions(request: Request):
    return templates.TemplateResponse("portfolio/transactions.html", {"request": request})

@app.get("/portfolio/lots")
async def portfolio_lots(request: Request):
    return templates.TemplateResponse("portfolio/lots.html", {"request": request})

@app.get("/portfolio/interest")
async def portfolio_interest(request: Request):
    return templates.TemplateResponse("portfolio/interest.html", {"request": request})

@app.get("/portfolio/sold-interest")
async def portfolio_sold_interest(request: Request):
    return templates.TemplateResponse("portfolio/sold_interest.html", {"request": request})

@app.get("/portfolio/reports")
async def portfolio_reports(request: Request):
    return templates.TemplateResponse("portfolio/reports.html", {"request": request})

@app.get("/portfolio/script/{symbol}")
async def portfolio_script_detail(request: Request, symbol: str):
    return templates.TemplateResponse("portfolio/script_detail.html", {"request": request, "symbol": symbol})

if __name__ == "__main__":
    import uvicorn
    print("="*70)
    print("Portfolio Viewer Starting...")
    print("="*70)
    print(f"Open your browser and navigate to: http://localhost:{WEB_PORT}/portfolio")
    print("="*70)
    uvicorn.run(app, host=WEB_HOST, port=WEB_PORT, reload=WEB_RELOAD)
