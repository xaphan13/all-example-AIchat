from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(SQLAlchemyBaseUserTableUUID, Base):
    full_name: Mapped[str] = mapped_column(String(length=100))
    email: Mapped[str] = mapped_column(String(length=100), unique=True, nullable=False)
