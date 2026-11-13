"""FastAPI entry point.  Run:  uvicorn app.main:app --reload  (from backend/)."""
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .db import Base, engine
from .routers import bookings, catalog, requests, suppliers
from .rules import RuleViolation

app = FastAPI(title="Airport Taxi - Ride Offers")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"), "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(engine)


# Every error response has the same shape: {"errors": [{"rule": "...", "message": "..."}]}
@app.exception_handler(RuleViolation)
def rule_violation_handler(_: Request, exc: RuleViolation):
    return JSONResponse(status_code=exc.status_code, content={"errors": [e.to_dict() for e in exc.errors]})


@app.exception_handler(RequestValidationError)
def validation_handler(_: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err["loc"] if p != "body")
        errors.append({"rule": "INPUT", "message": f"{field or 'body'}: {err['msg']}"})
    return JSONResponse(status_code=422, content={"errors": errors})


app.include_router(catalog.router, prefix="/api")
app.include_router(requests.router, prefix="/api")
app.include_router(suppliers.router, prefix="/api")
app.include_router(bookings.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}
