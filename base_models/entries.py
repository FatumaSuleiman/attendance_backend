from sqlmodel import SQLModel
from datetime import datetime as dt
from typing import Union
from fastapi import UploadFile


class ManualEntryBase(SQLModel):
    employee_id: int
    branch_id: int
    date_of_attendance: dt = dt.now().replace(hour=12, minute=0, second=0, microsecond=0)
    signature: Union[UploadFile, None] = None
