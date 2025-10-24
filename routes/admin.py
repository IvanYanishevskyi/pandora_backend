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
from models.user_database_access import UserDatabaseAccess
from schemas.permission import PermissionCreate, PermissionUpdate, PermissionResponse, UserWithPermissions
from schemas.database_access import (
    DatabaseAccessCreate,
    DatabaseAccessBulkCreate,
    DatabaseAccessUpdate,
    DatabaseAccessResponse,
    DatabaseAccessWithDetails,
    UserDatabaseAccessSummary,
    DatabaseUserAccessSummary
)
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


@router.put("/organizations/{org_id}")
def update_organization(
    org_id: int,
    data: OrganizationCreate,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("super_admin")),
    db: Session = Depends(get_db)
):
    """🌍✏️ Обновить организацию (только super_admin)"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Проверка уникальности имени (если меняется)
    if data.name != org.name:
        existing = db.query(Organization).filter(
            Organization.name == data.name,
            Organization.id != org_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Organization with this name already exists")
    
    # Защита: нельзя убрать is_root у корневой организации
    if org.is_root and not data.is_root:
        raise HTTPException(
            status_code=403,
            detail="Cannot remove root status from root organization"
        )
    
    # Обновляем данные
    org.name = data.name
    org.description = data.description
    org.is_root = data.is_root
    
    db.commit()
    db.refresh(org)
    
    return {
        "message": f"Organization '{org.name}' updated successfully",
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
        # Super admin видит ВСЕХ клиентов всех организаций
        clients = db.query(Client).all()
    else:
        # Admin видит ТОЛЬКО СВОЙ клиент (к которому привязан)
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
    
    # Проверка: нельзя удалить клиента корневой организации
    organization = db.query(Organization).filter(Organization.id == client.organization_id).first()
    if organization and organization.is_root:
        raise HTTPException(
            status_code=403, 
            detail="Cannot delete clients from root organization"
        )
    
    users_count = db.query(User).filter(User.client_id == client_id).count()
    if users_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete client with {users_count} users. Remove users first."
        )
    
    db.delete(client)
    db.commit()
    return {"message": f"Client '{client.name}' deleted successfully"}


@router.put("/clients/{client_id}")
def update_client(
    client_id: int,
    data: ClientCreate,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("super_admin")),
    db: Session = Depends(get_db)
):
    """🏢✏️ Обновить данные клиента (только super_admin)"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Проверка уникальности имени (если меняется)
    if data.name != client.name:
        existing = db.query(Client).filter(
            Client.name == data.name,
            Client.id != client_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Client with this name already exists")
    
    # Проверка существования организации (если меняется)
    if data.organization_id != client.organization_id:
        org = db.query(Organization).filter(Organization.id == data.organization_id).first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
    
    # Обновляем данные
    client.name = data.name
    client.contact_email = data.contact_email
    client.organization_id = data.organization_id
    
    db.commit()
    db.refresh(client)
    
    return {
        "message": f"Client '{client.name}' updated successfully",
        "client": {
            "id": client.id,
            "name": client.name,
            "contact_email": client.contact_email,
            "organization_id": client.organization_id
        }
    }


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
    
    # Запрет удаления пользователей корневой организации
    if target.organization_id:
        organization = db.query(Organization).filter(Organization.id == target.organization_id).first()
        if organization and organization.is_root:
            raise HTTPException(
                status_code=403, 
                detail="Cannot delete users from root organization"
            )
    
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


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    data: UserCreateRequest,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """👥✏️ Обновить данные пользователя"""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Проверка прав доступа
    if user.role == UserRole.admin:
        if target.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="You can only update users from your client")
    
    # Проверка: нельзя редактировать super_admin (только другой super_admin)
    if target.role == UserRole.super_admin and user.role != UserRole.super_admin:
        raise HTTPException(status_code=403, detail="Only super_admin can update super_admin users")
    
    # Проверка уникальности username (если меняется)
    if data.username != target.username:
        existing_username = db.query(User).filter(
            User.username == data.username,
            User.id != user_id
        ).first()
        if existing_username:
            raise HTTPException(status_code=400, detail="Username already exists")
    
    # Проверка уникальности email (если меняется)
    if data.email and data.email != target.email:
        existing_email = db.query(User).filter(
            User.email == data.email,
            User.id != user_id
        ).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already exists")
    
    # Валидация роли
    try:
        new_role = UserRole[data.role]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {[r.value for r in UserRole]}")
    
    # Проверка: admin не может делать пользователей super_admin
    if new_role == UserRole.super_admin and user.role != UserRole.super_admin:
        raise HTTPException(status_code=403, detail="Only super_admin can promote users to super_admin")
    
    # Обновляем данные
    target.username = data.username
    target.email = data.email
    target.full_name = data.full_name
    target.role = new_role
    target.is_active = data.is_active
    
    # Обновляем пароль только если он передан
    if data.password:
        target.password_hash = hash_password(data.password)
    
    # Обновляем client_id (только super_admin может менять)
    if user.role == UserRole.super_admin:
        if data.client_id and data.client_id != target.client_id:
            client = db.query(Client).filter(Client.id == data.client_id).first()
            if not client:
                raise HTTPException(status_code=404, detail="Client not found")
            target.client_id = data.client_id
            target.organization_id = client.organization_id
    
    db.commit()
    db.refresh(target)
    
    return {
        "message": f"User '{target.username}' updated successfully",
        "user": user_to_dict(target)
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
        # Super admin видит ВСЕ базы данных всех организаций
        databases = db.query(ClientDatabase).all()
    else:
        # Admin видит ТОЛЬКО базы данных СВОЕГО клиента
        if not user.client_id:
            raise HTTPException(status_code=403, detail="User must be assigned to a client")
        
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
    if user.role == UserRole.super_admin:
        # Super admin может добавлять к ЛЮБОМУ клиенту
        client_id = data.client_id
    else:
        # Admin может добавлять ТОЛЬКО к СВОЕМУ клиенту
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        client_id = user.client_id
    
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
    
    # Проверка: нельзя удалить базу данных клиента корневой организации
    client = db.query(Client).filter(Client.id == target.client_id).first()
    if client:
        organization = db.query(Organization).filter(Organization.id == client.organization_id).first()
        if organization and organization.is_root:
            raise HTTPException(
                status_code=403, 
                detail="Cannot delete databases from root organization clients"
            )
    
    # Проверка прав доступа
    if user.role == UserRole.admin:
        # Admin может удалять ТОЛЬКО базы СВОЕГО клиента
        if not user.client_id or target.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="You can only delete databases from your own client")
    
    db_name = target.name
    db.delete(target)
    db.commit()
    
    return {"message": f"Database '{db_name}' deleted successfully"}


