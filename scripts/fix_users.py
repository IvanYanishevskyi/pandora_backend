# scripts/fix_users.py
"""
Utility to adjust existing users after changing model defaults:
- Set is_active to 0 for all existing users (if desired)
- Optionally set last_login for a specific username

Usage:
    python3 scripts/fix_users.py --deactivate-all
    python3 scripts/fix_users.py --set-last-login username
"""
import sys
import os
import argparse
from datetime import datetime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database.database import SessionLocal
from models.user import User

def deactivate_all():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        for u in users:
            u.is_active = False
            db.add(u)
        db.commit()
        print(f"Updated {len(users)} users: is_active=False")
    finally:
        db.close()

def set_last_login(username: str):
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == username).first()
        if not u:
            print("User not found")
            return
        u.last_login = datetime.utcnow()
        db.add(u)
        db.commit()
        print(f"Set last_login for {username}")
    finally:
        db.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--deactivate-all', action='store_true')
    parser.add_argument('--set-last-login', type=str, help='username')
    args = parser.parse_args()

    if args.deactivate_all:
        deactivate_all()
    elif args.set_last_login:
        set_last_login(args.set_last_login)
    else:
        parser.print_help()
