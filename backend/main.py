from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import Base, engine
from backend import models  # noqa: F401
from backend.routers import admin, approvals, auth, currency, expenses, ocr


app = FastAPI(title="Reimbursement Management API")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(expenses.router)
app.include_router(approvals.router)
app.include_router(admin.router)
app.include_router(currency.router)
app.include_router(ocr.router)


@app.get("/")
def health():
    return {"ok": True, "service": "reimbursement-api"}