@router.put("/databases/{database_id}")
def update_database(
    database_id: int,
    data: DatabaseCreate,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """🗄️✏️ Обновить базу данных"""
    target = db.query(ClientDatabase).filter(ClientDatabase.id == database_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Database not found")
    
    # Проверка прав доступа
    if user.role == UserRole.admin:
        # Admin может редактировать ТОЛЬКО базы СВОЕГО клиента
        if not user.client_id or target.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="You can only update databases from your own client")
    
    # Обновляем данные
    target.name = data.name
    target.description = data.description
    
    # Обновить client_id может только super_admin
    if user.role == UserRole.super_admin and data.client_id != target.client_id:
        client = db.query(Client).filter(Client.id == data.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        target.client_id = data.client_id
    
    db.commit()
    db.refresh(target)
    
    return {
        "message": f"Database '{target.name}' updated successfully",
        "database": {
            "id": target.id,
            "name": target.name,
            "description": target.description,
            "client_id": target.client_id
        }
    }


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


# =====================================================
# 🔐 DATABASE ACCESS MANAGEMENT
# =====================================================

@router.get("/database-access", response_model=List[DatabaseAccessWithDetails])
def list_database_access(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    database_id: Optional[int] = Query(None, description="Filter by database ID"),
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """📊 Получить список всех правил доступа к БД
    
    - super_admin: видит все доступы
    - admin: видит только доступы в пределах своего клиента
    """
    # Используем LEFT JOIN чтобы не терять записи если связей нет
    query = db.query(UserDatabaseAccess)
    
    # Фильтрация по роли
    if user.role != UserRole.super_admin:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        # Admin видит только доступы пользователей и БД своего клиента
        # Нужно join чтобы фильтровать по client_id
        query = query.join(User).filter(User.client_id == user.client_id)
    
    # Дополнительные фильтры
    if user_id:
        query = query.filter(UserDatabaseAccess.user_id == user_id)
    if database_id:
        query = query.filter(UserDatabaseAccess.database_id == database_id)
    
    accesses = query.all()
    
    # Формируем расширенный ответ с деталями
    result = []
    for access in accesses:
        target_user = db.query(User).filter(User.id == access.user_id).first()
        target_db = db.query(ClientDatabase).filter(ClientDatabase.id == access.database_id).first()
        client = db.query(Client).filter(Client.id == target_db.client_id).first() if target_db else None
        
        result.append(DatabaseAccessWithDetails(
            id=access.id,
            user_id=access.user_id,
            database_id=access.database_id,
            can_read=access.can_read,
            can_write=access.can_write,
            created_at=access.created_at,
            updated_at=access.updated_at,
            created_by=access.created_by,
            user_username=target_user.username if target_user else None,
            database_name=target_db.name if target_db else None,
            client_name=client.name if client else None
        ))
    
    return result


@router.get("/database-access/user/{user_id}", response_model=UserDatabaseAccessSummary)
def get_user_database_access(
    user_id: int,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """👤📂 Получить все базы данных, к которым имеет доступ пользователь"""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    
    # Проверка прав: admin может управлять только своим клиентом
    if user.role != UserRole.super_admin:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        if target_user.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="Cannot access users from other clients")
    
    # Получаем все доступы пользователя
    accesses = db.query(UserDatabaseAccess).filter(
        UserDatabaseAccess.user_id == user_id
    ).all()
    
    # Получаем общее количество БД клиента
    total_databases = db.query(ClientDatabase).filter(
        ClientDatabase.client_id == target_user.client_id
    ).count()
    
    # Формируем детализированный список
    databases = []
    write_count = 0
    
    for access in accesses:
        target_db = db.query(ClientDatabase).filter(ClientDatabase.id == access.database_id).first()
        client = db.query(Client).filter(Client.id == target_db.client_id).first() if target_db else None
        
        if access.can_write:
            write_count += 1
        
        databases.append(DatabaseAccessWithDetails(
            id=access.id,
            user_id=access.user_id,
            database_id=access.database_id,
            can_read=access.can_read,
            can_write=access.can_write,
            created_at=access.created_at,
            updated_at=access.updated_at,
            created_by=access.created_by,
            user_username=target_user.username,
            database_name=target_db.name if target_db else None,
            client_name=client.name if client else None
        ))
    
    return UserDatabaseAccessSummary(
        user_id=target_user.id,
        username=target_user.username,
        total_databases=total_databases,
        accessible_databases=len(accesses),
        databases_with_write=write_count,
        databases=databases
    )


@router.get("/database-access/database/{database_id}", response_model=DatabaseUserAccessSummary)
def get_database_user_access(
    database_id: int,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """📂👥 Получить всех пользователей, имеющих доступ к базе данных"""
    target_db = db.query(ClientDatabase).filter(ClientDatabase.id == database_id).first()
    if not target_db:
        raise HTTPException(status_code=404, detail=f"Database {database_id} not found")
    
    client = db.query(Client).filter(Client.id == target_db.client_id).first()
    
    # Проверка прав: admin может управлять только своим клиентом
    if user.role != UserRole.super_admin:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        if target_db.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="Cannot access databases from other clients")
    
    # Получаем все доступы к БД
    accesses = db.query(UserDatabaseAccess).filter(
        UserDatabaseAccess.database_id == database_id
    ).all()
    
    # Формируем детализированный список пользователей
    users = []
    for access in accesses:
        target_user = db.query(User).filter(User.id == access.user_id).first()
        
        users.append(DatabaseAccessWithDetails(
            id=access.id,
            user_id=access.user_id,
            database_id=access.database_id,
            can_read=access.can_read,
            can_write=access.can_write,
            created_at=access.created_at,
            updated_at=access.updated_at,
            created_by=access.created_by,
            user_username=target_user.username if target_user else None,
            database_name=target_db.name,
            client_name=client.name if client else None
        ))
    
    return DatabaseUserAccessSummary(
        database_id=target_db.id,
        database_name=target_db.name,
        client_id=target_db.client_id,
        client_name=client.name if client else "Unknown",
        total_users_with_access=len(accesses),
        users=users
    )


@router.post("/database-access", response_model=DatabaseAccessResponse)
def create_database_access(
    data: DatabaseAccessCreate,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """➕ Выдать доступ пользователю к базе данных"""
    # Проверяем существование пользователя и БД
    target_user = db.query(User).filter(User.id == data.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User {data.user_id} not found")
    
    target_db = db.query(ClientDatabase).filter(ClientDatabase.id == data.database_id).first()
    if not target_db:
        raise HTTPException(status_code=404, detail=f"Database {data.database_id} not found")
    
    # Проверка прав: admin может управлять только своим клиентом
    if user.role != UserRole.super_admin:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        if target_user.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="Cannot manage users from other clients")
        if target_db.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="Cannot manage databases from other clients")
    
    # Проверка: пользователь и БД должны принадлежать одному клиенту
    if target_user.client_id != target_db.client_id:
        raise HTTPException(
            status_code=400,
            detail=f"User (client_id={target_user.client_id}) and database (client_id={target_db.client_id}) belong to different clients"
        )
    
    # Проверяем, не существует ли уже доступ
    existing = db.query(UserDatabaseAccess).filter(
        UserDatabaseAccess.user_id == data.user_id,
        UserDatabaseAccess.database_id == data.database_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Accesso già esistente (id={existing.id}). Usa PUT per aggiornare i permessi."
        )
    
    # Создаём доступ
    access = UserDatabaseAccess(
        user_id=data.user_id,
        database_id=data.database_id,
        can_read=data.can_read,
        can_write=data.can_write,
        created_by=user.id
    )
    
    db.add(access)
    db.commit()
    db.refresh(access)
    
    return DatabaseAccessResponse(
        id=access.id,
        user_id=access.user_id,
        database_id=access.database_id,
        can_read=access.can_read,
        can_write=access.can_write,
        created_at=access.created_at,
        updated_at=access.updated_at,
        created_by=access.created_by
    )


@router.post("/database-access/bulk", response_model=Dict[str, Any])
def create_bulk_database_access(
    data: DatabaseAccessBulkCreate,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """➕📦 Выдать доступ пользователю к нескольким базам данных сразу"""
    target_user = db.query(User).filter(User.id == data.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User {data.user_id} not found")
    
    # Проверка прав
    if user.role != UserRole.super_admin:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        if target_user.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="Cannot manage users from other clients")
    
    created = []
    skipped = []
    errors = []
    
    for db_id in data.database_ids:
        try:
            target_db = db.query(ClientDatabase).filter(ClientDatabase.id == db_id).first()
            if not target_db:
                errors.append({"database_id": db_id, "error": "Database non trovato"})
                continue
            
            # Проверка прав для каждой БД
            if user.role != UserRole.super_admin and target_db.client_id != user.client_id:
                errors.append({"database_id": db_id, "error": "Cannot manage databases from other clients"})
                continue
            
            # Проверка: пользователь и БД одного клиента
            if target_user.client_id != target_db.client_id:
                errors.append({
                    "database_id": db_id,
                    "error": f"User and database belong to different clients"
                })
                continue
            
            # Проверяем существующий доступ
            existing = db.query(UserDatabaseAccess).filter(
                UserDatabaseAccess.user_id == data.user_id,
                UserDatabaseAccess.database_id == db_id
            ).first()
            
            if existing:
                skipped.append({"database_id": db_id, "reason": "Accesso già esistente", "access_id": existing.id})
                continue
            
            # Создаём доступ
            access = UserDatabaseAccess(
                user_id=data.user_id,
                database_id=db_id,
                can_read=data.can_read,
                can_write=data.can_write,
                created_by=user.id
            )
            
            db.add(access)
            db.flush()
            
            created.append({
                "access_id": access.id,
                "database_id": db_id,
                "database_name": target_db.name
            })
            
        except Exception as e:
            errors.append({"database_id": db_id, "error": str(e)})
    
    db.commit()
    
    return {
        "message": f"Creazione accessi multipli completata: {len(created)} creati, {len(skipped)} saltati, {len(errors)} errori",
        "user_id": data.user_id,
        "username": target_user.username,
        "created": created,
        "skipped": skipped,
        "errors": errors
    }


@router.put("/database-access/{access_id}", response_model=DatabaseAccessResponse)
def update_database_access(
    access_id: int,
    data: DatabaseAccessUpdate,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """✏️ Обновить права доступа к базе данных"""
    access = db.query(UserDatabaseAccess).filter(UserDatabaseAccess.id == access_id).first()
    if not access:
        raise HTTPException(status_code=404, detail=f"Access record {access_id} not found")
    
    target_user = db.query(User).filter(User.id == access.user_id).first()
    target_db = db.query(ClientDatabase).filter(ClientDatabase.id == access.database_id).first()
    
    # Проверка прав
    if user.role != UserRole.super_admin:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        if target_user and target_user.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="Cannot manage users from other clients")
        if target_db and target_db.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="Cannot manage databases from other clients")
    
    # Обновляем права
    access.can_read = data.can_read
    access.can_write = data.can_write
    access.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(access)
    
    return DatabaseAccessResponse(
        id=access.id,
        user_id=access.user_id,
        database_id=access.database_id,
        can_read=access.can_read,
        can_write=access.can_write,
        created_at=access.created_at,
        updated_at=access.updated_at,
        created_by=access.created_by
    )


@router.delete("/database-access/{access_id}")
def delete_database_access(
    access_id: int,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """🗑️ Отозвать доступ пользователя к базе данных"""
    access = db.query(UserDatabaseAccess).filter(UserDatabaseAccess.id == access_id).first()
    if not access:
        raise HTTPException(status_code=404, detail=f"Access record {access_id} not found")
    
    target_user = db.query(User).filter(User.id == access.user_id).first()
    target_db = db.query(ClientDatabase).filter(ClientDatabase.id == access.database_id).first()
    
    # Проверка прав
    if user.role != UserRole.super_admin:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        if target_user and target_user.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="Cannot manage users from other clients")
        if target_db and target_db.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="Cannot manage databases from other clients")
    
    user_info = target_user.username if target_user else f"User#{access.user_id}"
    db_info = target_db.name if target_db else f"Database#{access.database_id}"
    
    db.delete(access)
    db.commit()
    
    return {
        "message": f"Accesso revocato: {user_info} → {db_info}",
        "access_id": access_id,
        "user_id": access.user_id,
        "database_id": access.database_id
    }


@router.delete("/database-access/user/{user_id}/all")
def revoke_all_user_database_access(
    user_id: int,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    """🗑️💥 Отозвать ВСЕ доступы пользователя к базам данных"""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    
    # Проверка прав
    if user.role != UserRole.super_admin:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        if target_user.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="Cannot manage users from other clients")
    
    accesses = db.query(UserDatabaseAccess).filter(UserDatabaseAccess.user_id == user_id).all()
    count = len(accesses)
    
    for access in accesses:
        db.delete(access)
    
    db.commit()
    
    return {
        "message": f"Tutti gli accessi al database revocati per l'utente '{target_user.username}'",
        "user_id": user_id,
        "username": target_user.username,
        "revoked_count": count
    }
