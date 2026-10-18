from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TransactionResponse(BaseModel):
    amount: float
    type: str
    description: str | None
    timestamp: datetime
    status: str

    model_config = ConfigDict(from_attributes= True)


class TransactionCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    type: Literal["credit", "debit"]
    description: str | None

