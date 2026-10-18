from agents import Agent, RunContextWrapper, function_tool

from app.agents.config import get_banking_model
from app.database.database import SessionLocal
from app.services.account_service import get_account_balance as read_account_balance


class BankingContext:
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id


@function_tool
def get_account_balance(ctx: RunContextWrapper[BankingContext]) -> str:
    """Read the authenticated customer's account balance from SQLite."""
    with SessionLocal() as db:
        balance = read_account_balance(db, ctx.context.user_id)

    if balance is None:
        return "No bank account is associated with your profile."
    return f"PKR {balance:,.2f}"


banking_agent = Agent(
    name="Banking Agent",
    instructions=(
        "You are a banking assistant. Your only banking operation is to retrieve "
        "the authenticated customer's account balance using get_account_balance. "
        "Call that tool when the customer asks about their balance. Report the "
        "returned amount exactly in PKR and do not invent or estimate balances. "
        "If no account is found, explain that clearly. For other requests, say "
        "you can currently help only with account balance inquiries."
    ),
    tools=[get_account_balance],
    model=get_banking_model(),
)