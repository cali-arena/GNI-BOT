#!/usr/bin/env python3
"""
Seed a user by email/password. Idempotent: if email exists, skip (or set password with --force).
Usage:
  python scripts/seed_user.py
  SEED_USER_EMAIL=admin@example.com SEED_USER_PASSWORD=secret python scripts/seed_user.py
  python scripts/seed_user.py --email admin@example.com --password secret [--force]
"""
import argparse
import os
import sys

# Repo root on path so we can run: python scripts/seed_user.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.api.db.session import get_db
from apps.api.db.models import User
from apps.api.auth import hash_password, verify_password


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed a user (email + password)")
    ap.add_argument("--email", default=os.environ.get("SEED_USER_EMAIL", ""), help="User email")
    ap.add_argument("--password", default=os.environ.get("SEED_USER_PASSWORD", ""), help="Password")
    ap.add_argument("--force", action="store_true", help="If user exists, update password")
    args = ap.parse_args()
    email = (args.email or "").strip().lower()
    password = (args.password or "").strip()
    if not email or not password:
        print("Error: email and password required (env SEED_USER_EMAIL, SEED_USER_PASSWORD or --email, --password)")
        sys.exit(1)
    with get_db() as session:
        user = session.query(User).filter(User.email == email).first()
        if user:
            if args.force:
                user.password_hash = hash_password(password)
                session.flush()
                print(f"Updated password for {email}")
            else:
                print(f"User {email} already exists (use --force to set password)")
            return
        user = User(email=email, password_hash=hash_password(password))
        session.add(user)
        session.flush()
        print(f"Created user {email} (id={user.id})")


if __name__ == "__main__":
    main()
