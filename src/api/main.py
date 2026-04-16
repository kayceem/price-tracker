from src.app.factories import create_api_app


app = create_api_app()

if __name__ == "__main__":
    import uvicorn
    from src.shared.config import settings

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
