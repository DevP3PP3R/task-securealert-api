from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from database import create_table, get_events, insert_event
from schemas import EventCreate, EventType, Severity

from typing import Annotated

from datetime import datetime


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_table()
    yield


app = FastAPI(
    title="SecureAlert API",
    lifespan=lifespan,
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    return JSONResponse(
        status_code=400, # Rule: return 400 instead of FastAPI's default 422 for validation errors
        content=jsonable_encoder({"detail": exc.errors()}),
    )


@app.get("/")
def read_root():
    return {"message": "SecureAlert API is running"}

@app.post("/events", status_code=201)
def create_event(event: EventCreate):
    event_id = insert_event(event)

    return {
        "id": event_id,
        **event.model_dump(),
    }

@app.get("/events")
def read_events(
    device_id: Annotated[
        str | None,
        Query(min_length=3, max_length=64),
    ] = None,
    severity: Severity | None = None,
    event_type: EventType | None = None,
    from_: Annotated[
        datetime | None,
        Query(alias="from"),
    ] = None,
    to: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return get_events(
        device_id=device_id,
        severity=severity,
        event_type=event_type,
        from_=from_,
        to=to,
        page=page,
        page_size=page_size,
    )