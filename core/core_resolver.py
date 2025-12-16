from sqlalchemy.orm import Session
from fastapi import HTTPException
from models.tenant_registry import TenantRegistry
from models.client import Client
import httpx
from typing import Optional


class CoreResolver:

    @staticmethod
    def get_core_url(tenant_id: str, db: Session) -> str:
      
        client = db.query(Client).filter(
            Client.name.ilike(tenant_id)
        ).first()
        
        if not client:
            raise HTTPException(
                status_code=404,
                detail=f"Tenant '{tenant_id}' not found"
            )
        
        registry = db.query(TenantRegistry).filter(
            TenantRegistry.client_id == client.id,
            TenantRegistry.is_active == True
        ).first()
        
        if not registry:
            raise HTTPException(
                status_code=503,
                detail=f"No active Core service configured for tenant '{tenant_id}'"
            )
        
        return registry.core_url
    
    @staticmethod
    async def check_core_health(core_url: str, timeout: float = 5.0) -> bool:
        """Check if Core service is healthy"""
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{core_url}/health")
                return response.status_code == 200
        except Exception:
            return False
