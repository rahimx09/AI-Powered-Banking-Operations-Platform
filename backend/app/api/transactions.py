from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.dependencies import get_current_user, get_db
from app.database.models import Account, Transaction, User
from app.schemas.transaction import TransactionCreate, TransactionResponse

router = APIRouter()

@router.get("/transactions", response_model=list[TransactionResponse])
def get_transactions(
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(default=5, ge=1, le=100),
    db: Session = Depends(get_db),
):
    transactions = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Account.user_id == current_user.id)
        .order_by(Transaction.timestamp.desc())
        .limit(limit)
        .all()
    )

    if not transactions:
        raise HTTPException(
            status_code=404,
            detail="No transactions found for this user",
        )
    return transactions

@router.post('/transactions', response_model=TransactionResponse)
def create_transaction(
    data: TransactionCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TransactionResponse:
    account = (
        db.query(Account)
        .filter(Account.user_id == current_user.id)
        .order_by(Account.id)
        .first()
    )
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Create an account before creating transactions",
        )
    if account.status.lower() != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active",
        )

    amount = float(data.amount)
    balance_change = (
        Account.balance + amount
        if data.type == "credit"
        else Account.balance - amount
    )
    balance_update = db.query(Account).filter(
        Account.id == account.id,
        Account.user_id == current_user.id,
    )
    if data.type == "debit":
        balance_update = balance_update.filter(Account.balance >= amount)

    updated_rows = balance_update.update(
        {Account.balance: func.round(balance_change, 2)},
        synchronize_session=False,
    )
    if updated_rows != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance",
        )

    new_transaction = Transaction(
        account_id=account.id,
        amount=amount,
        type=data.type,
        description=data.description,
    )
    db.add(new_transaction)
    try:
        db.commit()
        db.refresh(new_transaction)
    except SQLAlchemyError:
        db.rollback()
        raise
    return new_transaction