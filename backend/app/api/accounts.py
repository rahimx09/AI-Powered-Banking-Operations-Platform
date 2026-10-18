import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.dependencies import get_current_user, get_db
from app.database.models import Account, User
from app.schemas.account import AccountCreate, AccountResponse

router = APIRouter()


def _generate_account_number(db: Session) -> str:
    for _ in range(10):
        account_number = f"{secrets.randbelow(10**12):012d}"
        existing_account = db.query(Account).filter(
            Account.account_number == account_number
        ).first()
        if existing_account is None:
            return account_number

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Unable to generate an account number. Please try again.",
    )


@router.post(
    "/accounts",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_account(
    data: AccountCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AccountResponse:
    account_type = data.account_type.strip()
    if not account_type:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Account type must not be empty",
        )

    existing_account = (
        db.query(Account.id)
        .filter(Account.user_id == current_user.id)
        .first()
    )
    if existing_account is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already has an account",
        )

    account = Account(
        user_id=current_user.id,
        account_number=_generate_account_number(db),
        account_type=account_type,
        balance=0.0,
        status="Active",
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("/accounts", response_model=list[AccountResponse])
def get_account_details(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AccountResponse]:
    accounts = (
        db.query(Account)
        .filter(Account.user_id == current_user.id)
        .all()
    )

    if not accounts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account Not Found",
        )

    return accounts
