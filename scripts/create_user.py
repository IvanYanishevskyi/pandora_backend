import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from database.database import get_db
from models.favourites import FavoriteQuestion
from models.chat import Chat
from models.user import User, UserRole
from core.security import hash_password


def create_user():
    db: Session = next(get_db())

    username = "andrea"
    password = "123"
    email = "andrea@camngo.com"

    user = User(
        username=username,
        email=email,
        full_name="CamnGo",
        password_hash=hash_password(password),
        role=UserRole.user,
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    print(f"✅ User {username} created with ID {user.id}")


if __name__ == "__main__":
    create_user()
