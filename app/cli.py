import argparse
import asyncio

from sqlalchemy import select

from app.auth.models import User
from app.auth.services import hash_password
from app.database import async_session


async def create_user(username: str, password: str) -> None:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none():
            print(f"User '{username}' already exists.")
            return
        user = User(username=username, password_hash=hash_password(password))
        session.add(user)
        await session.commit()
        print(f"User '{username}' created successfully.")


def main():
    parser = argparse.ArgumentParser(description="AI Job Tracker CLI")
    subparsers = parser.add_subparsers(dest="command")

    create_cmd = subparsers.add_parser("create-user")
    create_cmd.add_argument("--username", required=True)
    create_cmd.add_argument("--password", required=True)

    args = parser.parse_args()

    if args.command == "create-user":
        asyncio.run(create_user(args.username, args.password))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
