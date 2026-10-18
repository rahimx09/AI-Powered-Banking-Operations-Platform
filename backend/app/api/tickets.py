from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.dependencies import get_current_user, get_db
from app.database.models import SupportTicket, User
from app.schemas.ticket import TicketCreate, TicketResponse


router = APIRouter()


@router.post("/ticket", response_model=TicketResponse)
def create_ticket(
    ticket: TicketCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SupportTicket:
    ticket_record = SupportTicket(
       user_id=current_user.id,
       title=ticket.title,
       description=ticket.description,
       category=ticket.category,
       priority=ticket.priority,
    )

    db.add(ticket_record)
    db.commit()
    db.refresh(ticket_record)
    return ticket_record


@router.get("/ticket/{ticket_id}", response_model=TicketResponse)
def get_ticket(
    ticket_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SupportTicket:
    ticket = (
       db.query(SupportTicket)
       .filter(
           SupportTicket.id == ticket_id,
           SupportTicket.user_id == current_user.id,
       )
       .first()
    )
    if ticket is None:
       raise HTTPException(
           status_code=status.HTTP_404_NOT_FOUND,
           detail="Ticket Not Found",
       )
    return ticket