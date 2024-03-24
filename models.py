import sqlalchemy as sa
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Float, Boolean, JSON
from sqlalchemy.sql import func
from sqlmodel import Field, Session, SQLModel, create_engine, select, Relationship
from sqlalchemy.ext.declarative import declarative_base
from typing import Optional, List, Union, Dict
from datetime import datetime, date
import uuid as pk
from fastapi import UploadFile
from sqlalchemy.dialects.postgresql import JSON


Base = declarative_base()

class Institution(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, nullable=False)
    uuid: pk.UUID = Field(default_factory=pk.uuid4, nullable=False)
    commissionType: str = Field(nullable=True)
    commission: str = Field(nullable=True)
    active_status: Optional[str] = Field(nullable=True)
    active_status_reason: Optional[str] = Field(nullable=True)
    rate_type: str = Field(nullable=True)
    name: str = Field(nullable=True)
    phone: str = Field(nullable=True)
    email: str = Field(nullable=True)
    address: Optional[str] = Field(nullable=True)
    deletedStatus: bool = Field(default=False)
    invoicing_period_type: str = Field(nullable=False)


class Contract(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, nullable=False)
    uuid: pk.UUID = Field(default_factory=pk.uuid4, nullable=False)
    current: bool = Field(nullable=False, default=False)
    attachment: Optional[str] = Field(nullable=True)
    rate: str = Field(nullable=True, default=0.0)
    expirationDate: datetime = Field(nullable=False)
    deletedStatus: bool = Field(default=False)
    due_date_days: int = Field(nullable=False, default=0)
    institution_id: Optional[int] = Field(nullable=True, default=None, foreign_key='institution.id')
    services:Optional[List]=Field(default=[],sa_column=Column(JSON))
    


class Employee(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, nullable=False)
    uuid: pk.UUID = Field(default_factory=pk.uuid4, nullable=False)
    firstName: str = Field(nullable=True)
    lastName: str = Field(nullable=True)
    gender: str = Field(nullable=True)
    photo: Optional[str] = Field(nullable=True)
    email: str = Field(nullable=True)
    phone: str = Field(nullable=True)
    title: str = Field(nullable=True)
    active_status: Optional[str] = Field(nullable=True)
    deletedStatus: bool = Field(default=False)
    institution_id: Optional[int] = Field(nullable=True, default=None, foreign_key='institution.id')
    referenceName: str = Field(nullable=False)
    services:Optional[List]=Field(default=[],sa_column=Column(JSON))
    

class Service(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, nullable=False)
    uuid: pk.UUID = Field(default_factory=pk.uuid4, nullable=False)
    name: str = Field(nullable=True)
    description: str = Field(nullable=True)
    is_available: bool = Field(default=True)
    deleted_status: bool = Field(default=False)


class EntryPeriod(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, nullable=False)
    uuid: pk.UUID = Field(default_factory=pk.uuid4, nullable=False)
    startDate: datetime = Field(nullable=False)
    endDate: datetime = Field(nullable=False)
    deletedStatus: bool = Field(default=False)
    institution_id: Optional[int] = Field(nullable=True, default=None, foreign_key='institution.id')
   

class Invoice(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, nullable=False)
    uuid: pk.UUID = Field(default_factory=pk.uuid4, nullable=False)
    payment_status: str = Field(nullable=False)
    payment_confirmed_at: datetime = Field(nullable=True)
    payment_confirmed_by: str = Field(nullable=True)
    deletedStatus: bool = Field(default=False)
    total_amount: str = Field(nullable=False)
    invoice_number: str = Field(nullable=False)
    invoice_notes: Optional[str] = Field(nullable=True)
    invoice_ebm: Optional[str] = Field(nullable=True)
    entry_period_id: Optional[int] = Field(default=None, foreign_key='entryperiod.id')
    invoiceEmailSent: Optional[bool] = Field(nullable=True, default=False)
    invoiceEmailSentAt: Optional[datetime] = Field(nullable=True)
    invoiceEmailSentBy: Optional[str] = Field(nullable=True)
    last_updated_at: Union[datetime, None] = Field(
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()))


