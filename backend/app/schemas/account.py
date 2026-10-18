from pydantic import BaseModel, ConfigDict, Field


class AccountCreate(BaseModel):
    account_type: str = Field(min_length=1, max_length=50)

    model_config = ConfigDict(str_strip_whitespace=True)


class AccountResponse(BaseModel):
    account_number: str
    account_type: str
    balance: float
    status: str

    model_config = ConfigDict(from_attributes= True)
