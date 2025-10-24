"""
🔐 PANDORA AI - ADMIN API
==========================
Многоуровневая система управления:
  🌍 ORGANIZATION → 🏢 CLIENT → 👥 USER → 🗄️ DATABASE

Роли:
  🧠 super_admin - полный доступ ко всему (Pandora AI root)
  ⚙️ admin - управление своим клиентом
  👤 user - работа в рамках своих разрешений
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
import zoneinfo

from core.dependencies import get_admin_from_token
from core.security import require_role, hash_password
from database.database import get_db
from models.user import User, UserRole
from models.organization import Organization
from models.client import Client
from models.client_database import ClientDatabase
from models.chat import Chat
from models.messages import Message
from models.user_permission import UserPermission
from schemas.permission import PermissionCreate, PermissionUpdate, PermissionResponse, UserWithPermissions
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/admin", tags=["admin"])


# =====================================================
# 📋 PYDANTIC SCHEMAS
# =====================================================

class UserCreateRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "user"
    is_active: bool = True
    client_id: Optional[int] = None
    organization_id: Optional[int] = 1


class OrganizationCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_root: bool = False


class ClientCreate(BaseModel):
    name: str
    contact_email: EmailStr
    organization_id: int = 1


class DatabaseCreate(BaseModel):
    name: str
    description: Optional[str] = None
    client_id: int


# =====================================================
# 🛠️ UTILITY FUNCTIONS
# =====================================================

def user_to_dict(user: User) -> Dict[str, Any]:
    """Преобразует User объект в словарь с дополнительной информацией"""
    last_login = user.last_login
    online = False
    if last_login:
        online = (datetime.utcnow() - last_login) <= timedelta(minutes=5)
    
    last_login_local = None
    if last_login:
        try:
            utc = last_login.replace(tzinfo=timezone.utc)
            local = utc.astimezone(zoneinfo.ZoneInfo("Europe/Rome"))
            last_login_local = local.isoformat()
        except Exception:
            pass

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value if isinstance(user.role, UserRole) else user.role,
        "is_active": user.is_active,
        "last_login": last_login.isoformat() if last_login else None,
        "last_login_local": last_login_local,
        "online": online,
        "client_id": user.client_id,
        "organization_id": user.organization_id,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


# =====================================================
# 🌍 ORGANIZATIONS (только super_admin)
# =====================================================

@router.get("/organizations")
def list_organizations(
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("super_admin")),
    db: Session = Depends(get_db)
):
    """🌍 Получить список всех организаций"""
    orgs = db.query(Organization).all()
    return [{
        "id": org.id,
        "name": org.name,
        "description": org.description,
        "is_root": org.is_root,
        "created_at": org.created_at.isoformat() if org.created_at else None,
        "clients_count": len(org.clients) if org.clients else 0
    } for org in orgs]


@router.post("/organizations", status_code=201)
def create_organization(
    data: OrganizationCreate,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("super_admin")),
    db: Session = Depends(get_db)
):
    """🌍 Создать новую организацию"""
    existing = db.query(Organization).filter(Organization.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Organization with this name already exists")
    
    org = Organization(
        name=data.name,
        description=data.description,
        is_root=data.is_root
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    
    return {
        "message": "Organization created successfully",
        "organization": {
            "id": org.id,
            "name": org.name,
            "description": org.description,
            "is_root": org.is_root
        }
    }


@router.delete("/organizations/{org_id}")
def delete_organization(
    org_id: int,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("super_admin")),
    db: Session = Depends(get_db)
):
    """🌍 Удалить организацию"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    if org.is_root:
        raise HTTPException(status_code=403, detail="Cannot delete root organization")
    
    clients_count = db.query(Client).filter(Client.organization_id == org_id).count()
    if clients_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete organization with {clients_count} clients. Remove clients first."
        )
    
    db.delete(org)
    db.commit()
    return {"message": f"Organization '{org.name}' deleted successfully"}


# =====================================================
# 🏢 CLIENTS (super_admin видит всех, admin только своих)
# =====================================================

