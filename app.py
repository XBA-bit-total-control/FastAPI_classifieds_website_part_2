from datetime import datetime

from fastapi import FastAPI, HTTPException, Response, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from authentication import hash_password, check_password, check_relevance_token, check_authorization
from database import Session, Advertisement, User, Token, Roles
from schemas import AdvertisementsPostInp, AdvertisementsPatchInp, UsersPostInp, UsersPatchInp, LoginInp


app = FastAPI(
    title="Service buy-and-sell Buyalliti",
    description="A service for convenient sale and purchase of all sorts of things",
    version="1.0.0"
)


async def async_session():
    async with Session() as session:
        yield session


async def role_user(
        session: AsyncSession = Depends(async_session)
) -> Roles:
    """
    Функция для получения роли обычного пользователя
    """
    stml = select(Roles).where(Roles.name == "user")
    role = await session.scalar(stml)
    if role is None:
        raise AssertionError("Роли не были созданы - проверьте запуск миграции")

    return role


async def get_user(
        user_id: int,
        session: AsyncSession
) -> User:
    """
    Вынесенная функция для получения пользователя по id
    """
    stml = select(User).where(User.id == user_id)
    user = await session.scalar(stml)
    if not user:
        raise HTTPException(404,
                            f"Пользователь с id = {user_id} отсутствует")

    return user


async def check_existence_user_by_name(
        name: str,
        session: AsyncSession = Depends(async_session)
) -> None:
    """
    Проверка существования пользователя по его имени
    """
    stml = select(User).where(User.name == name)
    user = await session.scalar(stml)
    if user:
        raise HTTPException(400, f"Имя {name} уже занято")


@app.post(
    path="/login",
    summary="Получить токен"
)
async def login(
        request_data: LoginInp,
        session: AsyncSession = Depends(async_session)
):
    stml = select(User).where(User.name == request_data.name)
    user = await session.scalar(stml)
    if not user:
        raise HTTPException(401, "Предоставлен несуществующий логин")
    if not check_password(request_data.password, user.password):
        raise HTTPException(401, "Предоставлен неверный пароль")

    token = Token(
        user=user,
        user_id=user.id
    )
    session.add(token)
    await session.commit()

    return {"token": token.token}


@app.get(
    path="/user/{user_id}",
    summary="Получить пользователя по его id"
)
async def get_user_by_id(
        user_id: int,
        session: AsyncSession = Depends(async_session)
):
    user = await get_user(user_id, session)
    return user.to_dict()


@app.post(
    path="/user",
    summary="Создать пользователя",
    status_code=201
)
async def create_user(
        request_data: UsersPostInp,
        session: AsyncSession = Depends(async_session)
):
    await check_existence_user_by_name(request_data.name, session)
    user = User(
        name=request_data.name,
        password=hash_password(request_data.password),
        role=await role_user(session)
    )
    session.add(user)
    await session.commit()

    return user.to_dict()


@app.patch(
    path="/user/{user_id}",
    summary="Изменить данные пользователя"
)
async def change_user(
        user_id: int,
        request_data: UsersPatchInp,
        token: str = Header(alias="Authorization"),
        session: AsyncSession = Depends(async_session)
):
    user: User = await get_user(user_id, session)
    token_activity: Token = await check_relevance_token(token, session)
    authorization: bool = await check_authorization(token_activity, session, user)

    if not authorization:
        raise HTTPException(403, "У вас нет прав на выполнение операции")

    request_data = dict(request_data)
    name = request_data.get("name")
    password = request_data.get("password")

    if name is None and password is None:
        raise HTTPException(400,
                            "В запросе отсутствуют данные для изменения")
    if name:
        await check_existence_user_by_name(name, session)
        user.name = name
    if password:
        user.password = hash_password(password)
    await session.commit()

    return user.to_dict()


@app.delete(
    path="/user/{user_id}",
    summary="Удалить пользователя"
)
async def delete_user(
        user_id: int,
        token: str = Header(alias="Authorization"),
        session: AsyncSession = Depends(async_session)
) -> Response:
    user = await get_user(user_id, session)
    token_activity: Token = await check_relevance_token(token, session)
    authorization: bool = await check_authorization(token_activity, session, user)

    if not authorization:
        raise HTTPException(403, "У вас нет прав на выполнение операции")

    await session.delete(user)
    await session.commit()

    return Response(status_code=204)


@app.get(
    path="/advertisement/{advertisement_id}",
    summary="Получить объявление по id"
)
async def get_advertisement_by_id(
        advertisement_id: int,
        session: AsyncSession = Depends(async_session)
):
    stml = select(Advertisement).where(Advertisement.id == advertisement_id)
    advertisement = await session.scalar(stml)
    if advertisement:
        return advertisement.to_dict()
    else:
        raise HTTPException(404,
                            f"Объявление с id = {advertisement_id} не существует")


