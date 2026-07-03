from pydantic import BaseModel
from typing import Optional

class LeadIn(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    source: str = "Website Form"
    message: Optional[str] = None

class StatusUpdate(BaseModel):
    status: str