class EmployeeEntry(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, nullable=False)
    uuid: pk.UUID = Field(default_factory=pk.uuid4, nullable=False)
    signature: Optional[str] = Field(nullable=True)
    signed: bool = Field(nullable=False, default=False)
    signedAt: Optional[datetime] = Field(nullable=True)
    deletedStatus: bool = Field(default=False)
    employee_id: Optional[int] = Field(nullable=True, default=None, foreign_key='employee.id')
    entry_period_id: Optional[int] = Field(default=None, foreign_key='entryperiod.id')
    doneAt: datetime = Field(nullable=True)
    branchName: str = Field(nullable=False)
    branchId: str = Field(nullable=False)
    has_expired: bool = Field(default=False)
    image: Optional[str] = Field(nullable=True)
    service_id:Optional[int] = Field(nullable=True)

class User(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, nullable=False)
    uuid: pk.UUID = Field(default_factory=pk.uuid4, nullable=False)
    firstName: str = Field(default=None, index=True)
    lastName: str = Field(default=None, index=True)
    userName: str = Field(index=True)
    email: str = Field(index=True)
    password: str = Field(index=True)
    deletedStatus: bool = Field(default=False)
    is_admin: bool = Field(default=False)
    is_superuser: bool = Field(default=False)
    is_staff: bool = Field(default=False)
    is_default_password: bool = Field(default=False)
    is_active: bool = Field(default=True)
    referenceId: Optional[str] = Field(nullable=True)
    referenceName: Optional[str] = Field(nullable=True)
    role: Optional[str] = Field(nullable=True)


class SupportingDocument(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, nullable=False)
    uuid: pk.UUID = Field(default_factory=pk.uuid4, nullable=False)
    name: str = Field(default=None, index=True)
    description: Optional[str] = Field(nullable=True)
    expirationDate: datetime = Field(nullable=False)
    path: Optional[str] = Field(nullable=True)
    is_active: bool = Field(default=True)
    deletedStatus: bool = Field(default=False)


class Branch(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True, nullable=False)
    uuid: pk.UUID = Field(default_factory=pk.uuid4, nullable=False)
    name: str = Field(default=None, index=True)
    description: str = Field(nullable=True)
    deletedStatus: bool = Field(default=False)
    services:Optional[List]=Field(default=[],sa_column=Column(JSON))


class InvoiceBase(SQLModel):
    payment_status: str


class InvoiceNote(SQLModel):
    invoice_notes: str


class UserLogin(SQLModel):
    username: str
    password: str


class InstitutionBase(SQLModel):
    name: str
    phone: str
    email: str
    address: str
    commissionType: str
    commission: str
    rate_type: str
    invoicing_period_type: str

class Serviceb(SQLModel):
     service_id:int
     service_rate:str
    # service_name:str
class Servicebr(SQLModel):
    service_id: int
   
class EmployeeBase(SQLModel):
    firstName: str
    lastName: str
    gender: str
    email: str
    phone: str
    title: str
    services:List=[]

class ContractBase(SQLModel):
    expirationDate: date
    due_date_days: int
    rate:Optional[str]
    services:List[Serviceb]
    

class ServiceBase(SQLModel):
    name: str
    description: str


class NewUserBase(SQLModel):
    firstName: str
    lastName: str
    email: str


class StaffUserBase(SQLModel):
    firstName: str
    lastName: str
    email: str
    role: str


class ChangePasswordBase(SQLModel):
    password: str
    confirm_password: str


class UserBase(SQLModel):
    firstName: str
    lastName: str
    email: str
    password: str
    confirm_password: str


class InstitutionDeactivate(SQLModel):
    deactivation_reason: str


class BranchBase(SQLModel):
    name: str
    description: str
    services:List[Servicebr]


class branchData(SQLModel):
    branch_id: int


class DocumentBase(SQLModel):
    name: str
    description: str
    expirationDate: date
    is_active: bool


class checkEmployeeOnetimeEntry(SQLModel):
    emp_id: int
    doneAt: datetime


class filterEntriesByDate(SQLModel):
    startDate: str
    endDate: str
class EmployeeS(SQLModel):
    services:List[Serviceb]

class EmployeeWithServiceBase(SQLModel):
    firstName: str
    lastName: str
    gender: str
    email: str
    phone: str
    title: str
    services:List[Serviceb]

class ContractS( SQLModel):
    services:List[Serviceb]

class BranchS(SQLModel):
    services:List[Servicebr]



class Servicec(SQLModel):
     service_id:Optional[int]
     service_rate:Optional[str]
     service_name:Optional[str]
     assigned:Optional[bool]
class ServiceCon(SQLModel):
    service_id:Optional[int]
    service_name:Optional[str]
    assigned:Optional[bool]
         