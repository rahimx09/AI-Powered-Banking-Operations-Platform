from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PaymentRequestCreate(BaseModel):
    beneficiary_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class PaymentRequestResponse(BaseModel):
    transaction_id: int
    amount: float
    beneficiary_name: str
    beneficiary_account_number: str
    beneficiary_bank_name: str
    timestamp: datetime
    status: str
    remaining_balance: float
