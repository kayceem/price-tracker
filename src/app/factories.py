from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from http import HTTPStatus

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

from src.infrastructure.db.session import SessionLocal
from src.interfaces.http.api.routes.floorsheet import router as floorsheet_api_router
from src.interfaces.http.api.routes.portfolio import router as portfolio_api_router
from src.modules.market_data import ScriptRefreshService
from src.services import Update, ptb, whatsapp_message_handler, check_trackers
from src.shared.config import settings
from src.shared.logging import configure_logging


configure_logging()
scheduler = AsyncIOScheduler()


def create_api_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        tracker_schedule = {
            "trigger": "cron",
            "day_of_week": "0-4",
            "hour": "10-14",
            "minute": "*/10",
            "max_instances": 1,
            "timezone": "Asia/Kathmandu",
        }
        refresh_script_schedule = {
            "trigger": "cron",
            "day_of_week": "0-4",
            "hour": "10-14",
            "minute": "*/3",
            "max_instances": 1,
            "timezone": "Asia/Kathmandu",
        }

        async def refresh_tracked_scripts():
            async with SessionLocal() as db:
                await ScriptRefreshService(db).refresh_tracked()

        scheduler.add_job(refresh_tracked_scripts, **refresh_script_schedule)
        scheduler.start()
        if ptb is None:
            yield
            scheduler.shutdown()
            return
        if settings.webhook_url:
            await ptb.bot.setWebhook(settings.webhook_url)
        async with ptb:
            await ptb.start()
            ptb.job_queue.run_custom(check_trackers, name="tracker_checker", job_kwargs=tracker_schedule)
            yield
            await ptb.stop()
        scheduler.shutdown()

    app = FastAPI(lifespan=lifespan)

    @app.middleware("http")
    async def db_session_middleware(request: Request, call_next):
        async with SessionLocal() as db:
            request.state.db = db
            response = await call_next(request)
        return response

    app.include_router(portfolio_api_router)
    app.include_router(floorsheet_api_router)

    @app.post("/")
    async def process_update(request: Request):
        if ptb is None:
            return Response(status_code=HTTPStatus.SERVICE_UNAVAILABLE)
        req = await request.json()
        update = Update.de_json(req, ptb.bot)
        await ptb.process_update(update)
        return Response(status_code=HTTPStatus.OK)

    @app.route("/webhook", methods=["GET", "POST"])
    async def webhook_handler(request: Request):
        if request.method == "GET":
            return Response(status_code=HTTPStatus.OK)
        form_data = await request.form()
        asyncio.create_task(whatsapp_message_handler(dict(form_data)))
        return Response(status_code=HTTPStatus.OK)

    return app


def create_web_app() -> FastAPI:
    app = FastAPI(title="Portfolio Viewer")
    app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
    templates = Jinja2Templates(directory=str(settings.templates_dir))

    @app.middleware("http")
    async def db_session_middleware(request: Request, call_next):
        async with SessionLocal() as db:
            request.state.db = db
            response = await call_next(request)
        return response

    app.include_router(portfolio_api_router)
    app.include_router(floorsheet_api_router)

    @app.get("/")
    async def root():
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

    @app.get("/portfolio/pools")
    async def portfolio_pools(request: Request):
        return templates.TemplateResponse("portfolio/pools.html", {"request": request})

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

    @app.get("/floorsheet")
    async def floorsheet_viewer(request: Request):
        return templates.TemplateResponse("floorsheet/viewer.html", {"request": request})

    return app
