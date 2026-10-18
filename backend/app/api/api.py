from app.api.accounts import router as accounts_router
from app.api.transactions import router as transaction_router
from app.api.tickets import router as ticket_router
from app.api.users import router as user_router
from app.api.login import router as login_router
from app.api.balance import router as balance_router
from app.api.beneficiaries import router as beneficiaires_router
from app.api.payment_request import router as payment_request_router

__all__ = [
    'accounts_router',
    'transaction_router',
    'ticket_router',
    'user_router',
    'login_router',
    'balance_router',
    'beneficiaires_router',
    'payment_request_router',
]