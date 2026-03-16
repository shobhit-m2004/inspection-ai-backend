from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from app.api.router import api_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.on_event('startup')
def startup_event() -> None:
    try:
        Base.metadata.create_all(bind=engine)
    except OperationalError as exc:
        raise RuntimeError(
            'Database connection failed. Set backend/.env -> DATABASE_URL with valid '
            'PostgreSQL credentials, e.g. '
            '"postgresql+psycopg://postgres:<your_password>@localhost:5432/sop_gap".'
        ) from exc


@app.get('/health')
def health_check() -> dict[str, str]:
    return {'status': 'ok'}


app.include_router(api_router, prefix=settings.api_prefix)
