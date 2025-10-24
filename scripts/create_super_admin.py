#!/usr/bin/env python3
"""
Script to create a super admin user.
Usage: python3 create_super_admin.py <username> <password> [email] [full_name]
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from database.database import get_db_session
from models.user import User, UserRole
from core.security import hash_password
from datetime import datetime

def create_super_admin(username: str, password: str, email: str = None, full_name: str = None):
    """Create a super admin user."""
    db = next(get_db_session())
    
    try:
        # Check if username already exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"❌ Error: User '{username}' already exists")
            return False
        
        # Check if email already exists (if provided)
        if email:
            existing_email = db.query(User).filter(User.email == email).first()
            if existing_email:
                print(f"❌ Error: Email '{email}' already exists")
                return False
        
        # Create new super admin user
        new_user = User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            role=UserRole.super_admin,
            is_active=True,
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        print(f"✅ Super admin user '{username}' created successfully!")
        print(f"   ID: {new_user.id}")
        print(f"   Role: {new_user.role.value}")
        print(f"   Email: {new_user.email or 'Not provided'}")
        print(f"   Full name: {new_user.full_name or 'Not provided'}")
        print(f"   Active: {new_user.is_active}")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating super admin: {e}")
        return False
    finally:
        db.close()

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 create_super_admin.py <username> <password> [email] [full_name]")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    email = sys.argv[3] if len(sys.argv) > 3 else None
    full_name = sys.argv[4] if len(sys.argv) > 4 else None
    
    print(f"Creating super admin user: {username}")
    success = create_super_admin(username, password, email, full_name)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
