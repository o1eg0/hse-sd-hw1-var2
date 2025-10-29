import uvicorn

from services.rental.core.config import HTTPBackendSettings

if __name__ == "__main__":
    config = {
        "app": "services.rental.app.app:create_app",
        "factory": True,
    }
    config.update(HTTPBackendSettings().model_dump())

    uvicorn.run(**config)
