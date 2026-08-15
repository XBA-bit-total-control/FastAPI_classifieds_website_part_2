import os
import uuid
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import Integer, String, DateTime, Numeric, ForeignKey, Uuid, Boolean, Table, Column
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, MappedColumn, Mapped, relationship
from sqlalchemy.sql import func


load_dotenv()

DNS = (f"{os.getenv("POSTGRES_DRIVER")}://{os.getenv("POSTGRES_USER")}:"
       f"{os.getenv("POSTGRES_PASSWORD")}@{os.getenv("POSTGRES_HOST")}:"
       f"{os.getenv("POSTGRES_PORT")}/{os.getenv("POSTGRES_DB")}")

engine = create_async_engine(DNS)
Session = async_sessionmaker(bind=engine, expire_on_commit=False)


def create_an_end_date() -> datetime:
    """
    Функция создает дату окончания для токена
    на 48 часов больше текущего времени
    """
    date = datetime.now()
    date = date.timestamp() + 172800
    return datetime.fromtimestamp(date)


class Base(DeclarativeBase, AsyncAttrs):
    id: Mapped[int] = MappedColumn(Integer, primary_key=True)


users_roles_relation = Table(
    "users_roles_relation",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True)
)

roles_rights_relation = Table(
    "roles_rights_relation",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
    Column("right_id", Integer, ForeignKey("rights.id"), primary_key=True)
)


class Rights(Base):
    __tablename__ = "rights"

    read: Mapped[bool] = MappedColumn(Boolean, default=True, nullable=False)
    write: Mapped[bool] = MappedColumn(Boolean, default=False, nullable=False)
    only_own: Mapped[bool] = MappedColumn(Boolean, default=True, nullable=False)


class Roles(Base):
    __tablename__ = "roles"

    name: Mapped[str] = MappedColumn(String(255), nullable=False)
    rights: Mapped[Rights] = relationship(
        secondary=roles_rights_relation,
        lazy="joined"
    )


class User(Base):
    __tablename__ = "users"

    name: Mapped[str] = MappedColumn(String(205), unique=True, nullable=False)
    password: Mapped[str] = MappedColumn(String(72), nullable=False)
    tokens: Mapped[list["Token"]] = relationship(
        "Token",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="joined"
    )
    role: Mapped[Roles] = relationship(
        secondary=users_roles_relation,
        lazy="joined"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name
        }


class Token(Base):
    __tablename__ = "tokens"

    token: Mapped[uuid.UUID] = MappedColumn(Uuid, default=func.gen_random_uuid(), unique=True, nullable=False)
    valid_until: Mapped[datetime] = MappedColumn(DateTime, default=create_an_end_date, nullable=False)
    user: Mapped[User] = relationship(
        User,
        back_populates="tokens",
        lazy="joined"
    )
    user_id: Mapped[int] = MappedColumn(ForeignKey("users.id"))


class Advertisement(Base):
    __tablename__ = 'advertisements'

    title: Mapped[str] = MappedColumn(String(200), nullable=False)
    description: Mapped[str] = MappedColumn(String(600), nullable=False)
    price: Mapped[float] = MappedColumn(Numeric(precision=11, scale=2), nullable=False)
    author: Mapped[str] = MappedColumn(ForeignKey("users.id"))
    created_at: Mapped[datetime] = MappedColumn(DateTime, default=func.now(), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'price': self.price,
            'author': self.author,
            'created_at': self.created_at.isoformat()
        }


async def open_orm():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_orm():
    await engine.dispose()
