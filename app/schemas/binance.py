from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, EmailStr


class ArchiveBackfillRequest(BaseModel):
    subaccount_email: EmailStr
    period_start: datetime
    period_end: datetime


class IncrementalSyncRequest(BaseModel):
    subaccount_email: EmailStr
    symbol: str
    period_start: datetime
    period_end: datetime