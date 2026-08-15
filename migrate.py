import asyncio

from database import open_orm, close_orm, Roles, Rights, Session


async def main():
    await open_orm()
    async with Session() as session:
        read_only_own = Rights(read=True, write=False, only_own=True)
        read_all = Rights(read=True, write=False, only_own=False)
        read_write_only_own = Rights(read=True, write=True, only_own=True)
        read_write_all = Rights(read=True, write=True, only_own=False)

        user = Roles(name="user", rights=read_write_only_own)
        admin = Roles(name="admin", rights=read_write_all)

        session.add_all([
            read_only_own,
            read_all,
            read_write_only_own,
            read_write_all,
            user,
            admin
        ])
        await session.commit()
    await close_orm()


try:
    asyncio.run(main())
    print("The tables have been successfully created\n"
          "Roles and rights to them have been created")
except Exception as err:
    print(f"Tables were not created due to an error {err.__class__.__name__}")
    raise err
