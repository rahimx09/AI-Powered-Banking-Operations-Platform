from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.auth import create_access_token, verify_password
from app.database.dependencies import get_db, get_current_user
from app.database.models import User
from app.schemas.auth import Token, UserPublic

router = APIRouter()


@router.post("/login", response_model=Token)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)]
) -> Token:
    user = db.query(User).filter(User.email == form_data.username).first()

    if user is None or not verify_password(
        form_data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(str(user.id))

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }

@router.get("/me", response_model=UserPublic)
def read_current_user(
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
):
    return current_user

    