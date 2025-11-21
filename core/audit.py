import json
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timedelta


def log_unified(
    db: Session,
    user_id: Optional[int],
    user_role: Optional[str],
    action: str,
    request_type: str,  # 'auth', 'admin', 'sql_proxy'
    status: str,  # 'success', 'error', 'denied'
    tenant_id: Optional[str] = None,
    database_name: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    duration_ms: Optional[int] = None,
    error_message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
):

    from models.audit_log import AuditLog
    
    try:
        audit_entry = AuditLog(
            user_id=user_id,
            user_role=user_role,
            action=action,
            request_type=request_type,
            status=status,
            tenant_id=tenant_id,
            database_name=database_name,
            target_type=target_type,
            target_id=target_id,
            duration_ms=duration_ms,
            error_message=error_message,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.utcnow()
        )
        db.add(audit_entry)
        db.commit()
        return audit_entry
    except Exception as e:
        print(f"[AUDIT ERROR] Failed to log: {e}")
        db.rollback()
        return None


def log_access(
    db: Session,
    actor_user: Optional[object] = None,
    actor_role: Optional[str] = None,
    admin_token: Optional[object] = None,
    action: str = "",
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    details: Optional[dict] = None,
    success: bool = True,
    dedupe_seconds: Optional[int] = None,
):

    from models.access_audit import AccessAudit

    actor_user_id = None
    if hasattr(actor_user, 'id'):
        actor_user_id = getattr(actor_user, 'id')
    elif isinstance(actor_user, int):
        actor_user_id = actor_user

    actor_role_val = None
    if actor_role:
        actor_role_val = actor_role
    elif hasattr(actor_user, 'role'):
        try:
            actor_role_val = actor_user.role.value if hasattr(actor_user.role, 'value') else str(actor_user.role)
        except Exception:
            actor_role_val = str(getattr(actor_user, 'role', None))

    admin_token_val = None
    if hasattr(admin_token, 'token'):
        admin_token_val = getattr(admin_token, 'token')
    elif isinstance(admin_token, str):
        admin_token_val = admin_token

    details_text = None
    if details is not None:
        try:
            details_text = json.dumps(details, default=str)
        except Exception:
            details_text = str(details)

    # Deduplication: if requested, check for a recent identical record and return it instead of inserting a duplicate.
    if dedupe_seconds and dedupe_seconds > 0:
        try:
            cutoff = datetime.utcnow() - timedelta(seconds=dedupe_seconds)
            q = db.query(AccessAudit).filter(AccessAudit.created_at >= cutoff)
            if actor_user_id is not None:
                q = q.filter(AccessAudit.actor_user_id == actor_user_id)
            elif admin_token_val is not None:
                q = q.filter(AccessAudit.admin_token == admin_token_val)
            else:
                q = None

            if q is not None:
                q = q.filter(AccessAudit.action == action)
                # allow target_type/target_id to be None as well
                q = q.filter(AccessAudit.target_type == target_type)
                q = q.filter(AccessAudit.target_id == target_id)
                existing = q.order_by(AccessAudit.created_at.desc()).first()
                if existing:
                    return existing
        except Exception:
            # If dedupe check fails for any reason, continue and attempt to write the record.
            pass

    rec = AccessAudit(
        actor_user_id=actor_user_id,
        actor_role=actor_role_val,
        admin_token=admin_token_val,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details_text,
        success=bool(success),
    )

    db.add(rec)
    try:
        db.commit()
        db.refresh(rec)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    return rec
