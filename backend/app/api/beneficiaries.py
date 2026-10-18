from typing import Annotated

from app.database.dependencies import get_db, get_current_user
from app.database.models import Account, User, Beneficiary
from app.schemas.beneficiarie import response_beneficiaries, create_beneficiaires
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

router = APIRouter()

@router.post('/beneficiaries', response_model=response_beneficiaries)
def create_beneficiaries(
    data: create_beneficiaires,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
                        ) -> response_beneficiaries:
    account = db.query(Account.id).filter(Account.user_id == current_user.id).first()
    if account is None:
        raise HTTPException(
            status_code=404,
            detail="Account Not Found"
        )

    existing_bene = db.query(Beneficiary).filter(Beneficiary.account_number == data.account_number).first()
    if existing_bene is not None:
        raise HTTPException(
            status_code=409,
            detail="Beneficiary already exists"
        )
    new_bene = Beneficiary(
        user_id = current_user.id,
        name = data.name,
        account_number = data.account_number,
        bank_name = data.bank_name
    )
    db.add(new_bene)
    db.commit()
    db.refresh(new_bene)

    return new_bene

@router.get('/beneficiaries', response_model=list[response_beneficiaries])
def get_beneficiaries(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]   
) -> list[response_beneficiaries]:
    bene = db.query(Beneficiary).filter(Beneficiary.user_id == current_user.id).all()
    if not bene:
        raise HTTPException(
            status_code= 404,
            detail= "Beneficiaries Not Found"
        )
    return bene

@router.get('/beneficiaries/{name}', response_model=list[response_beneficiaries])
def get_beneficiaries_by_name(
    name: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]   
) -> list[response_beneficiaries]:
    bene = db.query(Beneficiary).filter(Beneficiary.name == name,
                                        Beneficiary.user_id == current_user.id).all()
    if not bene:
        raise HTTPException(
            status_code= 404,
            detail= "Beneficiaries Not Found"
        )
    return bene


