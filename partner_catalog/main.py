"""HTTP boundary and persistence for a deliberately small catalog application."""

import hmac
import json
import logging
import re
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.security import APIKeyHeader
from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from partner_catalog.config import Settings
from partner_catalog.models import Base, Partner
from partner_catalog.schemas import PartnerCreate, PartnerPage, PartnerPatch, PartnerRead

logger = logging.getLogger("partner_catalog.http")
key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_environment()
    database_file = make_url(settings.database_url).database
    if database_file:
        Path(database_file).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _record):
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        engine.dispose()

    app = FastAPI(
        title="Partner Catalog API",
        version="1.0.0",
        description="Synthetic B2B partner catalog for local Python backend practice.",
        lifespan=lifespan,
    )
    app.state.engine = engine

    def authenticate(api_key: Annotated[str | None, Depends(key_header)]) -> None:
        supplied = api_key.encode() if api_key else b""
        if not hmac.compare_digest(supplied, settings.api_key.encode()):
            raise HTTPException(status_code=401, detail="invalid_api_key")

    def session() -> Iterator[Session]:
        with sessions() as database:
            yield database

    Database = Annotated[Session, Depends(session)]

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", incoming) else str(uuid4())
        started = perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "status": response.status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 3),
                }
            )
        )
        return response

    @app.get("/health", tags=["operations"])
    def health(database: Database) -> dict[str, str]:
        database.execute(text("SELECT 1"))
        return {"status": "ok"}

    def get_partner(database: Session, partner_id: UUID) -> Partner:
        partner = database.get(Partner, str(partner_id))
        if partner is None:
            raise HTTPException(status_code=404, detail="partner_not_found")
        return partner

    def commit(database: Session) -> None:
        try:
            database.commit()
        except IntegrityError:
            database.rollback()
            raise HTTPException(status_code=409, detail="partner_code_conflict") from None

    protected = [Depends(authenticate)]

    @app.post(
        "/v1/partners",
        response_model=PartnerRead,
        status_code=status.HTTP_201_CREATED,
        dependencies=protected,
        tags=["partners"],
    )
    def create_partner(payload: PartnerCreate, database: Database, response: Response) -> Partner:
        partner = Partner(
            id=str(uuid4()), created_at=datetime.now(UTC).isoformat(), **payload.model_dump()
        )
        database.add(partner)
        commit(database)
        response.headers["Location"] = f"/v1/partners/{partner.id}"
        return partner

    @app.get("/v1/partners", response_model=PartnerPage, dependencies=protected, tags=["partners"])
    def list_partners(
        database: Database,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        offset: Annotated[int, Query(ge=0)] = 0,
        active: bool | None = None,
    ) -> dict:
        query = select(Partner)
        if active is not None:
            query = query.where(Partner.active == active)
        total = database.scalar(select(func.count()).select_from(query.subquery()))
        items = database.scalars(
            query.order_by(Partner.code, Partner.id).limit(limit).offset(offset)
        )
        return {"items": list(items), "total": total, "limit": limit, "offset": offset}

    @app.get(
        "/v1/partners/{partner_id}",
        response_model=PartnerRead,
        dependencies=protected,
        tags=["partners"],
    )
    def read_partner(partner_id: UUID, database: Database) -> Partner:
        return get_partner(database, partner_id)

    @app.patch(
        "/v1/partners/{partner_id}",
        response_model=PartnerRead,
        dependencies=protected,
        tags=["partners"],
    )
    def update_partner(partner_id: UUID, payload: PartnerPatch, database: Database) -> Partner:
        partner = get_partner(database, partner_id)
        for name, value in payload.model_dump(exclude_unset=True).items():
            setattr(partner, name, value)
        commit(database)
        return partner

    @app.delete(
        "/v1/partners/{partner_id}", status_code=204, dependencies=protected, tags=["partners"]
    )
    def delete_partner(partner_id: UUID, database: Database) -> Response:
        database.delete(get_partner(database, partner_id))
        commit(database)
        return Response(status_code=204)

    return app
