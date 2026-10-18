from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.dependencies import get_current_user, get_db
from app.database.models import Account, Beneficiary, Transaction, User
from app.schemas.payment_request import (
    PaymentRequestCreate,
    PaymentRequestResponse,
)

router = APIRouter()


@router.post(
    "/payment-requests",
    response_model=PaymentRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a payment to a saved beneficiary",
)
def payment_request(
    data: PaymentRequestCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PaymentRequestResponse:
    account = (
        db.query(Account)
        .filter(Account.user_id == current_user.id)
        .order_by(Account.id)
        .first()
    )
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account Not Found",
        )
    if account.status.lower() != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active",
        )

    beneficiary = (
        db.query(Beneficiary)
        .filter(
            Beneficiary.id == data.beneficiary_id,
            Beneficiary.user_id == current_user.id,
        )
        .first()
    )
    if beneficiary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Beneficiary Not Found",
        )
    if beneficiary.account_number == account.account_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payments to your own account are not allowed",
        )

    amount = float(data.amount)
    if amount > account.balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance",
        )

    # Keep the balance check and debit in one conditional database update so
    # concurrent requests cannot spend the same available balance twice.
    updated_rows = (
        db.query(Account)
        .filter(
            Account.id == account.id,
            Account.user_id == current_user.id,
            Account.balance >= amount,
        )
        .update(
            {Account.balance: func.round(Account.balance - amount, 2)},
            synchronize_session=False,
        )
    )
    if updated_rows != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance",
        )

    transaction = Transaction(
        account_id=account.id,
        amount=amount,
        type="debit",
        description=(
            f"Payment to {beneficiary.name}; "
            f"account {beneficiary.account_number}; "
            f"bank {beneficiary.bank_name}"
        ),
        status="completed",
    )
    db.add(transaction)

    try:
        db.commit()
        db.refresh(transaction)
        db.refresh(account)
    except SQLAlchemyError:
        db.rollback()
        raise

    return PaymentRequestResponse(
        transaction_id=transaction.id,
        amount=amount,
        beneficiary_name=beneficiary.name,
        beneficiary_account_number=beneficiary.account_number,
        beneficiary_bank_name=beneficiary.bank_name,
        timestamp=transaction.timestamp,
        status=transaction.status,
        remaining_balance=account.balance,
    )
