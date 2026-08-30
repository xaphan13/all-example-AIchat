import uuid

from fastapi import Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
    JWTStrategy,
)

from app.core.config import settings
from app.models.users import User
from app.schemas.users import UserCreate, UserRead, UserUpdate
from app.services.user_manager import get_user_manager

SECRET = settings.SECRET


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)


# JWT authentication for API
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")
jwt_auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# Cookie authentication for web browser
cookie_transport = CookieTransport(cookie_max_age=3600)
cookie_auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [jwt_auth_backend, cookie_auth_backend],
)

# Routers for authentication methods
login_router = fastapi_users.get_auth_router(cookie_auth_backend)
users_router = fastapi_users.get_users_router(UserRead, UserUpdate)
register_router = fastapi_users.get_register_router(UserRead, UserCreate)

current_user = fastapi_users.current_user()
