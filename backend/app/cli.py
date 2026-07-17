from __future__ import annotations

import argparse
import getpass

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import User


def create_admin(email: str, display_name: str, password: str) -> None:
    normalized_email = email.strip().lower()
    if len(password) < 12:
        raise SystemExit("管理员密码至少12位")
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == normalized_email))
        if existing:
            if existing.role != "admin":
                raise SystemExit("该邮箱已被非管理员账号占用")
            if existing.status != "active":
                existing.status = "active"
            existing.display_name = display_name.strip()
            existing.password_hash = hash_password(password)
            db.commit()
            print(f"管理员账号已更新：{normalized_email}")
            return
        db.add(
            User(
                email=normalized_email,
                password_hash=hash_password(password),
                role="admin",
                display_name=display_name.strip(),
                status="active",
            )
        )
        db.commit()
        print(f"管理员账号已创建：{normalized_email}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    admin_parser = subparsers.add_parser("create-admin", help="创建或重置平台管理员")
    admin_parser.add_argument("--email", required=True)
    admin_parser.add_argument("--display-name", default="平台管理员")
    admin_parser.add_argument("--password")
    args = parser.parse_args()

    if args.command == "create-admin":
        password = args.password or getpass.getpass("管理员密码：")
        create_admin(args.email, args.display_name, password)


if __name__ == "__main__":
    main()
