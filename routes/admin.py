from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from core.dependencies import get_admin_from_token
from core.security import require_role
from database.database import get_db
from models.user import User, UserRole
from models.chat import Chat
from models.messages import Message
from models.organization import Organization
from models.client import Client
from models.client_database import ClientDatabase
from datetime import datetime, timedelta, timezone
import zoneinfo
from schemas.permission import PermissionCreate, PermissionUpdate, PermissionResponse, UserWithPermissions
from models.user_permission import UserPermission
from core.security import hash_password
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/admin", tags=["admin"])


class UserCreateRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "user"  # "super_admin", "admin" or "user"
    is_active: bool = True


def user_to_dict(user: User) -> Dict[str, Any]:
    last_login = user.last_login
    online = False
    if last_login:
        # consider online if last_login within last 5 minutes
        online = (datetime.utcnow() - last_login) <= timedelta(minutes=5)
    # compute local representation
    last_login_local = None
    if last_login:
        try:
            utc = last_login.replace(tzinfo=timezone.utc)
            local = utc.astimezone(zoneinfo.ZoneInfo("Europe/Rome"))
            last_login_local = local.isoformat()
        except Exception:
            last_login_local = None

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.name if hasattr(user.role, 'name') else str(user.role),
        "is_active": user.is_active,
        "last_login": last_login,
        "last_login_local": last_login_local,
        "online": online,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


from datetime import datetime, timedelta

@router.get("/users", response_model=List[Dict[str, Any]])
def list_users(admin_token=Depends(get_admin_from_token), db: Session = Depends(get_db)):
    t = datetime.utcnow() - timedelta(hours=0.5)
    outdated = db.query(User).filter(User.is_active == True, User.last_login < t).all()
    for user in outdated:
        user.is_active = False
        db.add(user)
    if outdated:
        db.commit()

    users = db.query(User).order_by(User.id.asc()).all()
    return [user_to_dict(u) for u in users]


@router.get("/users/full", response_model=List[Dict[str, Any]])
def list_users_full(include_sensitive: bool = False, admin_token=Depends(get_admin_from_token), db: Session = Depends(get_db)):
    """Return all users with full set of parameters. By default sensitive fields like password_hash are omitted unless include_sensitive=true."""
    users = db.query(User).order_by(User.id.asc()).all()
    out = []
    for u in users:
        item = {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role.name if hasattr(u.role, 'name') else str(u.role),
            "is_active": u.is_active,
            "last_login": u.last_login,
            "last_login_local": None,
            "online": False,
            "created_at": u.created_at,
            "updated_at": u.updated_at,
        }
        if u.last_login:
            try:
                utc = u.last_login.replace(tzinfo=timezone.utc)
                local = utc.astimezone(zoneinfo.ZoneInfo("Europe/Rome"))
                item["last_login_local"] = local.isoformat()
                item["online"] = (datetime.utcnow() - u.last_login) <= timedelta(minutes=5)
            except Exception:
                pass
        if include_sensitive:
            item["password_hash"] = u.password_hash

        out.append(item)

    return out


@router.get("/permissions", response_model=List[PermissionResponse])
def list_all_permissions(
    admin_token=Depends(get_admin_from_token),
    db: Session = Depends(get_db)
):
    """Get all user permissions"""
    permissions = db.query(UserPermission).all()
    return permissions


