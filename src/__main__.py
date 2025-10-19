import uvicorn

from src.core.config import HTTPBackendSettings

if __name__ == "__main__":
    config = {
        "app": "src.app.app:create_app",
        "factory": True,
    }
    config.update(HTTPBackendSettings().model_dump())

    uvicorn.run(**config)