@app.get(
    path="/advertisement",
    summary="Получение объявлений по переданным полям"
)
async def get_advertisements_by_fields(
        title: str = None,
        description: str = None,
        price: float = None,
        price_more: float = None,
        price_less: float = None,
        author: int = None,
        created_at: str = None,
        created_before: str = None,
        created_after: str = None,
        session: AsyncSession = Depends(async_session)
):
    stml = select(Advertisement)
    if title:
        stml = stml.where(Advertisement.title.ilike(f"%{title}%"))

    if description:
        stml = stml.where(Advertisement.description.ilike(f"%{description}%"))

    if price:
        if price < 0:
            raise HTTPException(400, "Стоимость не может быть отрицательной")
        stml = stml.where(Advertisement.price == price)
        if price_more or price_less:
            raise HTTPException(400,
                                f"Можно назначить точную стоимость или диапазон, но не все вместе")
    else:
        if price_less and price_more:
            if price_more > price_less:
                raise HTTPException(400, "Диапазон поиска стоимости назначен не не корректно")
        if price_more:
            if price_more < 0:
                raise HTTPException(400, "Стоимость не может быть отрицательной")
            stml = stml.where(Advertisement.price > price_more)
        if price_less:
            if price_less < 0:
                raise HTTPException(400, "Стоимость не может быть отрицательной")
            stml = stml.where(Advertisement.price < price_less)

    if author:
        stml = stml.where(Advertisement.author == author)

    try:
        if created_at:
            stml = stml.where(Advertisement.created_at == datetime.fromisoformat(created_at))
            if created_before or created_after:
                raise HTTPException(400,
                                    f"Можно задать точную дату создания или диапазон, но не все вместе")
        else:
            if created_before:
                stml = stml.where(Advertisement.created_at <= datetime.fromisoformat(created_before))
            if created_after:
                stml = stml.where(Advertisement.created_at >= datetime.fromisoformat(created_after))
    except ValueError:
        raise HTTPException(400,
                            f"Значение для времени указанно не верно - придерживайтесь формата YYYY-MM-DD")

    advertisements = await session.scalars(stml)
    result = [advertisement.to_dict() for advertisement in advertisements]
    if result:
        return result
    else:
        raise HTTPException(404, f"Объявлений с такими параметрами не найдено")


@app.post(
    path="/advertisement",
    summary="Создать объявление",
    status_code=201
)
async def create_advertisement(
        request_data: AdvertisementsPostInp,
        token: str = Header(alias="Authorization"),
        session: AsyncSession = Depends(async_session)
):
    token_activity: Token = await check_relevance_token(token, session)

    advertisement = Advertisement(
        title=request_data.title,
        description=request_data.description,
        price=request_data.price,
        author=token_activity.user_id
    )
    session.add(advertisement)
    await session.commit()

    return advertisement.to_dict()


@app.patch(
    path="/advertisement/{advertisement_id}",
    summary="Внести изменение в объявление",
    status_code=200
)
async def change_advertisement(
        advertisement_id: int,
        request_data: AdvertisementsPatchInp,
        token: str = Header(alias="Authorization"),
        session: AsyncSession = Depends(async_session)
):
    stml = select(Advertisement).where(Advertisement.id == advertisement_id)
    advertisement: Advertisement = await session.scalar(stml)
    if not advertisement:
        raise HTTPException(404,
                            f"Объявления с id = {advertisement_id} не создано")

    token_activity: Token = await check_relevance_token(token, session)
    authorization: bool = await check_authorization(token_activity, session, advertisement=advertisement)

    if not authorization:
        raise HTTPException(403, "У вас нет прав на выполнение операции")

    request_data = dict(request_data)
    title = request_data.get('title')
    description = request_data.get('description')
    price = request_data.get('price')

    if title:
        advertisement.title = title
    if description:
        advertisement.description = description
    if price:
        advertisement.price = price
    await session.commit()

    return advertisement.to_dict()


@app.delete(
    "/advertisement/{advertisement_id}",
    summary="Удалить объявление"
)
async def delete_advertisement(
        advertisement_id: int,
        token: str = Header(alias="Authorization"),
        session: AsyncSession = Depends(async_session)
):
    stml = select(Advertisement).where(Advertisement.id == advertisement_id)
    advertisement = await session.scalar(stml)
    if not advertisement:
        raise HTTPException(404,
                            f"Объявление с id = {advertisement_id} не существует")

    token_activity: Token = await check_relevance_token(token, session)
    authorization: bool = await check_authorization(token_activity, session, advertisement=advertisement)

    if not authorization:
        raise HTTPException(403, "У вас нет прав на выполнение операции")

    await session.delete(advertisement)
    await session.commit()

    return Response(status_code=204)
