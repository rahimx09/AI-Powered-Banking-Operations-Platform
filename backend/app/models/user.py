from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String

from app.database.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    role: Mapped[str] = mapped_column(
        String(50),
        default= "Customer",
        nullable=False
    )

    accounts = relationship(
        "Account",
        back_populates="user"
    )

    beneficiaries = relationship(
        "Beneficiary",
        back_populates="user"
    )

    support_tickets = relationship(
        "SupportTicket",
        back_populates="user"
    )

