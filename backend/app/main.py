from app.database.database import Base, engine
from app.api.api import (
    accounts_router,
    balance_router,
    beneficiaires_router,
    login_router,
    payment_request_router,
    ticket_router,
    transaction_router,
    user_router,
)
from app.database import models
from fastapi import FastAPI  # type: ignore

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title= "BankAI API",
    description= "Backend API for the banking operations platform",
    version= '0.1.0'
)


@app.get("/health")
def health_check():
    return{"status": "ok"}

app.include_router(login_router)
app.include_router(accounts_router)
app.include_router(balance_router)
app.include_router(transaction_router)
app.include_router(ticket_router)
app.include_router(user_router)
app.include_router(beneficiaires_router)
app.include_router(payment_request_router)