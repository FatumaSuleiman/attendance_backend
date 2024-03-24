from enum import Enum
from sqlmodel import SQLModel
from typing import List, Optional
from datetime import date


class OneInvoiceResponse(SQLModel):
    id: int
    payment_status: str
    total_amount: str
    invoice_number: str
    start_date: Optional[date]
    end_date: Optional[date]
    entry_period_id:int


class InvoicesResponse(SQLModel):
    results: int
    invoices: List[OneInvoiceResponse]


class InvoiceByDate(SQLModel):
    invoice_number: str
    start_date: date
    end_date: date
    institution_name: str
    number_of_attendance: float
    rate: str
    total: float


class FetchStatus(str, Enum):
    """Fetch status"""
    data = 'data'
    download = 'download'

class FetchEmployees(str, Enum):
    """Fetch Employes"""
    download = 'download'

    


class PeriodType(str, Enum):
    """ Period Types """
    Weekly = 'Weekly'
    Monthly = 'Monthly'
    Term = 'Term'
    Semester = 'Semester'
    Annually = 'Annually'
