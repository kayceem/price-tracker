"""
Standalone Portfolio Viewer App
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Portfolio Viewer")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Include portfolio routes
from server.portfolio_routes import router as portfolio_router
app.include_router(portfolio_router)

# Template routes
@app.get("/")
async def root():
    """Redirect to portfolio dashboard"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/portfolio")

@app.get("/portfolio")
async def portfolio_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/portfolio/holdings")
async def portfolio_holdings(request: Request):
    return templates.TemplateResponse("holdings.html", {"request": request})

@app.get("/portfolio/transactions")
async def portfolio_transactions(request: Request):
    return templates.TemplateResponse("transactions.html", {"request": request})

@app.get("/portfolio/lots")
async def portfolio_lots(request: Request):
    return templates.TemplateResponse("lots.html", {"request": request})

@app.get("/portfolio/interest")
async def portfolio_interest(request: Request):
    return templates.TemplateResponse("interest.html", {"request": request})

@app.get("/portfolio/sold-interest")
async def portfolio_sold_interest(request: Request):
    return templates.TemplateResponse("sold_interest.html", {"request": request})

@app.get("/portfolio/reports")
async def portfolio_reports(request: Request):
    return templates.TemplateResponse("reports.html", {"request": request})

@app.get("/portfolio/script/{symbol}")
async def portfolio_script_detail(request: Request, symbol: str):
    return templates.TemplateResponse("script_detail.html", {"request": request, "symbol": symbol})

if __name__ == "__main__":
    import uvicorn
    print("="*70)
    print("Portfolio Viewer Starting...")
    print("="*70)
    print("Open your browser and navigate to: http://localhost:8000/portfolio")
    print("="*70)
    uvicorn.run(app, host="0.0.0.0", port=8000)