@router.get("/permissions/user/{user_id}", response_model=PermissionResponse)
def get_user_permissions(
    user_id: int,
    admin_token=Depends(get_admin_from_token),
    db: Session = Depends(get_db)
):
    """Get permissions for a specific user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    permission = db.query(UserPermission).filter(UserPermission.user_id == user_id).first()
    if not permission:
        # Return default permissions if not set
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


@router.post("/permissions", response_model=PermissionResponse, status_code=201)
def create_user_permissions(
    permission_data: PermissionCreate,
    admin_token=Depends(get_admin_from_token),
    db: Session = Depends(get_db)
):
    """Create permissions for a user"""
    # Check if user exists
    user = db.query(User).filter(User.id == permission_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if permissions already exist
    existing = db.query(UserPermission).filter(UserPermission.user_id == permission_data.user_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Permissions already exist for this user. Use PUT to update.")
    
    # Create new permissions
    new_permission = UserPermission(
        user_id=permission_data.user_id,
        economics=permission_data.economics,
        consuntivi=permission_data.consuntivi,
        efficienza=permission_data.efficienza,
        risorse=permission_data.risorse
    )
    
    db.add(new_permission)
    db.commit()
    db.refresh(new_permission)
    
    return new_permission


@router.put("/permissions/user/{user_id}", response_model=PermissionResponse)
def update_user_permissions(
    user_id: int,
    permission_data: PermissionUpdate,
    admin_token=Depends(get_admin_from_token),
    db: Session = Depends(get_db)
):
    """Update permissions for a user"""
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get or create permissions
    permission = db.query(UserPermission).filter(UserPermission.user_id == user_id).first()
    
    if not permission:
        # Create if doesn't exist
        permission = UserPermission(user_id=user_id)
        db.add(permission)
    
    # Update fields
    permission.economics = permission_data.economics
    permission.consuntivi = permission_data.consuntivi
    permission.efficienza = permission_data.efficienza
    permission.risorse = permission_data.risorse
    
    db.commit()
    db.refresh(permission)
    
    return permission


@router.delete("/permissions/user/{user_id}", status_code=204)
def delete_user_permissions(
    user_id: int,
    admin_token=Depends(get_admin_from_token),
    db: Session = Depends(get_db)
):
    """Delete permissions for a user (reset to defaults)"""
    permission = db.query(UserPermission).filter(UserPermission.user_id == user_id).first()
    
    if not permission:
        raise HTTPException(status_code=404, detail="Permissions not found for this user")
    
    db.delete(permission)
    db.commit()
    
    return None


@router.get("/users-with-permissions", response_model=List[UserWithPermissions])
def list_users_with_permissions(
    admin_token=Depends(get_admin_from_token),
    db: Session = Depends(get_db)
):
    """Get all users with their permissions"""
    users = db.query(User).order_by(User.id.asc()).all()
    result = []
    
    for user in users:
        permission = db.query(UserPermission).filter(UserPermission.user_id == user.id).first()
        
        user_data = UserWithPermissions(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role.name if hasattr(user.role, 'name') else str(user.role),
            is_active=user.is_active,
            permissions=permission
        )
        result.append(user_data)
    
    return result


@router.post("/users", response_model=Dict[str, Any], status_code=201)
def create_user(
    user_data: UserCreateRequest,
    admin_token=Depends(get_admin_from_token),
    db: Session = Depends(get_db)
):
    """Create a new user (admin only)"""
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Check if email already exists (if provided)
    if user_data.email:
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already exists")
    
    # Validate role
    try:
        role = UserRole[user_data.role]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be 'super_admin', 'admin' or 'user'")
    
    # Create new user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        password_hash=hash_password(user_data.password),
        role=role,
        is_active=user_data.is_active,
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "message": "User created successfully",
        "user": user_to_dict(new_user)
    }


@router.delete("/users/{user_id}", status_code=200)
def delete_user(
    user_id: int,
    admin_token=Depends(get_admin_from_token),
    db: Session = Depends(get_db)
):
    """Delete a user (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent deletion of super admin users
    if user.role == UserRole.super_admin:
        raise HTTPException(
            status_code=403, 
            detail="Cannot delete users with super admin role"
        )
    
    username = user.username
    
    # Delete all chats and their messages for this user
    user_chats = db.query(Chat).filter(Chat.user_id == user_id).all()
    for chat in user_chats:
        # Delete messages in this chat
        db.query(Message).filter(Message.chat_id == chat.id).delete()
        # Delete the chat
        db.delete(chat)
    
    # Delete associated permissions
    db.query(UserPermission).filter(UserPermission.user_id == user_id).delete()
    
    # Delete the user
    db.delete(user)
    db.commit()
    
    return {
        "message": f"User '{username}' deleted successfully",
        "deleted_user_id": user_id
    }


@router.put("/users/{user_id}/promote-to-super-admin", status_code=200)
def promote_to_super_admin(
    user_id: int,
    admin_token=Depends(get_admin_from_token),
    db: Session = Depends(get_db)
):
    """Promote a user to super admin role (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update user role to super_admin
    user.role = UserRole.super_admin
    db.commit()
    db.refresh(user)
    
    return {
        "message": f"User '{user.username}' promoted to super admin successfully",
        "user": user_to_dict(user)
    }


@router.put("/users/{user_id}/demote-from-super-admin", status_code=200)
def demote_from_super_admin(
    user_id: int,
    admin_token=Depends(get_admin_from_token),
    db: Session = Depends(get_db)
):
    """Demote a super admin to regular admin role (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.role != UserRole.super_admin:
        raise HTTPException(status_code=400, detail="User is not a super admin")
    
    # Demote to regular admin
    user.role = UserRole.admin
    db.commit()
    db.refresh(user)
    
    return {
        "message": f"User '{user.username}' demoted to admin successfully",
        "user": user_to_dict(user)
    }


@router.get("/super-admins", response_model=List[Dict[str, Any]])
def list_super_admins(
    admin_token=Depends(get_admin_from_token),
    db: Session = Depends(get_db)
):
    """Get list of all super admin users"""
    super_admins = db.query(User).filter(User.role == UserRole.super_admin).order_by(User.id.asc()).all()
    return [user_to_dict(user) for user in super_admins]


@router.get("/stats/users-by-role", response_model=Dict[str, Any])
def get_users_stats_by_role(
    admin_token=Depends(get_admin_from_token),
    db: Session = Depends(get_db)
):
    """Get statistics of users by role"""
    stats = {}
    
    # Count users by role
    for role in UserRole:
        count = db.query(User).filter(User.role == role).count()
        stats[role.value] = count
    
    # Also get active users count by role
    active_stats = {}
    for role in UserRole:
        count = db.query(User).filter(User.role == role, User.is_active == True).count()
        active_stats[role.value] = count
    
    return {
        "total_by_role": stats,
        "active_by_role": active_stats,
        "total_users": sum(stats.values()),
        "total_active_users": sum(active_stats.values())
    }


# =====================================================
# 🔹 ORGANIZATIONS — только для super_admin
# =====================================================

@router.get("/organizations", dependencies=[Depends(require_role("super_admin"))])
def list_organizations(db: Session = Depends(get_db)):
    return db.query(Organization).all()


@router.post("/organizations", dependencies=[Depends(require_role("super_admin"))])
def create_organization(name: str, description: str = None, db: Session = Depends(get_db)):
    if db.query(Organization).filter_by(name=name).first():
        raise HTTPException(status_code=400, detail="Organization already exists")
    org = Organization(name=name, description=description)
    db.add(org)
    db.commit()
    db.refresh(org)
    return {"message": "Organization created", "organization": org}


@router.delete("/organizations/{org_id}", dependencies=[Depends(require_role("super_admin"))])
def delete_organization(org_id: int, db: Session = Depends(get_db)):
    org = db.query(Organization).get(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    db.delete(org)
    db.commit()
    return {"message": "Organization deleted"}


# =====================================================
# 🔹 CLIENTS — super_admin видит всех, admin только своих
# =====================================================

@router.get("/clients")
def list_clients(
    db: Session = Depends(get_db),
    user=Depends(require_role("admin", "super_admin"))
):
    if user.role == UserRole.super_admin:
        return db.query(Client).all()
    return db.query(Client).filter(Client.id == user.client_id).all()


@router.post("/clients", dependencies=[Depends(require_role("super_admin"))])
def create_client(name: str, contact_email: str, organization_id: int = 1, db: Session = Depends(get_db)):
    if db.query(Client).filter_by(name=name).first():
        raise HTTPException(status_code=400, detail="Client already exists")
    client = Client(name=name, contact_email=contact_email, organization_id=organization_id)
    db.add(client)
    db.commit()
    db.refresh(client)
    return {"message": "Client created", "client": client}


@router.delete("/clients/{client_id}", dependencies=[Depends(require_role("super_admin"))])
def delete_client(client_id: int, db: Session = Depends(get_db)):
    client = db.query(Client).get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(client)
    db.commit()
    return {"message": "Client deleted"}


# =====================================================
# 🔹 DATABASES — видит только свой клиент или super_admin
# =====================================================

@router.get("/databases")
def list_databases(
    db: Session = Depends(get_db),
    user=Depends(require_role("admin", "super_admin"))
):
    if user.role == UserRole.super_admin:
        return db.query(ClientDatabase).all()
    return db.query(ClientDatabase).filter(ClientDatabase.client_id == user.client_id).all()


@router.post("/databases")
def add_database(
    name: str,
    description: str = None,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin", "super_admin"))
):
    client_id = user.client_id if user.role == UserRole.admin else None
    if client_id:
        new_db = ClientDatabase(name=name, description=description, client_id=client_id)
    else:
        raise HTTPException(status_code=403, detail="Super admin must specify client manually")

    db.add(new_db)
    db.commit()
    db.refresh(new_db)
    return {"message": "Database added", "database": new_db}


@router.delete("/databases/{database_id}")
def delete_database(
    database_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role("admin", "super_admin"))
):
    target = db.query(ClientDatabase).get(database_id)
    if not target:
        raise HTTPException(status_code=404, detail="Database not found")

    if user.role == UserRole.admin and target.client_id != user.client_id:
        raise HTTPException(status_code=403, detail="You cannot delete other clients' databases")

    db.delete(target)
    db.commit()
    return {"message": f"Database {target.name} deleted"}
