import bcrypt
from fastapi import HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from database import Token, datetime, User, Roles, Rights, roles_rights_relation, users_roles_relation, Advertisement


def hash_password(password: str) -> str:
    password = password.encode()
    password = bcrypt.hashpw(password, bcrypt.gensalt())
    return password.decode()


def check_password(
        password: str,
        hashed_password: str
) -> bool:
    return bcrypt.checkpw(password.encode(), hashed_password.encode())


async def check_relevance_token(
        token: str,
        session: AsyncSession
) -> Token:
    if not token:
        raise HTTPException(400, "Токен не передан - запрос отклонён")

    field_data = token.split()
    if len(field_data) != 2:
        raise HTTPException(400, "В заголовок не был передан"
                                 " префикс или значение токена")
    if field_data[0] not in ["Bearer", "JWT"]:
        raise HTTPException(400, f"Переданный префикс {field_data[0]} не поддерживается. "
                                 f"Используйте Bearer или JWT")

    stml = select(Token).where(Token.token == field_data[1])
    try:
        token: Token | None = await session.scalar(stml)
    except DBAPIError:
        raise HTTPException(400, "Для токена передано неверное значение")
    if not token:
        raise HTTPException(401, "Токен не существует")
    if datetime.now() > token.valid_until:
        raise HTTPException(401, "Токен устарел и больше не действителен")

    return token


async def check_authorization(
        token: Token,
        session: AsyncSession,
        user: User | None = None,
        advertisement: Advertisement | None = None
) -> bool:
    if user:
        request_right = Rights.id == 3 if user.id == token.user_id else Rights.id == 4
    else:
        if token.user_id == advertisement.author:
            request_right = or_(Rights.id == 3, Rights.id == 4)
        else:
            request_right = Rights.id == 4

    query = (
        select(func.count()).select_from(User)
        .join(users_roles_relation, User.id == users_roles_relation.c.user_id)
        .join(Roles, Roles.id == users_roles_relation.c.role_id)
        .join(roles_rights_relation, Roles.id == roles_rights_relation.c.role_id)
        .join(Rights, Rights.id == roles_rights_relation.c.right_id)
        .where(request_right)
    )
    result = await session.execute(query)
    count: int = result.scalar()
    return count > 0