@router.get("/clients")
def list_clients(
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """🏢 Получить список клиентов"""
    if user.role == UserRole.super_admin:
        clients = db.query(Client).all()
    else:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin user must be assigned to a client")
        clients = db.query(Client).filter(Client.id == user.client_id).all()
    
    return [{
        "id": client.id,
        "name": client.name,
        "contact_email": client.contact_email,
        "organization_id": client.organization_id,
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "users_count": db.query(User).filter(User.client_id == client.id).count(),
        "databases_count": db.query(ClientDatabase).filter(ClientDatabase.client_id == client.id).count()
    } for client in clients]


@router.post("/clients", status_code=201)
def create_client(
    data: ClientCreate,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("super_admin")),
    db: Session = Depends(get_db)
):
    """🏢 Создать нового клиента (только super_admin)"""
    existing = db.query(Client).filter(Client.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Client with this name already exists")
    
    org = db.query(Organization).filter(Organization.id == data.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    client = Client(
        name=data.name,
        contact_email=data.contact_email,
        organization_id=data.organization_id
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    
    return {
        "message": "Client created successfully",
        "client": {
            "id": client.id,
            "name": client.name,
            "contact_email": client.contact_email,
            "organization_id": client.organization_id
        }
    }


@router.delete("/clients/{client_id}")
def delete_client(
    client_id: int,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("super_admin")),
    db: Session = Depends(get_db)
):
    """🏢 Удалить клиента"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    users_count = db.query(User).filter(User.client_id == client_id).count()
    if users_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete client with {users_count} users. Remove users first."
        )
    
    db.delete(client)
    db.commit()
    return {"message": f"Client '{client.name}' deleted successfully"}


# =====================================================
# 👥 USERS (admin управляет своими, super_admin всеми)
# =====================================================

@router.get("/users")
def list_users(
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """👥 Получить список пользователей"""
    # Автоматически деактивируем неактивных пользователей
    cutoff = datetime.utcnow() - timedelta(hours=0.5)
    outdated = db.query(User).filter(
        User.is_active == True,
        User.last_login < cutoff
    ).all()
    for u in outdated:
        u.is_active = False
        db.add(u)
    if outdated:
        db.commit()
    
    # Фильтр по роли
    if user.role == UserRole.super_admin:
        users = db.query(User).order_by(User.id.asc()).all()
    else:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        users = db.query(User).filter(User.client_id == user.client_id).order_by(User.id.asc()).all()
    
    return [user_to_dict(u) for u in users]


@router.post("/users", status_code=201)
def create_user(
    data: UserCreateRequest,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """👥 Создать нового пользователя"""
    # Проверка существования
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    
    if data.email and db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Валидация роли
    try:
        role = UserRole[data.role]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {[r.value for r in UserRole]}")
    
    # Определение client_id и organization_id
    if user.role == UserRole.admin:
        # Админ может создавать пользователей только в своём клиенте
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        client_id = user.client_id
        organization_id = user.organization_id
    else:
        # super_admin может указать любой client_id
        client_id = data.client_id
        organization_id = data.organization_id or 1
        
        if client_id:
            client = db.query(Client).filter(Client.id == client_id).first()
            if not client:
                raise HTTPException(status_code=404, detail="Client not found")
            organization_id = client.organization_id
    
    # Создание пользователя
    new_user = User(
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        role=role,
        is_active=data.is_active,
        client_id=client_id,
        organization_id=organization_id
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "message": "User created successfully",
        "user": user_to_dict(new_user)
    }


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """👥 Удалить пользователя"""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Проверка прав доступа
    if user.role == UserRole.admin:
        if target.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="You can only delete users from your client")
    
    # Запрет удаления super_admin
    if target.role == UserRole.super_admin:
        raise HTTPException(status_code=403, detail="Cannot delete super admin users")
    
    username = target.username
    
    # Каскадное удаление связанных данных
    db.query(Message).filter(Message.chat_id.in_(
        db.query(Chat.id).filter(Chat.user_id == user_id)
    )).delete(synchronize_session=False)
    
    db.query(Chat).filter(Chat.user_id == user_id).delete()
    db.query(UserPermission).filter(UserPermission.user_id == user_id).delete()
    
    db.delete(target)
    db.commit()
    
    return {
        "message": f"User '{username}' deleted successfully",
        "deleted_user_id": user_id
    }


# =====================================================
# 🗄️ DATABASES (видит только свой клиент или super_admin)
# =====================================================

@router.get("/databases")
def list_databases(
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """🗄️ Получить список баз данных"""
    if user.role == UserRole.super_admin:
        databases = db.query(ClientDatabase).all()
    else:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        databases = db.query(ClientDatabase).filter(ClientDatabase.client_id == user.client_id).all()
    
    return [{
        "id": db_item.id,
        "name": db_item.name,
        "description": db_item.description,
        "client_id": db_item.client_id,
        "created_at": db_item.created_at.isoformat() if db_item.created_at else None
    } for db_item in databases]


@router.post("/databases", status_code=201)
def create_database(
    data: DatabaseCreate,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """🗄️ Добавить базу данных"""
    # Определение client_id
    if user.role == UserRole.admin:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        client_id = user.client_id
    else:
        client_id = data.client_id
    
    # Проверка существования клиента
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Проверка прав доступа для админа
    if user.role == UserRole.admin and client_id != user.client_id:
        raise HTTPException(status_code=403, detail="You can only add databases to your own client")
    
    # Создание базы данных
    new_db = ClientDatabase(
        name=data.name,
        description=data.description,
        client_id=client_id
    )
    
    db.add(new_db)
    db.commit()
    db.refresh(new_db)
    
    return {
        "message": "Database added successfully",
        "database": {
            "id": new_db.id,
            "name": new_db.name,
            "description": new_db.description,
            "client_id": new_db.client_id
        }
    }


@router.delete("/databases/{database_id}")
def delete_database(
    database_id: int,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """🗄️ Удалить базу данных"""
    target = db.query(ClientDatabase).filter(ClientDatabase.id == database_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Database not found")
    
    # Проверка прав доступа
    if user.role == UserRole.admin:
        if not user.client_id or target.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="You can only delete databases from your own client")
    
    db_name = target.name
    db.delete(target)
    db.commit()
    
    return {"message": f"Database '{db_name}' deleted successfully"}


# =====================================================
# 🔑 PERMISSIONS (управление разрешениями пользователей)
# =====================================================

@router.get("/permissions")
def list_all_permissions(
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """🔑 Получить список всех разрешений"""
    if user.role == UserRole.super_admin:
        permissions = db.query(UserPermission).all()
    else:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        user_ids = db.query(User.id).filter(User.client_id == user.client_id).all()
        user_ids = [uid[0] for uid in user_ids]
        permissions = db.query(UserPermission).filter(UserPermission.user_id.in_(user_ids)).all()
    
    return permissions


@router.get("/permissions/user/{user_id}")
def get_user_permissions(
    user_id: int,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """🔑 Получить разрешения конкретного пользователя"""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Проверка прав доступа
    if user.role == UserRole.admin:
        if target_user.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="You can only view permissions for users in your client")
    
    permission = db.query(UserPermission).filter(UserPermission.user_id == user_id).first()
    if not permission:
        return PermissionResponse(
            id=0,
            user_id=user_id,
            economics=False,
            consuntivi=False,
            efficienza=False,
            risorse=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    return permission


@router.post("/permissions", status_code=201)
def create_user_permissions(
    data: PermissionCreate,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """🔑 Создать разрешения для пользователя"""
    target_user = db.query(User).filter(User.id == data.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Проверка прав доступа
    if user.role == UserRole.admin:
        if target_user.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="You can only manage permissions for users in your client")
    
    # Проверка существования
    existing = db.query(UserPermission).filter(UserPermission.user_id == data.user_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Permissions already exist. Use PUT to update.")
    
    new_permission = UserPermission(
        user_id=data.user_id,
        economics=data.economics,
        consuntivi=data.consuntivi,
        efficienza=data.efficienza,
        risorse=data.risorse
    )
    
    db.add(new_permission)
    db.commit()
    db.refresh(new_permission)
    
    return new_permission


@router.put("/permissions/user/{user_id}")
def update_user_permissions(
    user_id: int,
    data: PermissionUpdate,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """🔑 Обновить разрешения пользователя"""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Проверка прав доступа
    if user.role == UserRole.admin:
        if target_user.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="You can only manage permissions for users in your client")
    
    permission = db.query(UserPermission).filter(UserPermission.user_id == user_id).first()
    if not permission:
        permission = UserPermission(user_id=user_id)
        db.add(permission)
    
    permission.economics = data.economics
    permission.consuntivi = data.consuntivi
    permission.efficienza = data.efficienza
    permission.risorse = data.risorse
    
    db.commit()
    db.refresh(permission)
    
    return permission


@router.delete("/permissions/user/{user_id}", status_code=204)
def delete_user_permissions(
    user_id: int,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """🔑 Удалить разрешения пользователя"""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Проверка прав доступа
    if user.role == UserRole.admin:
        if target_user.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="You can only manage permissions for users in your client")
    
    permission = db.query(UserPermission).filter(UserPermission.user_id == user_id).first()
    if not permission:
        raise HTTPException(status_code=404, detail="Permissions not found")
    
    db.delete(permission)
    db.commit()
    return None


# =====================================================
# 📊 STATISTICS & ANALYTICS
# =====================================================

@router.get("/stats/overview")
def get_overview_stats(
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """📊 Получить общую статистику системы"""
    if user.role == UserRole.super_admin:
        return {
            "organizations": db.query(Organization).count(),
            "clients": db.query(Client).count(),
            "users": db.query(User).count(),
            "databases": db.query(ClientDatabase).count(),
            "active_users": db.query(User).filter(User.is_active == True).count(),
            "super_admins": db.query(User).filter(User.role == UserRole.super_admin).count(),
            "admins": db.query(User).filter(User.role == UserRole.admin).count(),
            "regular_users": db.query(User).filter(User.role == UserRole.user).count(),
        }
    else:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        return {
            "client_id": user.client_id,
            "users": db.query(User).filter(User.client_id == user.client_id).count(),
            "databases": db.query(ClientDatabase).filter(ClientDatabase.client_id == user.client_id).count(),
            "active_users": db.query(User).filter(
                User.client_id == user.client_id,
                User.is_active == True
            ).count(),
        }


@router.get("/stats/users-by-role")
def get_users_by_role(
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """📊 Статистика пользователей по ролям"""
    query = db.query(User)
    if user.role != UserRole.super_admin:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        query = query.filter(User.client_id == user.client_id)
    
    stats = {}
    active_stats = {}
    
    for role in UserRole:
        stats[role.value] = query.filter(User.role == role).count()
        active_stats[role.value] = query.filter(User.role == role, User.is_active == True).count()
    
    return {
        "total_by_role": stats,
        "active_by_role": active_stats,
        "total_users": sum(stats.values()),
        "total_active_users": sum(active_stats.values())
    }


# =====================================================
# 🎭 ROLE MANAGEMENT (управление ролями пользователей)
# =====================================================

@router.put("/users/{user_id}/promote-to-super-admin")
def promote_to_super_admin(
    user_id: int,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("super_admin")),
    db: Session = Depends(get_db)
):
    """🎭 Повысить пользователя до super_admin"""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    target.role = UserRole.super_admin
    db.commit()
    db.refresh(target)
    
    return {
        "message": f"User '{target.username}' promoted to super_admin",
        "user": user_to_dict(target)
    }


@router.put("/users/{user_id}/demote-from-super-admin")
def demote_from_super_admin(
    user_id: int,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("super_admin")),
    db: Session = Depends(get_db)
):
    """🎭 Понизить super_admin до admin"""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    if target.role != UserRole.super_admin:
        raise HTTPException(status_code=400, detail="User is not a super_admin")
    
    target.role = UserRole.admin
    db.commit()
    db.refresh(target)
    
    return {
        "message": f"User '{target.username}' demoted to admin",
        "user": user_to_dict(target)
    }


@router.get("/users-with-permissions")
def list_users_with_permissions(
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """👥🔑 Получить всех пользователей с их разрешениями"""
    query = db.query(User).order_by(User.id.asc())
    if user.role != UserRole.super_admin:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        query = query.filter(User.client_id == user.client_id)
    
    users = query.all()
    result = []
    
    for u in users:
        permission = db.query(UserPermission).filter(UserPermission.user_id == u.id).first()
        
        user_data = UserWithPermissions(
            id=u.id,
            username=u.username,
            email=u.email,
            full_name=u.full_name,
            role=u.role.value if isinstance(u.role, UserRole) else u.role,
            is_active=u.is_active,
            permissions=permission
        )
        result.append(user_data)
    
    return result
