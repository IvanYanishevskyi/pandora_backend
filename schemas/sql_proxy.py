from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class SQLGenerateRequest(BaseModel):

    tenant_id: str = Field(...)
    database_name: str = Field(...)
    prompt: str = Field(...)
    core_token: str = Field(...)
    chat_id: Optional[str] = Field(None)


class SQLGenerateResponse(BaseModel):

    successo: bool
    spiegazione: Optional[str] = None
    query_riformulata: Optional[str] = None
    sql: Optional[str] = None
    conteggio_righe: Optional[int] = None
    risultati: Optional[List[Dict[str, Any]]] = None
    link: Optional[str] = None
    error: Optional[str] = None
