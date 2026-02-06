from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import require_auth
from apps.api.db import init_db
from middleware import RateLimitMiddleware, RequestIdMiddleware, RequestSizeLimitMiddleware
from routes.admin import router as admin_router
from routes.auth_routes import router as auth_router
from routes.control import router as control_router
from routes.dlq import router as dlq_router
from routes.health import router as health_router
from routes.metrics import router as metrics_router
from routes.review import router as review_router
from routes.sources import router as sources_router
from routes.wa_bridge import router as wa_bridge_router
from routes.whatsapp_user import router as whatsapp_user_router

from apps.shared.config import ConfigError, validate_config
from apps.shared.env_validation import EnvValidationError, validate_env
from apps.shared.secrets import get_secret

_CORS_ORIGINS = [
    o.strip() for o in (get_secret("CORS_ALLOWED_ORIGINS") or "").split(",") if o.strip()
]
_streamlit_origin = (get_secret("STREAMLIT_ORIGIN") or "").strip()
if _streamlit_origin:
    _CORS_ORIGINS = [*_CORS_ORIGINS, _streamlit_origin]


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        validate_env(role="api")
    except (ConfigError, EnvValidationError) as e:
        import logging
        logging.getLogger(__name__).error("Startup env validation failed: %s", e)
        raise
    init_db()
    yield
    # Shutdown: Uvicorn handles SIGTERM; stop accepting new requests, drain in-flight


app = FastAPI(title="gni-bot-creator API", lifespan=lifespan)

app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS if _CORS_ORIGINS else [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "X-API-Key", "Content-Type"],
)

app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(admin_router)
app.include_router(wa_bridge_router)
app.include_router(whatsapp_user_router)
app.include_router(auth_router)
app.include_router(control_router, dependencies=[Depends(require_auth)])
app.include_router(dlq_router, dependencies=[Depends(require_auth)])
app.include_router(sources_router, dependencies=[Depends(require_auth)])
app.include_router(review_router, dependencies=[Depends(require_auth)])
