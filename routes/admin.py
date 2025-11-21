

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
import zoneinfo
import json

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


class UserCreateRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "user"
    is_active: bool = True
    client_id: Optional[int] = None
    organization_id: Optional[int] = 1


class UserUpdateRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    client_id: Optional[int] = None
    organization_id: Optional[int] = None


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
    db_host: Optional[str] = "localhost"
    db_port: Optional[int] = 3306
    db_user: Optional[str] = None
    db_password: Optional[str] = None
    db_name: Optional[str] = None  



def user_to_dict(user: User) -> Dict[str, Any]:
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



@router.get("/organizations")
def list_organizations(
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("super_admin")),
    db: Session = Depends(get_db)
):
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
    try:
        from core.audit import log_access
        log_access(db=db, actor_user=user, admin_token=admin_token, action="create_organization", target_type="organization", target_id=org.id, details={"name": org.name})
    except Exception:
        pass

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
    try:
        from core.audit import log_access
        log_access(db=db, actor_user=user, admin_token=admin_token, action="delete_organization", target_type="organization", target_id=org_id, details={"name": org.name})
    except Exception:
        pass

    return {"message": f"Organization '{org.name}' deleted successfully"}



@router.get("/clients")
def list_clients(
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    
    if user.role == UserRole.super_admin:
        clients = db.query(Client).all()
    else:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin user must be assigned to a client")
        clients = db.query(Client).filter(Client.id == user.client_id).all()
    
    result = [{
        "id": client.id,
        "name": client.name,
        "contact_email": client.contact_email,
        "organization_id": client.organization_id,
        "created_at": client.created_at.isoformat() if client.created_at else None,
        "users_count": db.query(User).filter(User.client_id == client.id).count(),
        "databases_count": db.query(ClientDatabase).filter(ClientDatabase.client_id == client.id).count()
    } for client in clients]


    return result


@router.post("/clients", status_code=201)
def create_client(
    data: ClientCreate,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("super_admin")),
    db: Session = Depends(get_db)
):
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
    try:
        from core.audit import log_access
        log_access(db=db, actor_user=user, admin_token=admin_token, action="create_client", target_type="client", target_id=client.id, details={"name": client.name})
    except Exception:
        pass

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
    try:
        from core.audit import log_access
        log_access(db=db, actor_user=user, admin_token=admin_token, action="delete_client", target_type="client", target_id=client_id, details={"name": client.name})
    except Exception:
        pass

    return {"message": f"Client '{client.name}' deleted successfully"}




@router.get("/users")
def list_users(
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):

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
    
    if user.role == UserRole.super_admin:
        users = db.query(User).order_by(User.id.asc()).all()
    else:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        users = db.query(User).filter(User.client_id == user.client_id).order_by(User.id.asc()).all()
    
    result = [user_to_dict(u) for u in users]

    return result


