# scripts/cleanup_active.py
"""
Clear is_active flag for users whose last_login is older than a threshold.

Usage:
    python3 scripts/cleanup_active.py --hours 2

Will set is_active = False for users with last_login older than now - hours.
"""
import sys
import os
import argparse
from datetime import datetime, timedelta
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from database.database import SessionLocal
from models.user import User


def cleanup(hours: int = 2):
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        users = db.query(User).filter(User.is_active == True).all()
        changed = 0
        for u in users:
            if not u.last_login or u.last_login < cutoff:
                u.is_active = False
                db.add(u)
                changed += 1
        db.commit()
        print(f"Cleared is_active for {changed} users (cutoff {cutoff.isoformat()})")
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--hours', type=int, default=2, help='hours of inactivity to clear')
    args = parser.parse_args()
    cleanup(args.hours)
