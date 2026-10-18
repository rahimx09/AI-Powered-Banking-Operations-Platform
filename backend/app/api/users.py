from typing import Annotated

from app.schemas.user import UserCreate, UserResponse
from app.database.models import User
from app.database.dependencies import get_current_user, get_db
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.api.auth import hash_password

router = APIRouter()

@router.post('/create_user', response_model=UserResponse)
def create_user(data: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    new_user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password)
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A user with this email already exists"
        ) from exc
    db.refresh(new_user)
    return new_user

@router.get('/create_user/{user_id}', response_model=UserResponse)
def get_user_by_id(user_id: int,
                   _current_user: Annotated[User, Depends(get_current_user)],
                   db: Session = Depends(get_db)) -> UserResponse | None:
    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User Not Found"
        )
    return user

@router.get('/create_user/email/{email}', response_model=UserResponse)
def get_user_by_email(email: str,
                   _current_user: Annotated[User, Depends(get_current_user)],
                   db: Session = Depends(get_db)) -> UserResponse | None:
    user = db.query(User).filter(User.email == email).first()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User Not Found"
        )
    return user
