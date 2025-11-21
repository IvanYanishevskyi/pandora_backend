from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database.database import get_db
from core.dependencies import get_current_user
from schemas.sql_proxy import SQLGenerateRequest
from core.core_resolver import CoreResolver
from core.audit import log_unified
from models.user_database_access import UserDatabaseAccess
from models.client_database import ClientDatabase
import httpx
import time
from typing import Dict, Any

router = APIRouter(prefix="/v1/sql", tags=["SQL Proxy"])


async def check_database_access(user: Dict[str, Any], database_name: str, db: Session):

    if user.get("role") == "super_admin":
        return True
    
    user_id = user.get("id")
    
    db_record = db.query(ClientDatabase).filter(
        ClientDatabase.name == database_name
    ).first()
    
    if not db_record:
        raise HTTPException(
            status_code=404,
            detail=f"Database '{database_name}' not found"
        )
    
    access = db.query(UserDatabaseAccess).filter(
        UserDatabaseAccess.user_id == user_id,
        UserDatabaseAccess.database_id == db_record.id,
        UserDatabaseAccess.can_read == True
    ).first()
    
    if not access:
        raise HTTPException(
            status_code=403,
            detail=f"No access to database '{database_name}'"
        )
    
    return True


@router.post("/generate")
async def generate_sql(
    request: SQLGenerateRequest,
    http_request: Request,
    user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
  
    start_time = time.time()
    user_id = user.id if hasattr(user, 'id') else user.get("id")
    user_role = user.role if hasattr(user, 'role') else user.get("role")
    if hasattr(user_role, 'value'):
        user_role = user_role.value
    
    try:
        await check_database_access(user, request.database_name, db)
        
        core_url = CoreResolver.get_core_url(request.tenant_id, db)
        
        client_link = f"/{request.tenant_id.lower()}/chat/{request.database_name}"
        target_url = f"{core_url}{client_link}/"
        
        core_request_body = {
            "chat_id": request.chat_id or "default_chat",
            "messaggio": request.prompt,
            "user_id": user_id,
            "timezone": "UTC"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            core_response = await client.post(
                target_url,
                json=core_request_body,
                headers={
                    "Authorization": f"Bearer {request.core_token}",
                    "Content-Type": "application/json",
                    "ngrok-skip-browser-warning": "true"
                }
            )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        if core_response.status_code != 200:
            log_unified(
                db=db,
                user_id=user_id,
                user_role=user_role,
                action="sql_generate",
                request_type="sql_proxy",
                status="error",
                tenant_id=request.tenant_id,
                database_name=request.database_name,
                duration_ms=duration_ms,
                error_message=f"Core returned {core_response.status_code}",
                ip_address=http_request.client.host if http_request.client else None,
                user_agent=http_request.headers.get("user-agent")
            )
            
            raise HTTPException(
                status_code=502,
                detail=f"Core service error: {core_response.status_code}"
            )
        
        result = core_response.json()
        
        result["link"] = client_link
        
        log_unified(
            db=db,
            user_id=user_id,
            user_role=user_role,
            action="sql_generate",
            request_type="sql_proxy",
            status="success",
            tenant_id=request.tenant_id,
            database_name=request.database_name,
            duration_ms=duration_ms,
            details={
                "prompt": request.prompt[:100],
                "sql_generated": result.get("sql", "")[:200] if result.get("sql") else None
            },
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent")
        )
        
        return result
        
    except HTTPException:
        raise
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        
        log_unified(
            db=db,
            user_id=user_id,
            user_role=user_role,
            action="sql_generate",
            request_type="sql_proxy",
            status="error",
            tenant_id=request.tenant_id,
            database_name=request.database_name,
            duration_ms=duration_ms,
            error_message=str(e),
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("user-agent")
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "pandora-sql-proxy"}
