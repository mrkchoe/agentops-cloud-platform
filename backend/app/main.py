from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_router
from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.seed import seed_demo


def create_app() -> FastAPI:
    app = FastAPI(
        title="agentops-cloud-platform",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    return app


app = create_app()


@app.on_event("startup")
def _startup() -> None:
    init_db()
    if settings.seed_demo:
        db = SessionLocal()
        try:
            seed_demo(db)
        finally:
            db.close()