@router.post("/users", status_code=201)
def create_user(
    data: UserCreateRequest,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):

    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")
    
    if data.email and db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")
    
    try:
        role = UserRole[data.role]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {[r.value for r in UserRole]}")
    
    if user.role == UserRole.admin:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        client_id = user.client_id
        organization_id = user.organization_id
    else:
        client_id = data.client_id
        organization_id = data.organization_id or 1
        
        if client_id:
            client = db.query(Client).filter(Client.id == client_id).first()
            if not client:
                raise HTTPException(status_code=404, detail="Client not found")
            organization_id = client.organization_id
    
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
    try:
        from core.audit import log_access
        log_access(db=db, actor_user=user, admin_token=admin_token, action="create_user", target_type="user", target_id=new_user.id, details={"username": new_user.username, "client_id": new_user.client_id})
    except Exception:
        pass

    return {
        "message": "User created successfully",
        "user": user_to_dict(new_user)
    }


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    data: UserUpdateRequest,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role == UserRole.admin:
        if target.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="You can only update users from your client")

    if data.username and data.username != target.username:
        if db.query(User).filter(User.username == data.username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        target.username = data.username

    if data.email and data.email != target.email:
        if db.query(User).filter(User.email == data.email).first():
            raise HTTPException(status_code=400, detail="Email already exists")
        target.email = data.email

    if data.full_name is not None:
        target.full_name = data.full_name

    # Password is optional on update — only set if provided
    if hasattr(data, 'password') and data.password:
        target.password_hash = hash_password(data.password)

    # Role and client changes restricted to super_admin
    try:
        # role provided as string like 'user'/'admin'/'super_admin'
        if data.role and data.role != (target.role.value if hasattr(target.role, 'value') else str(target.role)):
            if user.role != UserRole.super_admin:
                raise HTTPException(status_code=403, detail="Only super_admin can change roles")
            try:
                new_role = UserRole[data.role]
            except KeyError:
                raise HTTPException(status_code=400, detail="Invalid role")
            target.role = new_role
    except Exception:
        # re-raise HTTPException
        raise

    if data.is_active is not None:
        target.is_active = data.is_active

    if data.client_id is not None:
        if user.role != UserRole.super_admin:
            raise HTTPException(status_code=403, detail="Only super_admin can change client assignment")
        client = db.query(Client).filter(Client.id == data.client_id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        target.client_id = data.client_id
        target.organization_id = client.organization_id

    db.add(target)
    db.commit()
    db.refresh(target)

    try:
        from core.audit import log_access
        log_access(db=db, actor_user=user, admin_token=admin_token, action="update_user", target_type="user", target_id=target.id, details={"username": target.username, "client_id": target.client_id})
    except Exception:
        pass

    return {"message": "User updated successfully", "user": user_to_dict(target)}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.role == UserRole.admin:
        if target.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="You can only delete users from your client")
    
    if target.role == UserRole.super_admin:
        raise HTTPException(status_code=403, detail="Cannot delete super admin users")
    
    username = target.username
    
    db.query(Message).filter(Message.chat_id.in_(
        db.query(Chat.id).filter(Chat.user_id == user_id)
    )).delete(synchronize_session=False)
    
    db.query(Chat).filter(Chat.user_id == user_id).delete()
    db.query(UserPermission).filter(UserPermission.user_id == user_id).delete()
    
    db.delete(target)
    db.commit()
    try:
        from core.audit import log_access
        log_access(db=db, actor_user=user, admin_token=admin_token, action="delete_user", target_type="user", target_id=user_id, details={"username": username})
    except Exception:
        pass

    return {
        "message": f"User '{username}' deleted successfully",
        "deleted_user_id": user_id
    }



@router.get("/databases")
def list_databases(
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    if user.role == UserRole.super_admin:
        databases = db.query(ClientDatabase).all()
    else:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        databases = db.query(ClientDatabase).filter(ClientDatabase.client_id == user.client_id).all()
    
    result = [{
        "id": db_item.id,
        "name": db_item.name,
        "description": db_item.description,
        "client_id": db_item.client_id,
        "db_host": db_item.db_host,
        "db_port": db_item.db_port,
        "db_user": db_item.db_user,
        "db_name": db_item.db_name,
        "created_at": db_item.created_at.isoformat() if db_item.created_at else None
    } for db_item in databases]


    return result


@router.post("/databases", status_code=201)
def create_database(
    data: DatabaseCreate,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):

    if user.role == UserRole.admin:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Admin must be assigned to a client")
        client_id = user.client_id
    else:
        client_id = data.client_id
    
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    if user.role == UserRole.admin and client_id != user.client_id:
        raise HTTPException(status_code=403, detail="You can only add databases to your own client")
    
    new_db = ClientDatabase(
        name=data.name,
        description=data.description,
        client_id=client_id,
        db_host=data.db_host,
        db_port=data.db_port,
        db_user=data.db_user,
        db_password=data.db_password,
        db_name=data.db_name if data.db_name else data.name 
    )
    
    db.add(new_db)
    db.commit()
    db.refresh(new_db)
    try:
        from core.audit import log_access
        log_access(db=db, actor_user=user, admin_token=admin_token, action="create_database", target_type="database", target_id=new_db.id, details={"name": new_db.name, "client_id": new_db.client_id})
    except Exception:
        pass

    return {
        "message": "Database added successfully",
        "database": {
            "id": new_db.id,
            "name": new_db.name,
            "description": new_db.description,
            "client_id": new_db.client_id,
            "db_host": new_db.db_host,
            "db_port": new_db.db_port,
            "db_user": new_db.db_user,
            "db_name": new_db.db_name
        }
    }


@router.delete("/databases/{database_id}")
def delete_database(
    database_id: int,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    target = db.query(ClientDatabase).filter(ClientDatabase.id == database_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Database not found")
    
    if user.role == UserRole.admin:
        if not user.client_id or target.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="You can only delete databases from your own client")
    
    db_name = target.name
    from models.user_database_access import UserDatabaseAccess
    db.query(UserDatabaseAccess).filter(UserDatabaseAccess.database_id == database_id).delete(synchronize_session=False)
    db.delete(target)
    db.commit()
    try:
        from core.audit import log_access
        log_access(db=db, actor_user=user, admin_token=admin_token, action="delete_database", target_type="database", target_id=database_id, details={"name": db_name})
    except Exception:
        pass

    return {"message": f"Database '{db_name}' deleted successfully"}



@router.get("/permissions")
def list_all_permissions(
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
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
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

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

    # (no audit logging for read/get permissions)
    return permission


@router.post("/permissions", status_code=201)
def create_user_permissions(
    data: PermissionCreate,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    target_user = db.query(User).filter(User.id == data.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.role == UserRole.admin:
        if target_user.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="You can only manage permissions for users in your client")
    
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
    try:
        from core.audit import log_access
        log_access(db=db, actor_user=user, admin_token=admin_token, action="create_permissions", target_type="user", target_id=data.user_id, details={"permissions_id": new_permission.id})
    except Exception:
        pass

    return new_permission


@router.put("/permissions/user/{user_id}")
def update_user_permissions(
    user_id: int,
    data: PermissionUpdate,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
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
    try:
        from core.audit import log_access
        log_access(db=db, actor_user=user, admin_token=admin_token, action="update_permissions", target_type="user", target_id=user_id, details={"permissions_id": permission.id})
    except Exception:
        pass

    return permission


@router.delete("/permissions/user/{user_id}", status_code=204)
def delete_user_permissions(
    user_id: int,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.role == UserRole.admin:
        if target_user.client_id != user.client_id:
            raise HTTPException(status_code=403, detail="You can only manage permissions for users in your client")
    
    permission = db.query(UserPermission).filter(UserPermission.user_id == user_id).first()
    if not permission:
        raise HTTPException(status_code=404, detail="Permissions not found")
    
    db.delete(permission)
    db.commit()
    try:
        from core.audit import log_access
        log_access(db=db, actor_user=user, admin_token=admin_token, action="delete_permissions", target_type="user", target_id=user_id, details={})
    except Exception:
        pass
    return None



@router.get("/stats/overview")
def get_overview_stats(
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
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




@router.put("/users/{user_id}/promote-to-super-admin")
def promote_to_super_admin(
    user_id: int,
    admin_token=Depends(get_admin_from_token),
    user=Depends(require_role("super_admin")),
    db: Session = Depends(get_db)
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    target.role = UserRole.super_admin
    db.commit()
    db.refresh(target)
    try:
        from core.audit import log_access
        log_access(db=db, actor_user=user, admin_token=admin_token, action="promote_to_super_admin", target_type="user", target_id=user_id, details={"username": target.username})
    except Exception:
        pass

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
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    
    if target.role != UserRole.super_admin:
        raise HTTPException(status_code=400, detail="User is not a super_admin")
    
    target.role = UserRole.admin
    db.commit()
    db.refresh(target)
    try:
        from core.audit import log_access
        log_access(db=db, actor_user=user, admin_token=admin_token, action="demote_from_super_admin", target_type="user", target_id=user_id, details={"username": target.username})
    except Exception:
        pass

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



@router.get("/database-access/user/{user_id}")
def get_user_database_access(
    user_id: int,
    admin_token=Depends(get_admin_from_token),
    current_user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    from models.user_database_access import UserDatabaseAccess
    
    target_user = db.query(User).get(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if current_user.role == UserRole.admin:
        if target_user.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    accesses = db.query(UserDatabaseAccess).filter(
        UserDatabaseAccess.user_id == user_id
    ).all()
    
    result = []
    for access in accesses:
        database = db.query(ClientDatabase).get(access.database_id)
        result.append({
            "id": access.id,
            "user_id": access.user_id,
            "database_id": access.database_id,
            "database_name": database.name if database else None,
            "can_read": access.can_read,
            "can_write": access.can_write,
            "created_at": access.created_at.isoformat() if access.created_at else None,
        })
    

    return result


@router.delete("/database-access/user/{user_id}/all")
def delete_all_user_database_access(
    user_id: int,
    admin_token=Depends(get_admin_from_token),
    current_user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    from models.user_database_access import UserDatabaseAccess

    target_user = db.query(User).get(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.role == UserRole.admin:
        if target_user.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Access denied")

    deleted = db.query(UserDatabaseAccess).filter(UserDatabaseAccess.user_id == user_id).delete(synchronize_session=False)
    db.commit()

    try:
        from core.audit import log_access
        log_access(db=db, actor_user=current_user, admin_token=admin_token, action="delete_all_user_database_access", target_type="user", target_id=user_id, details={"deleted_count": deleted})
    except Exception:
        pass

    return {"message": f"Deleted {deleted} database access records for user {user_id}"}


@router.post("/database-access")
def create_database_access(
    user_id: int,
    database_id: int,
    can_read: bool = True,
    can_write: bool = False,
    admin_token=Depends(get_admin_from_token),
    current_user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    from models.user_database_access import UserDatabaseAccess
    
    target_user = db.query(User).get(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    target_db = db.query(ClientDatabase).get(database_id)
    if not target_db:
        raise HTTPException(status_code=404, detail="Database not found")
    
    if current_user.role == UserRole.admin:
        if target_user.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Cannot grant access to users from other organizations")
        
        client = db.query(Client).get(target_db.client_id)
        if not client or client.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Cannot grant access to databases from other organizations")
    
    existing = db.query(UserDatabaseAccess).filter(
        UserDatabaseAccess.user_id == user_id,
        UserDatabaseAccess.database_id == database_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Access already exists")
    
    access = UserDatabaseAccess(
        user_id=user_id,
        database_id=database_id,
        can_read=can_read,
        can_write=can_write,
        created_by=current_user.id
    )
    
    db.add(access)
    db.commit()
    db.refresh(access)
    try:
        from core.audit import log_access
        log_access(db=db, actor_user=current_user, admin_token=admin_token, action="create_database_access", target_type="user", target_id=user_id, details={"access_id": access.id, "database_id": access.database_id})
    except Exception:
        pass

    return {
        "message": "Database access granted",
        "access": {
            "id": access.id,
            "user_id": access.user_id,
            "database_id": access.database_id,
            "can_read": access.can_read,
            "can_write": access.can_write,
        }
    }


@router.put("/database-access/{access_id}")
def update_database_access(
    access_id: int,
    can_read: bool = None,
    can_write: bool = None,
    admin_token=Depends(get_admin_from_token),
    current_user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    from models.user_database_access import UserDatabaseAccess
    
    access = db.query(UserDatabaseAccess).get(access_id)
    if not access:
        raise HTTPException(status_code=404, detail="Access not found")
    
    if current_user.role == UserRole.admin:
        target_user = db.query(User).get(access.user_id)
        if target_user.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    if can_read is not None:
        access.can_read = can_read
    if can_write is not None:
        access.can_write = can_write
    
    db.commit()
    db.refresh(access)
    try:
        from core.audit import log_access
        log_access(db=db, actor_user=current_user, admin_token=admin_token, action="update_database_access", target_type="database_access", target_id=access_id, details={"user_id": access.user_id, "database_id": access.database_id})
    except Exception:
        pass

    return {
        "message": "Access updated",
        "access": {
            "id": access.id,
            "can_read": access.can_read,
            "can_write": access.can_write,
        }
    }


@router.delete("/database-access/{access_id}")
def delete_database_access(
    access_id: int,
    admin_token=Depends(get_admin_from_token),
    current_user=Depends(require_role("admin", "super_admin")),
    db: Session = Depends(get_db)
):
    from models.user_database_access import UserDatabaseAccess
    
    access = db.query(UserDatabaseAccess).get(access_id)
    if not access:
        raise HTTPException(status_code=404, detail="Access not found")
    
    if current_user.role == UserRole.admin:
        target_user = db.query(User).get(access.user_id)
        if target_user.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    db.delete(access)
    db.commit()
    try:
        from core.audit import log_access
        log_access(db=db, actor_user=current_user, admin_token=admin_token, action="delete_database_access", target_type="database_access", target_id=access_id, details={"user_id": access.user_id, "database_id": access.database_id})
    except Exception:
        pass

    return {"message": "Database access revoked"}




@router.get("/tenant-registry")
def get_tenant_registry(
    admin_token = Depends(get_admin_from_token),
    user = Depends(require_role("super_admin", "admin")),
    db: Session = Depends(get_db)
):
   
    from models.tenant_registry import TenantRegistry
    
    query = db.query(TenantRegistry).join(Client)
    
    if user.role == UserRole.admin:
        query = query.filter(Client.id == user.client_id)
    
    registries = query.all()
    
    return [{
        "id": r.id,
        "client_id": r.client_id,
        "client_name": r.client.name,
        "core_url": r.core_url,
        "is_active": r.is_active,
        "health_check_url": r.health_check_url,
        "created_at": r.created_at,
        "updated_at": r.updated_at
    } for r in registries]


@router.post("/tenant-registry")
def create_tenant_registry(
    client_id: int,
    core_url: str,
    health_check_url: str = "/health",
    admin_token = Depends(get_admin_from_token),
    user = Depends(require_role("super_admin")),
    db: Session = Depends(get_db)
):
 
    from models.tenant_registry import TenantRegistry
    from core.audit import log_unified
    
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(404, "Client not found")
    
    existing = db.query(TenantRegistry).filter(
        TenantRegistry.client_id == client_id
    ).first()
    
    if existing:
        raise HTTPException(400, f"Core already registered for client {client.name}")
    
    registry = TenantRegistry(
        client_id=client_id,
        core_url=core_url,
        health_check_url=health_check_url,
        is_active=True
    )
    
    db.add(registry)
    db.commit()
    db.refresh(registry)
    
    # Audit log
    try:
        log_unified(
            db=db,
            user_id=user.id,
            user_role=user.role.value if hasattr(user.role, 'value') else str(user.role),
            action="create_tenant_registry",
            request_type="admin",
            status="success",
            target_type="tenant_registry",
            target_id=registry.id,
            details={"client_id": client_id, "core_url": core_url}
        )
    except Exception:
        pass
    
    return {
        "message": "Tenant registry created",
        "registry": {
            "id": registry.id,
            "client_id": registry.client_id,
            "client_name": client.name,
            "core_url": registry.core_url
        }
    }


@router.put("/tenant-registry/{registry_id}")
def update_tenant_registry(
    registry_id: int,
    core_url: Optional[str] = None,
    is_active: Optional[bool] = None,
    health_check_url: Optional[str] = None,
    admin_token = Depends(get_admin_from_token),
    user = Depends(require_role("super_admin")),
    db: Session = Depends(get_db)
):

    from models.tenant_registry import TenantRegistry
    from core.audit import log_unified
    
    registry = db.query(TenantRegistry).filter(
        TenantRegistry.id == registry_id
    ).first()
    
    if not registry:
        raise HTTPException(404, "Registry not found")

    if core_url is not None:
        registry.core_url = core_url
    if is_active is not None:
        registry.is_active = is_active
    if health_check_url is not None:
        registry.health_check_url = health_check_url
    
    db.commit()
    db.refresh(registry)
    
    # Audit log
    try:
        log_unified(
            db=db,
            user_id=user.id,
            user_role=user.role.value if hasattr(user.role, 'value') else str(user.role),
            action="update_tenant_registry",
            request_type="admin",
            status="success",
            target_type="tenant_registry",
            target_id=registry.id,
            details={
                "core_url": core_url,
                "is_active": is_active,
                "health_check_url": health_check_url
            }
        )
    except Exception:
        pass
    
    return {"message": "Registry updated", "registry_id": registry.id}


@router.delete("/tenant-registry/{registry_id}")
def delete_tenant_registry(
    registry_id: int,
    admin_token = Depends(get_admin_from_token),
    user = Depends(require_role("super_admin")),
    db: Session = Depends(get_db)
):
    
    from models.tenant_registry import TenantRegistry
    from core.audit import log_unified
    
    registry = db.query(TenantRegistry).filter(
        TenantRegistry.id == registry_id
    ).first()
    
    if not registry:
        raise HTTPException(404, "Registry not found")
    
    client_name = registry.client.name
    db.delete(registry)
    db.commit()
    
    # Audit log
    try:
        log_unified(
            db=db,
            user_id=user.id,
            user_role=user.role.value if hasattr(user.role, 'value') else str(user.role),
            action="delete_tenant_registry",
            request_type="admin",
            status="success",
            target_type="tenant_registry",
            target_id=registry_id,
            details={"client_name": client_name}
        )
    except Exception:
        pass
    
    return {"message": f"Registry deleted for client {client_name}"}

