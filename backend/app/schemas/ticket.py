from pydantic import BaseModel, ConfigDict
from datetime import datetime


class TicketCreate(BaseModel):
    title: str
    description: str
    category: str
    priority: str


class TicketResponse(BaseModel):
    id: int
    title: str
    description: str
    category: str
    priority: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
