from fastapi_users.manager import BaseUserManager  # noqa: I001
from fastapi_users import UUIDIDMixin
from app.models.users import User
from app.db.session import get_db as get_async_session
from typing import Optional
from fastapi import Depends
import uuid
from app.core.config import settings

SECRET = settings.SECRET


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(self, user: User, request=None):
        print(f"User {user.id} has registered.")


async def get_user_manager(session=Depends(get_async_session)):
    from fastapi_users.db import SQLAlchemyUserDatabase

    user_db = SQLAlchemyUserDatabase(session, User)
    yield UserManager(user_db)
