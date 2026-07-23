import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents_registry.registry import AgentRegistry
from app.api.routes import router
from app.config import get_settings
from app.db.session import build_session_factory
from app.orchestrator.service import sync_agent_defs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    app.state.session_factory = build_session_factory(settings.database_url)

    registry = AgentRegistry()
    registry.load()
    for failure in registry.failures:
        logger.warning("Agent excluded: %s — %s", failure.agent_dir, failure.reason)
    app.state.registry = registry

    session = app.state.session_factory()
    try:
        sync_agent_defs(session, registry.list_agents())
    finally:
        session.close()

    yield


app = FastAPI(title="PP-SDLC-Orchestrator", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
