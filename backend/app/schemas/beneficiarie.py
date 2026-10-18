from pydantic import BaseModel, ConfigDict


class response_beneficiaries(BaseModel):
    id: int
    name: str
    account_number: str
    bank_name: str

    model_config = ConfigDict(from_attributes=True)


class create_beneficiaires(BaseModel):
    name: str
    account_number: str
    bank_name: str

