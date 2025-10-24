# scripts/manage_admin_token.py
"""
Utility to manage admin tokens:
- List all tokens
- Update expiration date
- Make token permanent (remove expiration)
- Deactivate token

Usage:
    python3 scripts/manage_admin_token.py --list
    python3 scripts/manage_admin_token.py --make-permanent --token-id 1
    python3 scripts/manage_admin_token.py --extend-days 365 --token-id 1
    python3 scripts/manage_admin_token.py --deactivate --token-id 1
"""
import sys
import os
import argparse
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.database import SessionLocalAdmin
from models.admin_token import AdminToken


def list_tokens():
    db = SessionLocalAdmin()
    try:
        tokens = db.query(AdminToken).all()
        print('\n=== Admin Tokens ===\n')
        for t in tokens:
            status = "✅ Active" if t.active else "❌ Inactive"
            expires = "Never" if not t.expires_at else t.expires_at.isoformat()
            expired = ""
            if t.expires_at and t.expires_at < datetime.utcnow():
                expired = " ⚠️ EXPIRED"
            
            print(f'ID: {t.id} {status}{expired}')
            print(f'  Name: {t.name}')
            print(f'  Token: {t.token}')
            print(f'  Expires: {expires}')
            print(f'  Created by: {t.created_by}')
            print(f'  Last used: {t.last_used or "Never"}')
            print()
    finally:
        db.close()


def make_permanent(token_id: int):
    db = SessionLocalAdmin()
    try:
        token = db.query(AdminToken).filter(AdminToken.id == token_id).first()
        if not token:
            print(f"❌ Token with ID {token_id} not found")
            return
        
        token.expires_at = None
        db.add(token)
        db.commit()
        print(f"✅ Token '{token.name}' is now permanent (no expiration)")
    finally:
        db.close()


def extend_expiration(token_id: int, days: int):
    db = SessionLocalAdmin()
    try:
        token = db.query(AdminToken).filter(AdminToken.id == token_id).first()
        if not token:
            print(f"❌ Token with ID {token_id} not found")
            return
        
        new_expiration = datetime.utcnow() + timedelta(days=days)
        token.expires_at = new_expiration
        db.add(token)
        db.commit()
        print(f"✅ Token '{token.name}' expiration extended to {new_expiration.isoformat()}")
    finally:
        db.close()


def deactivate_token(token_id: int):
    db = SessionLocalAdmin()
    try:
        token = db.query(AdminToken).filter(AdminToken.id == token_id).first()
        if not token:
            print(f"❌ Token with ID {token_id} not found")
            return
        
        token.active = False
        db.add(token)
        db.commit()
        print(f"✅ Token '{token.name}' deactivated")
    finally:
        db.close()


def activate_token(token_id: int):
    db = SessionLocalAdmin()
    try:
        token = db.query(AdminToken).filter(AdminToken.id == token_id).first()
        if not token:
            print(f"❌ Token with ID {token_id} not found")
            return
        
        token.active = True
        db.add(token)
        db.commit()
        print(f"✅ Token '{token.name}' activated")
    finally:
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Manage admin tokens')
    parser.add_argument('--list', action='store_true', help='List all tokens')
    parser.add_argument('--token-id', type=int, help='Token ID to modify')
    parser.add_argument('--make-permanent', action='store_true', help='Remove expiration date')
    parser.add_argument('--extend-days', type=int, help='Extend expiration by N days from now')
    parser.add_argument('--deactivate', action='store_true', help='Deactivate token')
    parser.add_argument('--activate', action='store_true', help='Activate token')
    
    args = parser.parse_args()
    
    if args.list:
        list_tokens()
    elif args.make_permanent:
        if not args.token_id:
            print("❌ Error: --token-id is required")
            sys.exit(1)
        make_permanent(args.token_id)
    elif args.extend_days:
        if not args.token_id:
            print("❌ Error: --token-id is required")
            sys.exit(1)
        extend_expiration(args.token_id, args.extend_days)
    elif args.deactivate:
        if not args.token_id:
            print("❌ Error: --token-id is required")
            sys.exit(1)
        deactivate_token(args.token_id)
    elif args.activate:
        if not args.token_id:
            print("❌ Error: --token-id is required")
            sys.exit(1)
        activate_token(args.token_id)
    else:
        parser.print_help()
