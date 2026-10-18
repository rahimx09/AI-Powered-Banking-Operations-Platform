from sqlalchemy.orm import Session

from app.database.models import Account


def get_account_balance(db: Session, user_id: int) -> float | None:
    """Return the balance belonging to one authenticated user."""
    account = db.query(Account).filter(Account.user_id == user_id).first()
    if account is None:
        return None
    return account.balance