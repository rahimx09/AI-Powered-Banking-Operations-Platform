from typing import Annotated
from app.database.dependencies import get_db, get_current_user
from app.database.models import User
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.services.account_service import get_account_balance

router = APIRouter()

@router.get("/account_balance", response_model=dict[str, float])
def account_balance(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, float]:
    balance = get_account_balance(db, current_user.id)
    if balance is None:
        raise HTTPException(
            status_code=404,
            detail="Account Not Found",
        )

    return {"balance": balance}