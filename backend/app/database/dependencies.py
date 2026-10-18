from typing import Annotated

from fastapi import Depends, HTTPException, status
from app.database.database import SessionLocal
from app.api.auth import oauth2_scheme, verify_access_token
from sqlalchemy.orm import Session
from app.database.models import User, Account


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = verify_access_token(token)
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject.isdecimal():
            raise credentials_exception
        user_id = int(subject)
    except (TypeError, ValueError):
        raise credentials_exception from None

    user = db.get(User, user_id)

    if user is None:
        raise credentials_exception

    return user

def get_current_user_account(current_user: User,
                     db: Annotated[Session, Depends(get_db)]) -> Account:
    account = db.query(Account).filter(Account.user_id == current_user.id).first()
    if account is None:
        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Account Not Found",
    )

    return account
