from fastapi import APIRouter, Depends, status, UploadFile, BackgroundTasks
from sqlmodel import select, col
from starlette.responses import JSONResponse
from base_models.entries import ManualEntryBase
from base_models.invoices import InvoicesResponse, OneInvoiceResponse, PeriodType
from invoice_report import checkEmployeeRawAdded
from models import (Institution, Service, Session, Employee, EmployeeEntry, EntryPeriod, Invoice, Contract,
                    Branch, checkEmployeeOnetimeEntry)
from database import engine, get_session
from auth import AuthHandler
import shutil
from dotenv import load_dotenv
import os
from datetime import datetime, date, timedelta
import random
import math
from Pindo import models as pindomodels
from fastapi.responses import FileResponse
from utils.export_to_excel import export_to_excel
from utils.entry_helper import employee_daily_entries
from utils.invoice_helper import update_invoice_amount

load_dotenv('.env')

entries_router = APIRouter(tags=["Entries"])
# ent_session=Session(bind=engine)

auth_handler = AuthHandler()


def rand_num():
    num = "145689876543"
    four_digits = ""
    for i in range(4):
        four_digits = four_digits + num[math.floor(random.random() * 10)]
    return four_digits


def get_first_date_of_current_month(year, month):
    """Return the first date of the month. """
    first_date = datetime(year, month, 1)
    return first_date


def get_last_date_of_month(year, month):
    """Return the last date of the month. """
    if month == 12:
        last_date = datetime(year, month, 31)
        print(last_date)
        return last_date
    else:
        last_date = datetime(year, month + 1, 1) + timedelta(days=-1)
        print(type(last_date))
        return last_date


def generate_invoice_number(institution):
    invoice_list = []
    with Session(engine) as ent_session:
        statement = select(Invoice)
        invoices = ent_session.exec(statement).all()
        # Get all invoices for the given institution
        for inv in invoices:
            period_statement = select(EntryPeriod).where(EntryPeriod.id == inv.entry_period_id,
                                                         EntryPeriod.institution_id == institution.id,
                                                         EntryPeriod.deletedStatus == False)
            entry_period = ent_session.exec(period_statement).first()
            if entry_period is not None:
                invoice_list.append(inv)

        if len(invoice_list) < 10:
            if len(invoice_list) == 0:
                number = "INV-" + str(institution.id) + "-001"
            else:
                number = "INV-" + str(institution.id) + "-00" + str(len(invoice_list) + 1)
        elif len(invoice_list) < 100:
            number = "INV-" + str(institution.id) + "-0" + str(len(invoice_list) + 1)
        else:
            number = "INV-" + str(institution.id) + "-" + str(len(invoice_list) + 1)
        return number


def get_employee_daily_entries(employee):
    list_entries = []
    with Session(engine) as ent_session:
        try:
            statement = select(EmployeeEntry).where(EmployeeEntry.deletedStatus == False,
                                                    EmployeeEntry.employee_id == employee.id)
            result = ent_session.exec(statement).all()

            if len(result) > 0:
                for r in result:
                    check_date = r.signedAt
                    if check_date.strftime('%Y-%m-%d') == datetime.now().strftime('%Y-%m-%d'):
                        list_entries.append(r)
                return list_entries
            else:
                return list_entries
        except Exception as e:
            print(e)
            return list_entries



@entries_router.post('/entries/{employee_id}/create')
async def create_employee_entry(employee_id: int, ent_session: Session = Depends(get_session),
                                user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Create Employee Entry."""

    try:
        new_employee_entry = ''
        statement = select(Employee).where(Employee.id == employee_id,
                                           Employee.deletedStatus == False)
        employee = ent_session.exec(statement).first()

        if user.referenceName == 'Branch' and not user.referenceId is None:
            branch_statement = select(Branch).where(Branch.id == user.referenceId,
                                                    Branch.deletedStatus == False)
            branch = ent_session.exec(branch_statement).first()
            if not employee is None:
                if employee.active_status == 'Active':
                    statement = select(Institution).where(Institution.id == employee.institution_id,
                                                          Institution.deletedStatus == False)
                    institution = ent_session.exec(statement).first()
                    if not institution is None and institution.active_status == 'Active':
                        if institution.invoicing_period_type == 'Weekly':
                            today = date.today()
                            start = today - timedelta(days=today.weekday())
                            end = start + timedelta(days=6)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if not entry_period is None:
                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=int(contract.rate)

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=entry_period.id, payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " this is your OTP: " + new_otp
                                pindomodels.PindoSMS.sendSMS(phone, text)

                            else:

                                new_entry_period = EntryPeriod(institution_id=institution.id,
                                                               startDate=datetime.combine(start,
                                                                                          datetime.min.time()),
                                                               endDate=datetime.combine(end,
                                                                                        datetime.min.time()))
                                ent_session.add(new_entry_period)
                                ent_session.commit()
                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=int(contract.rate)

                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=new_entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == new_entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=new_entry_period.id,
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " this is your OTP: " + new_otp
                                pindomodels.PindoSMS.sendSMS(phone, text)

                        elif institution.invoicing_period_type == PeriodType.Monthly:
                            today = datetime.now()
                            start = get_first_date_of_current_month(today.year, today.month)
                            end = get_last_date_of_month(today.year, today.month)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if entry_period is not None:
                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=int(contract.rate)

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " this is your OTP: " + new_otp
                                pindomodels.PindoSMS.sendSMS(phone, text)

                            else:
                                new_entry_period = EntryPeriod(institution_id=institution.id,
                                                               startDate=datetime.combine(start,
                                                                                          datetime.min.time()),
                                                               endDate=datetime.combine(end,
                                                                                        datetime.min.time()))
                                ent_session.add(new_entry_period)
                                ent_session.commit()

                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=new_entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=int(contract.rate)

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == new_entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=new_entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " this is your OTP: " + new_otp
                                pindomodels.PindoSMS.sendSMS(phone, text)


                        elif institution.invoicing_period_type == 'Term':
                            current_date = datetime.now()
                            current_quarter = round((current_date.month - 1) / 3 + 1)
                            start = datetime(current_date.year, 3 * current_quarter - 2, 1)
                            end = datetime(current_date.year, 3 * current_quarter + 1,
                                           1) + timedelta(days=-1)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if not entry_period is None:
                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=int(contract.rate)

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " this is your OTP: " + new_otp
                                pindomodels.PindoSMS.sendSMS(phone, text)

                            else:
                                new_entry_period = EntryPeriod(institution_id=institution.id,
                                                               startDate=datetime.combine(start,
                                                                                          datetime.min.time()),
                                                               endDate=datetime.combine(end,
                                                                                        datetime.min.time()))
                                ent_session.add(new_entry_period)
                                ent_session.commit()

                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=new_entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=int(contract.rate)

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == new_entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=new_entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " this is your OTP: " + new_otp
                                pindomodels.PindoSMS.sendSMS(phone, text)


                        elif institution.invoicing_period_type == 'Semester':
                            current_date = datetime.now()
                            start = ''
                            end = ''
                            current_quarter = round((current_date.month - 1))
                            if current_quarter < 6:
                                start = datetime(current_date.year, 1, 1)
                                end = datetime(current_date.year, 6, 30)
                            else:
                                start = datetime(current_date.year, 6, 1)
                                end = datetime(current_date.year, 12, 31)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if not entry_period is None:
                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # Incrementing Invoice Amount
                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=int(contract.rate)

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " this is your OTP: " + new_otp
                                pindomodels.PindoSMS.sendSMS(phone, text)

                            else:
                                new_entry_period = EntryPeriod(institution_id=institution.id,
                                                               startDate=datetime.combine(start,
                                                                                          datetime.min.time()),
                                                               endDate=datetime.combine(end,
                                                                                        datetime.min.time()))
                                ent_session.add(new_entry_period)
                                ent_session.commit()

                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=new_entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=int(contract.rate)

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == new_entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=new_entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " this is your OTP: " + new_otp
                                pindomodels.PindoSMS.sendSMS(phone, text)


                        elif institution.invoicing_period_type == 'Annaly':
                            today = datetime.now()
                            start = date(date.today().year, 1, 1)
                            end = date(date.today().year, 12, 31)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if not entry_period is None:
                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # Incrementing Invoice Amount
                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=int(contract.rate)

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " this is your OTP: " + new_otp
                                pindomodels.PindoSMS.sendSMS(phone, text)

                            else:
                                new_entry_period = EntryPeriod(institution_id=institution.id,
                                                               startDate=datetime.combine(start,
                                                                                          datetime.min.time()),
                                                               endDate=datetime.combine(end,
                                                                                        datetime.min.time()))
                                ent_session.add(new_entry_period)
                                ent_session.commit()

                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=new_entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=int(contract.rate)

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == new_entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=new_entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " this is your OTP: " + new_otp
                                pindomodels.PindoSMS.sendSMS(phone, text)

                        return JSONResponse(content="Entry Created Successfuly",
                                            status_code=status.HTTP_200_OK)
                    else:
                        return JSONResponse(content="Institution was Not Found",
                                            status_code=status.HTTP_404_NOT_FOUND)
                else:
                    return JSONResponse(
                        content="Sorry, Employee with " + str(employee_id) + " Not Active",
                        status_code=status.HTTP_400_BAD_REQUEST)
            else:
                return JSONResponse(content="Employee with " + str(employee_id) + " Not Found",
                                    status_code=status.HTTP_404_NOT_FOUND)
        else:
            return JSONResponse(content="User Has no Permission To Perform This Action! ",
                                status_code=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@entries_router.post('/entries/manual_create')
async def create_employee_entry_manually(entry_data: ManualEntryBase = Depends(),
                                         ent_session: Session = Depends(get_session),
                                         user=Depends(auth_handler.get_current_user)):
    """ Endpoint to record employee attendance manually """

    try:
        statement = select(Employee).where(Employee.id == entry_data.employee_id,
                                           Employee.deletedStatus == False)
        employee = ent_session.exec(statement).first()

        if user.referenceName == 'Branch' and user.referenceId is not None:
            branch_statement = select(Branch).where(Branch.id == entry_data.branch_id,
                                                    Branch.deletedStatus == False)
            branch = ent_session.exec(branch_statement).first()
            if branch is None:
                return JSONResponse(content="Provided Branch does not exists",
                                    status_code=status.HTTP_400_BAD_REQUEST)

            if employee is not None:
                if employee.active_status == 'Active':
                    statement = select(Institution).where(Institution.id == employee.institution_id,
                                                          Institution.deletedStatus == False)
                    institution = ent_session.exec(statement).first()
                    if institution is not None and institution.active_status == 'Active':
                        if institution.invoicing_period_type == PeriodType.Weekly:
                            today = date.today()
                            start = today - timedelta(days=today.weekday())
                            end = start + timedelta(days=6)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if entry_period is not None:
                                checkNotPaid = True
                                statement = select(Invoice).where(Invoice.deletedStatus == False,
                                                                  Invoice.entry_period_id == entry_period.id)
                                invoice = ent_session.exec(statement).first()
                                statement = select(Contract).where(
                                    Contract.institution_id == institution.id,
                                    Contract.deletedStatus == False, Contract.current == True)
                                contract = ent_session.exec(statement).first()

                                if invoice is not None:
                                    if invoice.payment_status != "Pending":
                                        checkNotPaid = False

                                if checkNotPaid:
                                    if contract is not None:
                                        new_employee_entry = EmployeeEntry(
                                            signature=entry_data.signature.filename,
                                            signedAt=entry_data.date_of_attendance, signed=True,
                                            employee_id=employee.id,
                                            entry_period_id=entry_period.id, doneAt=datetime.now(),
                                            branchName=branch.name, branchId=branch.id)

                                        if entry_data.signature:
                                            if os.path.exists(os.environ[
                                                                  'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + entry_data.signature.filename

                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(entry_data.signature.file,
                                                                       buffer)
                                            else:
                                                os.mkdir(os.environ[
                                                             'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + entry_data.signature.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(entry_data.signature.file,
                                                                       buffer)
                                                new_employee_entry.image = file_path
                                        ent_session.add(new_employee_entry)
                                        ent_session.commit()

                                        # Checking for Incrementing Invoice Amount
                                        if len(get_employee_daily_entries(employee)) < 2:
                                            ins_statement = select(Institution).where(
                                                Institution.id == entry_period.institution_id,
                                                Institution.deletedStatus == False)
                                            institution = ent_session.exec(ins_statement).first()

                                            amount = 0
                                            if institution.rate_type == 'Individual':
                                                amount = int(employee.individualRate)
                                            else:

                                                amount = int(contract.rate)

                                            statement = select(Invoice).where(
                                                Invoice.entry_period_id == entry_period.id,
                                                Invoice.deletedStatus == False)
                                            invoice = ent_session.exec(statement).first()
                                            if invoice is None:
                                                # Increment Invoice Amount
                                                new_invoice = Invoice(
                                                    invoice_number=generate_invoice_number(
                                                        institution),
                                                    entry_period_id=entry_period.id,
                                                    payment_status='Pending', total_amount=amount)
                                                ent_session.add(new_invoice)
                                                ent_session.commit()
                                            else:
                                                invoice.total_amount = int(
                                                    invoice.total_amount) + amount
                                                ent_session.add(invoice)
                                                ent_session.commit()
                                    else:
                                        return JSONResponse(
                                            content="There is no active contract for the institution of the employee",
                                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                else:
                                    return JSONResponse(content="Can't Sign. Invoice looks paid",
                                                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                            else:
                                statement = select(Contract).where(
                                    Contract.institution_id == institution.id,
                                    Contract.deletedStatus == False, Contract.current == True)
                                contract = ent_session.exec(statement).first()
                                if contract is not None:
                                    entry_period = EntryPeriod(institution_id=institution.id,
                                                               startDate=datetime.combine(start,
                                                                                          datetime.min.time()),
                                                               endDate=datetime.combine(end,
                                                                                        datetime.min.time()))
                                    ent_session.add(entry_period)
                                    ent_session.commit()

                                    new_employee_entry = EmployeeEntry(
                                        signature=entry_data.signature.filename,
                                        signedAt=entry_data.date_of_attendance, signed=True,
                                        employee_id=employee.id, entry_period_id=entry_period.id,
                                        doneAt=datetime.now(), branchName=branch.name,
                                        branchId=branch.id)

                                    if entry_data.signature:
                                        if os.path.exists(os.environ[
                                                              'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                            file_path = os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                new_employee_entry.uuid) + '_' + entry_data.signature.filename

                                            with open(f'{file_path}', 'wb') as buffer:
                                                shutil.copyfileobj(entry_data.signature.file,
                                                                   buffer)
                                        else:
                                            os.mkdir(os.environ[
                                                         'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                            file_path = os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                new_employee_entry.uuid) + '_' + entry_data.signature.filename
                                            with open(f'{file_path}', 'wb') as buffer:
                                                shutil.copyfileobj(entry_data.signature.file,
                                                                   buffer)
                                            new_employee_entry.image = file_path

                                    ent_session.add(new_employee_entry)
                                    ent_session.commit()

                                    # Checking for Incrementing Invoice Amount
                                    if len(get_employee_daily_entries(employee)) < 2:
                                        ins_statement = select(Institution).where(
                                            Institution.id == entry_period.institution_id,
                                            Institution.deletedStatus == False)
                                        institution = ent_session.exec(ins_statement).first()

                                        if institution.rate_type == 'Individual':
                                            amount = int(employee.individualRate)
                                        else:
                                            amount = int(contract.rate)

                                        statement = select(Invoice).where(
                                            Invoice.entry_period_id == entry_period.id,
                                            Invoice.deletedStatus == False)
                                        invoice = ent_session.exec(statement).first()
                                        if invoice is None:
                                            # Increment Invoice Amount
                                            new_invoice = Invoice(
                                                invoice_number=generate_invoice_number(institution),
                                                entry_period_id=entry_period.id,
                                                payment_status='Pending', total_amount=amount)
                                            ent_session.add(new_invoice)
                                            ent_session.commit()
                                        else:
                                            invoice.total_amount = int(
                                                invoice.total_amount) + amount
                                            ent_session.add(invoice)
                                            ent_session.commit()
                                else:
                                    return JSONResponse(
                                        content="There is no active contract for the institution of the employee",
                                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                        elif institution.invoicing_period_type == PeriodType.Monthly:
                            attendance_day = entry_data.date_of_attendance
                            start = get_first_date_of_current_month(attendance_day.year,
                                                                    attendance_day.month)
                            end = get_last_date_of_month(attendance_day.year, attendance_day.month)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if entry_period is not None:
                                checkNotPaid = True
                                statement = select(Invoice).where(Invoice.deletedStatus == False,
                                                                  Invoice.entry_period_id == entry_period.id)
                                invoice = ent_session.exec(statement).first()
                                statement = select(Contract).where(
                                    Contract.institution_id == institution.id,
                                    Contract.deletedStatus == False, Contract.current == True)
                                contract = ent_session.exec(statement).first()

                                if invoice is not None:
                                    if invoice.payment_status != "Pending":
                                        checkNotPaid = False

                                if checkNotPaid:
                                    if contract is not None:
                                        new_employee_entry = EmployeeEntry(
                                            signature=entry_data.signature,
                                            signedAt=entry_data.date_of_attendance, signed=True,
                                            employee_id=employee.id,
                                            entry_period_id=entry_period.id, doneAt=datetime.now(),
                                            branchName=branch.name, branchId=branch.id)

                                        if entry_data.signature:
                                            if os.path.exists(os.environ[
                                                                  'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + entry_data.signature.filename

                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(entry_data.signature.file,
                                                                       buffer)
                                            else:
                                                os.mkdir(os.environ[
                                                             'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + entry_data.signature.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(entry_data.signature.file,
                                                                       buffer)
                                                new_employee_entry.image = file_path
                                        ent_session.add(new_employee_entry)
                                        ent_session.commit()

                                        # Checking for Incrementing Invoice Amount
                                        if employee_daily_entries(new_employee_entry) < 2:
                                            ins_statement = select(Institution).where(
                                                Institution.id == entry_period.institution_id,
                                                Institution.deletedStatus == False)
                                            institution = ent_session.exec(ins_statement).first()

                                            if institution.rate_type == 'Individual':
                                                amount = int(employee.individualRate)
                                            else:
                                                amount = int(contract.rate)

                                            statement = select(Invoice).where(
                                                Invoice.entry_period_id == entry_period.id,
                                                Invoice.deletedStatus == False)
                                            invoice = ent_session.exec(statement).first()
                                            if invoice is None:
                                                # Increment Invoice Amount
                                                new_invoice = Invoice(
                                                    invoice_number=generate_invoice_number(
                                                        institution),
                                                    entry_period_id=entry_period.id,
                                                    payment_status='Pending', total_amount=amount)
                                                ent_session.add(new_invoice)
                                                ent_session.commit()
                                            else:
                                                invoice.total_amount = update_invoice_amount(
                                                    entry_period.id, amount)

                                                ent_session.add(invoice)
                                                ent_session.commit()
                                    else:
                                        return JSONResponse(
                                            content="There is no active contract for the institution of the employee",
                                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                else:
                                    return JSONResponse(content="Can't Sign. Invoice looks paid",
                                                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                            else:
                                statement = select(Contract).where(
                                    Contract.institution_id == institution.id,
                                    Contract.deletedStatus == False, Contract.current == True)
                                contract = ent_session.exec(statement).first()
                                if contract is not None:
                                    entry_period = EntryPeriod(institution_id=institution.id,
                                                               startDate=datetime.combine(start,
                                                                                          datetime.min.time()),
                                                               endDate=datetime.combine(end,
                                                                                        datetime.min.time()))
                                    ent_session.add(entry_period)
                                    ent_session.commit()

                                    new_employee_entry = EmployeeEntry(
                                        signature=entry_data.signature,
                                        signedAt=entry_data.date_of_attendance, signed=True,
                                        employee_id=employee.id, entry_period_id=entry_period.id,
                                        doneAt=datetime.now(), branchName=branch.name,
                                        branchId=branch.id)

                                    if entry_data.signature:
                                        if os.path.exists(os.environ[
                                                              'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                            file_path = os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                new_employee_entry.uuid) + '_' + entry_data.signature.filename

                                            with open(f'{file_path}', 'wb') as buffer:
                                                shutil.copyfileobj(entry_data.signature.file,
                                                                   buffer)
                                        else:
                                            os.mkdir(os.environ[
                                                         'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                            file_path = os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                new_employee_entry.uuid) + '_' + entry_data.signature.filename
                                            with open(f'{file_path}', 'wb') as buffer:
                                                shutil.copyfileobj(entry_data.signature.file,
                                                                   buffer)
                                            new_employee_entry.image = file_path

                                    ent_session.add(new_employee_entry)
                                    ent_session.commit()

                                    # Checking for Incrementing Invoice Amount
                                    if employee_daily_entries(new_employee_entry) < 2:
                                        ins_statement = select(Institution).where(
                                            Institution.id == entry_period.institution_id,
                                            Institution.deletedStatus == False)
                                        institution = ent_session.exec(ins_statement).first()

                                        if institution.rate_type == 'Individual':
                                            amount = int(employee.individualRate)
                                        else:
                                            amount = int(contract.rate)

                                        statement = select(Invoice).where(
                                            Invoice.entry_period_id == entry_period.id,
                                            Invoice.deletedStatus == False)
                                        invoice = ent_session.exec(statement).first()
                                        if invoice is None:
                                            # Increment Invoice Amount
                                            new_invoice = Invoice(
                                                invoice_number=generate_invoice_number(institution),
                                                entry_period_id=entry_period.id,
                                                payment_status='Pending', total_amount=amount)
                                            ent_session.add(new_invoice)
                                            ent_session.commit()
                                        else:
                                            invoice.total_amount = update_invoice_amount(
                                                entry_period.id, amount)
                                            ent_session.add(invoice)
                                            ent_session.commit()
                                else:
                                    return JSONResponse(
                                        content="There is no active contract for the institution of the employee",
                                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                        elif institution.invoicing_period_type == PeriodType.Term:
                            current_date = datetime.now()
                            current_quarter = round((current_date.month - 1) / 3 + 1)
                            start = datetime(current_date.year, 3 * current_quarter - 2, 1)
                            end = datetime(current_date.year, 3 * current_quarter + 1,
                                           1) + timedelta(days=-1)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if entry_period is not None:
                                new_employee_entry = EmployeeEntry(signature=entry_data.signature,
                                                                   signedAt=entry_data.date_of_attendance,
                                                                   signed=True,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()
                            else:
                                new_entry_period = EntryPeriod(institution_id=institution.id,
                                                               startDate=datetime.combine(start,
                                                                                          datetime.min.time()),
                                                               endDate=datetime.combine(end,
                                                                                        datetime.min.time()))
                                ent_session.add(new_entry_period)
                                ent_session.commit()

                                new_employee_entry = EmployeeEntry(signature=entry_data.signature,
                                                                   signedAt=entry_data.date_of_attendance,
                                                                   signed=True,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=new_entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == new_entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=new_entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                        elif institution.invoicing_period_type == PeriodType.Semester:
                            current_date = datetime.now()
                            start = ''
                            end = ''
                            current_quarter = round((current_date.month - 1))
                            if current_quarter < 6:
                                start = datetime(current_date.year, 1, 1)
                                end = datetime(current_date.year, 6, 30)
                            else:
                                start = datetime(current_date.year, 6, 1)
                                end = datetime(current_date.year, 12, 31)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if entry_period is not None:
                                new_employee_entry = EmployeeEntry(signature=entry_data.signature,
                                                                   signedAt=entry_data.date_of_attendance,
                                                                   signed=True,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()
                            else:
                                new_entry_period = EntryPeriod(institution_id=institution.id,
                                                               startDate=datetime.combine(start,
                                                                                          datetime.min.time()),
                                                               endDate=datetime.combine(end,
                                                                                        datetime.min.time()))
                                ent_session.add(new_entry_period)
                                ent_session.commit()

                                new_employee_entry = EmployeeEntry(signature=entry_data.signature,
                                                                   signedAt=entry_data.date_of_attendance,
                                                                   signed=True,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=new_entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == new_entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=new_entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                        elif institution.invoicing_period_type == PeriodType.Annually:
                            start = date(date.today().year, 1, 1)
                            end = date(date.today().year, 12, 31)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if entry_period is not None:
                                new_employee_entry = EmployeeEntry(signature=entry_data.signature,
                                                                   signedAt=entry_data.date_of_attendance,
                                                                   signed=True,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()
                            else:
                                new_entry_period = EntryPeriod(institution_id=institution.id,
                                                               startDate=datetime.combine(start,
                                                                                          datetime.min.time()),
                                                               endDate=datetime.combine(end,
                                                                                        datetime.min.time()))
                                ent_session.add(new_entry_period)
                                ent_session.commit()

                                new_employee_entry = EmployeeEntry(signature=entry_data.signature,
                                                                   signedAt=entry_data.date_of_attendance,
                                                                   signed=True,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=new_entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == new_entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=new_entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                        return JSONResponse(content="Entry Created Successfully",
                                            status_code=status.HTTP_200_OK)
                    else:
                        return JSONResponse(content="Institution was not Found",
                                            status_code=status.HTTP_404_NOT_FOUND)
                else:
                    return JSONResponse(content="Sorry, Employee with " + str(
                        entry_data.employee_id) + " Not Active",
                                        status_code=status.HTTP_400_BAD_REQUEST)
            else:
                return JSONResponse(
                    content="Employee with " + str(entry_data.employee_id) + " Not Found",
                    status_code=status.HTTP_404_NOT_FOUND)
        else:
            return JSONResponse(content="User Has no Permission To Perform This Action! ",
                                status_code=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@entries_router.get('/entries/{entry_id}/', response_model=EmployeeEntry)
async def fetch_entry_detail(entry_id: int, ent_session: Session = Depends(get_session),
                             user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Return Employee Entry Detail """

    try:
        statement = select(EmployeeEntry).where(EmployeeEntry.id == entry_id,
                                                EmployeeEntry.deletedStatus == False)
        result = ent_session.exec(statement).first()
        if result is not None:
            return result
        else:
            return JSONResponse(content="Employee Entry with " + str(entry_id) + " Not Found",
                                status_code=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@entries_router.get('/entries/daily/all')
async def fetch_daily_entry(ent_session: Session = Depends(get_session),
                            user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Return current day Employee Entries  """

    try:
        list_entries = []
        statement = select(EmployeeEntry).where(EmployeeEntry.deletedStatus == False)
        # statement = select(EmployeeEntry)
        result = ent_session.exec(statement).all()

        if result is not None:
            for r in result:
                if r.signedAt:
                    check_date = r.signedAt
                    if check_date.strftime('%Y-%m-%d') == datetime.now().strftime('%Y-%m-%d'):
                        # list_entries.append(r)
                        st = select(Employee).where(Employee.id == r.employee_id,
                                                    Employee.deletedStatus == False)
                        emp = ent_session.exec(st).first()
                        if not emp is None:
                            st1 = select(Institution).where(Institution.id == emp.institution_id,
                                                            Institution.deletedStatus == False)
                            inst = ent_session.exec(st1).first()
                            data = {'id': r.id, 'firstName': emp.firstName,
                                    'lastName': emp.lastName, 'phone': emp.phone,
                                    'signedAt': str(r.signedAt), 'signature': r.signature,
                                    'branchName': r.branchName, 'image': r.image,
                                    'doneAt': r.doneAt, 'institution': inst.name,
                                    'signed': r.signed, 'location': r.branchName}
                            list_entries.append(data)
                else:
                    continue
            return list_entries
        else:
            return JSONResponse(content="No Data Found", status_code=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@entries_router.put('/entries/{entry_id}/validate', response_model=EmployeeEntry)
async def validate_employee_entry(entry_id: int, ent_session: Session = Depends(get_session),
                                  user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Validate Employee Entry """

    try:
        statement = select(EmployeeEntry).where(EmployeeEntry.id == entry_id,
                                                EmployeeEntry.deletedStatus == False)
        result = ent_session.exec(statement).first()
        if result is not None:
            result.signed = True
            result.signedAt = datetime.now()
            ent_session.add(result)
            ent_session.commit()

            return result
        else:
            return JSONResponse(content="Employee Entry with " + str(entry_id) + " Not Found",
                                status_code=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@entries_router.get('/employees/{employee_id}/entries')
async def fetch_employee_entries(employee_id: int, ent_session: Session = Depends(get_session),
                                 user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Return Employee Entry which are not Signed """

    try:
        statement = select(EmployeeEntry).where(EmployeeEntry.employee_id == employee_id,
                                                EmployeeEntry.deletedStatus == False,
                                                EmployeeEntry.signed == False)
        result = ent_session.exec(statement).all()
        if result is not None:
            return result
        else:
            return JSONResponse(content="Employee with " + str(employee_id) + " Not Found",
                                status_code=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@entries_router.put('/entries/{entry_id}/validate/{signature}/entry')
async def validate_employee_entry_by_signature(entry_id: int, signature: str,
                                               ent_session: Session = Depends(get_session),
                                               user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Validate Employee Entry """

    try:
        statement = select(EmployeeEntry).where(EmployeeEntry.id == entry_id,
                                                EmployeeEntry.signature == signature,
                                                EmployeeEntry.deletedStatus == False)
        result = ent_session.exec(statement).first()
        if result is not None:
            if result.signed:
                return JSONResponse(content="This OTP " + signature + "is Already Signed.",
                                    status_code=status.HTTP_400_BAD_REQUEST)
            else:
                if result.has_expired:
                    return JSONResponse(content="This OTP " + signature + "has Expired.",
                                        status_code=status.HTTP_400_BAD_REQUEST)
                else:
                    if (datetime.now().minute - result.doneAt.minute) > 3:
                        result.has_expired = True
                        ent_session.add(result)
                        ent_session.commit()
                        return JSONResponse(content="This OTP " + signature + "has Expired.",
                                            status_code=status.HTTP_400_BAD_REQUEST)
                    else:
                        emp_statement = select(Employee).where(Employee.id == result.employee_id,
                                                               Employee.deletedStatus == False)
                        employee = ent_session.exec(emp_statement).first()

                        if len(get_employee_daily_entries(employee)) < 2:
                            # Increase Invoice Amount
                            statement = select(EntryPeriod).where(
                                EntryPeriod.id == result.entry_period_id,
                                EntryPeriod.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()

                            ins_statement = select(Institution).where(
                                Institution.id == entry_period.institution_id,
                                Institution.deletedStatus == False)
                            institution = ent_session.exec(ins_statement).first()

                            amount = 0
                            if institution.rate_type == 'Individual':
                                amount = int(employee.individualRate)
                            else:
                                statement = select(Contract).where(
                                    Contract.institution_id == institution.id,
                                    Contract.deletedStatus == False)
                                contract = ent_session.exec(statement).first()
                                amount = int(contract.rate)

                            inv_statement = select(Invoice).where(
                                Invoice.entry_period_id == entry_period.id,
                                Invoice.deletedStatus == False)
                            invoice = ent_session.exec(inv_statement).first()
                            if invoice is not None:
                                invoice.total_amount = int(invoice.total_amount) + amount
                                ent_session.add(invoice)
                                ent_session.commit()
                            else:
                                new_invoice = Invoice(
                                    invoice_number=generate_invoice_number(institution),
                                    entry_period_id=entry_period.id, total_amount=amount,
                                    payment_status='Pending')
                                ent_session.add(new_invoice)
                                ent_session.commit()

                        result.signed = True
                        result.signedAt = datetime.now()
                        ent_session.add(result)
                        ent_session.commit()
            return result
        else:
            return JSONResponse(content="Employee Entry with " + str(entry_id) + " Not Found",
                                status_code=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@entries_router.get('/employees/{employee_id}/monthly_entries/')
async def fetch_employee_monthly_entries(employee_id: int,
                                         ent_session: Session = Depends(get_session),
                                         user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Return Employee Entry which are not Signed """

    try:
        today = datetime.now()
        start = get_first_date_of_current_month(today.year, today.month)
        end = get_last_date_of_month(today.year, today.month)

        statement = select(EmployeeEntry).where(EmployeeEntry.employee_id == employee_id,
                                                EmployeeEntry.signedAt > start,
                                                EmployeeEntry.signedAt < end,
                                                EmployeeEntry.deletedStatus == False)
        result = ent_session.exec(statement).all()
        if result is not None:
            return result
        else:
            return JSONResponse(content="Employee with " + str(employee_id) + " Not Found",
                                status_code=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@entries_router.post('/entries/{entry_id}/resend/otp/')
async def resend_Otp(entry_id: int, ent_session: Session = Depends(get_session),
                     user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Validate Employee Entry """

    try:
        statement = select(EmployeeEntry).where(EmployeeEntry.id == entry_id,
                                                EmployeeEntry.deletedStatus == False)
        result = ent_session.exec(statement).first()
        statement = select(Employee).where(Employee.id == result.employee_id,
                                           Employee.deletedStatus == False)
        employee = ent_session.exec(statement).first()
        if result is not None:
            # Send SMS To Employee
            first_three = employee.phone[0:3]
            phone = employee.phone
            if first_three != "+25":
                if first_three == "250":
                    phone = "+" + employee.phone
                else:
                    first_two = employee.phone[0:2]
                    if first_two == "07":
                        phone = "+25" + employee.phone

            text = "Hi," + employee.firstName + " this is your OTP: " + result.signature
            pindomodels.PindoSMS.sendSMS(phone, text)
            return result
        else:
            return JSONResponse(content="Employee Entry with " + str(entry_id) + " Not Found",
                                status_code=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@entries_router.post('/entries/{employee_id}/create/validation_link/')
async def create_employee_entry_and_validation_link(employee_id: int,
                                                    ent_session: Session = Depends(get_session),
                                                    user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Create Employee Entry. and Send Validation """

    try:
        new_employee_entry = ''
        statement = select(Employee).where(Employee.id == employee_id,
                                           Employee.deletedStatus == False)
        employee = ent_session.exec(statement).first()
        if user.referenceName == 'Branch' and not user.referenceId is None:
            branch_statement = select(Branch).where(Branch.id == user.referenceId,
                                                    Branch.deletedStatus == False)
            branch = ent_session.exec(branch_statement).first()
            if not employee is None:
                if employee.active_status == 'Active':
                    statement = select(Institution).where(Institution.id == employee.institution_id,
                                                          Institution.deletedStatus == False)
                    institution = ent_session.exec(statement).first()
                    if not institution is None and institution.active_status == 'Active':
                        if institution.invoicing_period_type == 'Weekly':
                            today = date.today()
                            start = today - timedelta(days=today.weekday())
                            end = start + timedelta(days=6)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if not entry_period is None:
                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=int(contract.rate)

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " click this link to confirm your Attendance: " + \
                                       os.environ[
                                           'FRONTEND_URL'] + '/' + new_employee_entry.signature
                                pindomodels.PindoSMS.sendSMS(phone, text)

                            else:

                                new_entry_period = EntryPeriod(institution_id=institution.id,
                                                               startDate=datetime.combine(start,
                                                                                          datetime.min.time()),
                                                               endDate=datetime.combine(end,
                                                                                        datetime.min.time()))
                                ent_session.add(new_entry_period)
                                ent_session.commit()
                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=int(contract.rate)

                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=new_entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == new_entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=new_entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " click this link to confirm your Attendance: " + \
                                       os.environ[
                                           'FRONTEND_URL'] + '/' + new_employee_entry.signature
                                pindomodels.PindoSMS.sendSMS(phone, text)

                        elif institution.invoicing_period_type == 'Monthly':
                            today = datetime.now()
                            start = get_first_date_of_current_month(today.year, today.month)
                            end = get_last_date_of_month(today.year, today.month)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if not entry_period is None:
                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=int(contract.rate)

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " click this link to confirm your Attendance: " + \
                                       os.environ[
                                           'FRONTEND_URL'] + '/' + new_employee_entry.signature
                                pindomodels.PindoSMS.sendSMS(phone, text)

                            else:
                                new_entry_period = EntryPeriod(institution_id=institution.id,
                                                               startDate=datetime.combine(start,
                                                                                          datetime.min.time()),
                                                               endDate=datetime.combine(end,
                                                                                        datetime.min.time()))
                                ent_session.add(new_entry_period)
                                ent_session.commit()

                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=new_entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=int(contract.rate)

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == new_entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=new_entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " click this link to confirm your Attendance: " + \
                                       os.environ[
                                           'FRONTEND_URL'] + '/' + new_employee_entry.signature
                                pindomodels.PindoSMS.sendSMS(phone, text)


                        elif institution.invoicing_period_type == 'Term':
                            current_date = datetime.now()
                            current_quarter = round((current_date.month - 1) / 3 + 1)
                            start = datetime(current_date.year, 3 * current_quarter - 2, 1)
                            end = datetime(current_date.year, 3 * current_quarter + 1,
                                           1) + timedelta(days=-1)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if not entry_period is None:
                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=contract.rate

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " click this link to confirm your Attendance: " + \
                                       os.environ[
                                           'FRONTEND_URL'] + '/' + new_employee_entry.signature
                                pindomodels.PindoSMS.sendSMS(phone, text)

                            else:
                                new_entry_period = EntryPeriod(institution_id=institution.id,
                                                               startDate=datetime.combine(start,
                                                                                          datetime.min.time()),
                                                               endDate=datetime.combine(end,
                                                                                        datetime.min.time()))
                                ent_session.add(new_entry_period)
                                ent_session.commit()

                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=new_entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=contract.rate

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == new_entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=new_entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " click this link to confirm your Attendance: " + \
                                       os.environ[
                                           'FRONTEND_URL'] + '/' + new_employee_entry.signature
                                pindomodels.PindoSMS.sendSMS(phone, text)

                        elif institution.invoicing_period_type == 'Semester':
                            current_date = datetime.now()
                            start = ''
                            end = ''
                            current_quarter = round((current_date.month - 1))
                            if current_quarter < 6:
                                start = datetime(current_date.year, 1, 1)
                                end = datetime(current_date.year, 6, 30)
                            else:
                                start = datetime(current_date.year, 6, 1)
                                end = datetime(current_date.year, 12, 31)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if not entry_period is None:
                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # Incrementing Invoice Amount
                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=contract.rate

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " click this link to confirm your Attendance: " + \
                                       os.environ[
                                           'FRONTEND_URL'] + '/' + new_employee_entry.signature
                                pindomodels.PindoSMS.sendSMS(phone, text)

                            else:
                                new_entry_period = EntryPeriod(institution_id=institution.id,
                                                               startDate=datetime.combine(start,
                                                                                          datetime.min.time()),
                                                               endDate=datetime.combine(end,
                                                                                        datetime.min.time()))
                                ent_session.add(new_entry_period)
                                ent_session.commit()

                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=new_entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=int(contract.rate)

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == new_entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=new_entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " click this link to confirm your Attendance: " + \
                                       os.environ[
                                           'FRONTEND_URL'] + '/' + new_employee_entry.signature
                                pindomodels.PindoSMS.sendSMS(phone, text)



                        elif institution.invoicing_period_type == 'Annaly':
                            today = datetime.now()
                            start = date(date.today().year, 1, 1)
                            end = date(date.today().year, 12, 31)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if not entry_period is None:
                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # Incrementing Invoice Amount
                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=int(contract.rate)

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " click this link to confirm your Attendance: " + \
                                       os.environ[
                                           'FRONTEND_URL'] + '/' + new_employee_entry.signature
                                pindomodels.PindoSMS.sendSMS(phone, text)

                            else:
                                new_entry_period = EntryPeriod(institution_id=institution.id,
                                                               startDate=datetime.combine(start,
                                                                                          datetime.min.time()),
                                                               endDate=datetime.combine(end,
                                                                                        datetime.min.time()))
                                ent_session.add(new_entry_period)
                                ent_session.commit()

                                new_otp = rand_num()
                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                   employee_id=employee.id,
                                                                   entry_period_id=new_entry_period.id,
                                                                   doneAt=datetime.now(),
                                                                   branchName=branch.name,
                                                                   branchId=branch.id)
                                ent_session.add(new_employee_entry)
                                ent_session.commit()

                                # amount=0
                                # if institution.rate_type == 'Individual':
                                #     amount=int(employee.individualRate)
                                # else:
                                #     statement = select(Contract).where(Contract.institution_id==institution.id,Contract.deletedStatus==False)
                                #     contract = ent_session.exec(statement).first()
                                #     amount=int(contract.rate)

                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == new_entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if invoice is None:
                                    new_invoice = Invoice(
                                        invoice_number=generate_invoice_number(institution),
                                        entry_period_id=new_entry_period.id, total_amount="0",
                                        payment_status='Pending')
                                    ent_session.add(new_invoice)
                                    ent_session.commit()

                                # Send SMS To Employee
                                first_three = employee.phone[0:3]
                                phone = employee.phone
                                if first_three != "+25":
                                    if first_three == "250":
                                        phone = "+" + employee.phone
                                    else:
                                        first_two = employee.phone[0:2]
                                        if first_two == "07":
                                            phone = "+25" + employee.phone

                                text = "Hi," + employee.firstName + " click this link to confirm your Attendance: " + \
                                       os.environ[
                                           'FRONTEND_URL'] + '/' + new_employee_entry.signature
                                pindomodels.PindoSMS.sendSMS(phone, text)

                        return JSONResponse(content="Entry Created Successfuly",
                                            status_code=status.HTTP_200_OK)
                    else:
                        return JSONResponse(content="Institution was Not Found",
                                            status_code=status.HTTP_404_NOT_FOUND)
                else:
                    return JSONResponse(
                        content="Sorry, Employee with " + str(employee_id) + " Not Active",
                        status_code=status.HTTP_404_NOT_FOUND)
            else:
                return JSONResponse(content="Employee with " + str(employee_id) + " Not Found",
                                    status_code=status.HTTP_404_NOT_FOUND)
        else:
            return JSONResponse(content="User Has no Permission To Perform This Action! ",
                                status_code=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@entries_router.get('/institutions/{institution_id}/entry/periods/')
async def fetch_institution_entry_period(institution_id: int,
                                         ent_session: Session = Depends(get_session),
                                         user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Return Institution EntryPeriod """

    try:
        statement = select(EntryPeriod).where(EntryPeriod.institution_id == institution_id,
                                              EntryPeriod.deletedStatus == False)
        result = ent_session.exec(statement).all()
        if len(result) > 0:
            invoices = []
            for r in result:
                st = select(Invoice).where(Invoice.entry_period_id == r.id,
                                           Invoice.deletedStatus == False)
                inv = ent_session.exec(st).first()

                if not inv is None:
                    data = {'id': r.id, 'invoiceNumber': inv.invoice_number,
                            'startDate': r.startDate, 'endDate': r.endDate,
                            'paymentStatus': inv.payment_status, 'amount': inv.total_amount}
                    invoices.append(data)
            return invoices
        else:
            return JSONResponse(content="No Data Found", status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@entries_router.get('/entry_period/{period_id}/entries')
async def fetch_entry_period_employee_entries(period_id: int,
                                              ent_session: Session = Depends(get_session),
                                              user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Return Employee Entry which are not Signed """

    try:
        entry_list = []
        statement = select(EmployeeEntry).where(EmployeeEntry.entry_period_id == period_id,
                                                EmployeeEntry.deletedStatus == False,
                                                EmployeeEntry.signed == True).order_by(
            EmployeeEntry.id.asc())
        result = ent_session.exec(statement).all()

        if len(result) > 0:
            list = []
            for r in result:
                show = True
                if checkEmployeeRawAdded(list, r.employee_id, r.doneAt):
                    show = False
                else:
                    show = True
                    obj = checkEmployeeOnetimeEntry(emp_id=r.employee_id, doneAt=r.doneAt)
                    list.append(obj)
                if show:
                    st = select(Employee).where(Employee.id == r.employee_id,
                                                Employee.deletedStatus == False)
                    emp = ent_session.exec(st).first()
                    if emp is not None:
                        data = {'id': r.id, 'firstName': emp.firstName, 'lastName': emp.lastName,
                                'phone': emp.phone, 'signedAt': str(r.signedAt),
                                'signature': r.signature, 'branchName': r.branchName,
                                'image': r.image}
                        entry_list.append(data)
            return entry_list
        else:
            return JSONResponse(content="Employee  Not Found",
                                status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:

        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@entries_router.get('/entries/period/start_date/end_date', response_class=FileResponse)
async def fetch_employee_entries_between_dates(bg_tasks: BackgroundTasks,
                                               start_date: datetime = datetime(1970, 1, 1),
                                               end_date: datetime = datetime.now(),
                                               ent_session: Session = Depends(get_session),
                                               user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Return all entries between start date and end date """

    try:
        """ Get all entries signed from start date to end date """

        statement = select(EmployeeEntry).where(
            col(EmployeeEntry.signedAt).between(start_date, end_date),
            EmployeeEntry.deletedStatus == False, EmployeeEntry.signed == True).order_by(
            EmployeeEntry.id.asc())
        entries = ent_session.exec(statement).all()

        if len(entries) < 1:
            return JSONResponse(
                content=f'There are no entries from {start_date.date()} to {end_date.date()}!',
                status_code=status.HTTP_200_OK)

        file_name = f"{start_date.date()}_{end_date.date()}"
        export_to_excel(entries, file_name)
        headers = {'Content-Disposition': f'attachment; filename="{file_name}.xlsx"'}
        file_path = os.getcwd() + "/" + f'{file_name}.xlsx'

        bg_tasks.add_task(os.remove, file_path)
        return FileResponse(path=file_path, media_type='application/octet-stream',
                            filename=f'{file_name}.xlsx', headers=headers, background=bg_tasks)

    except Exception as e:
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@entries_router.get('/entry_period/{period_id}/details/')
async def fetch_entry_period_and_invoice(period_id: int,
                                         ent_session: Session = Depends(get_session),
                                         user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Return Employee Entry which are not Signed """

    try:
        statement = select(EntryPeriod).where(EntryPeriod.id == period_id,
                                              EntryPeriod.deletedStatus == False)
        result = ent_session.exec(statement).first()
        inv_statement = select(Invoice).where(Invoice.entry_period_id == period_id,
                                              Invoice.deletedStatus == False)
        invoice = ent_session.exec(inv_statement).first()
        ins_statement = select(Institution).where(Institution.id == result.institution_id,
                                                  Institution.deletedStatus == False)
        institution = ent_session.exec(ins_statement).first()

        period_data = {'startDate': str(result.startDate), 'endDate': str(result.endDate),
                       'uuid': str(result.uuid), 'institutionName': institution.name}
        invoice_notes = ''
        if invoice.invoice_notes is not None:
            invoice_notes = invoice.invoice_notes

        invoice_data = {'uuid': str(invoice.uuid), 'payment_status': invoice.payment_status,
                        'payment_confirmed_at': str(invoice.payment_confirmed_at),
                        'payment_confirmed_by': invoice.payment_confirmed_by,
                        'total_amount': invoice.total_amount,
                        'invoice_number': invoice.invoice_number, 'invoice_notes': invoice_notes,
                        'invoice_ebm': invoice.invoice_ebm}

        context = {'period': period_data, 'invoice': invoice_data}
        print(context)
        if result is not None and invoice is not None:
            return context
        else:
            return JSONResponse(content="Entry Period Not Found",
                                status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


from pathlib import Path


@entries_router.post('/entries/{uuid}/create/withSignature/')
async def create_employee_entry_with_signature_image(uuid: str, file: UploadFile,
                                                     ent_session: Session = Depends(get_session),
                                                     user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Create Employee Entry."""
    try:
        statement = select(Employee).where(Employee.uuid == uuid, Employee.deletedStatus == False)
        employee = ent_session.exec(statement).first()

        if user.referenceName == 'Branch' and not user.referenceId is None:
            branch_statement = select(Branch).where(Branch.id == user.referenceId,
                                                    Branch.deletedStatus == False)
            branch = ent_session.exec(branch_statement).first()
            if not employee is None:
                if employee.active_status == 'Active':
                    statement = select(Institution).where(Institution.id == employee.institution_id,
                                                          Institution.deletedStatus == False)
                    institution = ent_session.exec(statement).first()

                    if not institution is None and institution.active_status == 'Active':
                        if institution.invoicing_period_type == 'Weekly':
                            today = date.today()
                            start = today - timedelta(days=today.weekday())
                            end = start + timedelta(days=6)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if not entry_period is None:

                                # Check if invoice is still pending
                                checkNotPaid = True
                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if not invoice is None:
                                    if invoice.payment_status != "Pending":
                                        checkNotPaid = False

                                if checkNotPaid:
                                    statement = select(Contract).where(
                                        Contract.institution_id == institution.id,
                                        Contract.deletedStatus == False, Contract.current == True)
                                    contract = ent_session.exec(statement).first()

                                    if not contract is None:

                                        new_otp = rand_num()
                                        new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                           employee_id=employee.id,
                                                                           entry_period_id=entry_period.id,
                                                                           doneAt=datetime.now(),
                                                                           branchName=branch.name,
                                                                           branchId=branch.id,
                                                                           signed=True,
                                                                           signedAt=datetime.now())
                                        ent_session.add(new_employee_entry)
                                        ent_session.commit()
                                        path = os.environ[
                                                   'FILE_SOURCE'] + '/' + 'SignatureAttachments'
                                        obj = Path(path)
                                        if obj.exists():
                                            file_path = os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                new_employee_entry.uuid) + '_' + file.filename
                                            with open(f'{file_path}', 'wb') as buffer:
                                                shutil.copyfileobj(file.file, buffer)
                                            print('File Exists')
                                        else:
                                            print('File was not existing but is being created')
                                            os.mkdir(os.environ[
                                                         'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                            file_path = os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                new_employee_entry.uuid) + '_' + file.filename
                                            with open(f'{file_path}', 'wb') as buffer:
                                                shutil.copyfileobj(file.file, buffer)

                                        new_employee_entry.image = file_path
                                        ent_session.add(new_employee_entry)
                                        ent_session.commit()

                                        # Checking for Incrementing Invoice Amount
                                        if len(get_employee_daily_entries(employee)) < 2:
                                            ins_statement = select(Institution).where(
                                                Institution.id == entry_period.institution_id,
                                                Institution.deletedStatus == False)
                                            institution = ent_session.exec(ins_statement).first()

                                            amount = 0
                                            if institution.rate_type == 'Individual':
                                                amount = int(employee.individualRate)
                                            else:

                                                amount = int(contract.rate)

                                            statement = select(Invoice).where(
                                                Invoice.entry_period_id == entry_period.id,
                                                Invoice.deletedStatus == False)
                                            invoice = ent_session.exec(statement).first()
                                            if invoice is None:
                                                # Increment Invoice Amount
                                                new_invoice = Invoice(
                                                    invoice_number=generate_invoice_number(
                                                        institution),
                                                    entry_period_id=entry_period.id,
                                                    payment_status='Pending', total_amount=amount)
                                                ent_session.add(new_invoice)
                                                ent_session.commit()
                                            else:
                                                invoice.total_amount = int(
                                                    invoice.total_amount) + amount
                                                ent_session.add(invoice)
                                                ent_session.commit()
                                    else:
                                        return JSONResponse(
                                            content="There is no active contract for the institution of the employee",
                                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                else:
                                    return JSONResponse(content="Can't Sign. Invoice looks paid",
                                                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                            else:
                                statement = select(Contract).where(
                                    Contract.institution_id == institution.id,
                                    Contract.deletedStatus == False, Contract.current == True)
                                contract = ent_session.exec(statement).first()

                                if not contract is None:

                                    new_entry_period = EntryPeriod(institution_id=institution.id,
                                                                   startDate=datetime.combine(start,
                                                                                              datetime.min.time()),
                                                                   endDate=datetime.combine(end,
                                                                                            datetime.min.time()))
                                    ent_session.add(new_entry_period)
                                    ent_session.commit()

                                    new_otp = rand_num()
                                    new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                       employee_id=employee.id,
                                                                       entry_period_id=new_entry_period.id,
                                                                       doneAt=datetime.now(),
                                                                       branchName=branch.name,
                                                                       branchId=branch.id,
                                                                       signed=True,
                                                                       signedAt=datetime.now())
                                    ent_session.add(new_employee_entry)
                                    ent_session.commit()

                                    if os.path.exists(os.environ[
                                                          'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                        file_path = os.environ[
                                                        'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                            new_employee_entry.uuid) + '_' + file.filename
                                        with open(f'{file_path}', 'wb') as buffer:
                                            shutil.copyfileobj(file.file, buffer)
                                    else:
                                        os.mkdir(os.environ[
                                                     'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                        file_path = os.environ[
                                                        'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                            new_employee_entry.uuid) + '_' + file.filename
                                        with open(f'{file_path}', 'wb') as buffer:
                                            shutil.copyfileobj(file.file, buffer)

                                    new_employee_entry.image = file_path
                                    ent_session.add(new_employee_entry)
                                    ent_session.commit()

                                    # Checking for Incrementing Invoice Amount
                                    if len(get_employee_daily_entries(employee)) < 2:
                                        ins_statement = select(Institution).where(
                                            Institution.id == new_entry_period.institution_id,
                                            Institution.deletedStatus == False)
                                        institution = ent_session.exec(ins_statement).first()

                                        amount = 0
                                        if institution.rate_type == 'Individual':
                                            amount = int(employee.individualRate)
                                        else:

                                            amount = int(contract.rate)

                                        statement = select(Invoice).where(
                                            Invoice.entry_period_id == new_entry_period.id,
                                            Invoice.deletedStatus == False)
                                        invoice = ent_session.exec(statement).first()
                                        if invoice is None:
                                            # Increment Invoice Amount
                                            new_invoice = Invoice(
                                                invoice_number=generate_invoice_number(institution),
                                                entry_period_id=new_entry_period.id,
                                                payment_status='Pending', total_amount=amount)
                                            ent_session.add(new_invoice)
                                            ent_session.commit()
                                        else:
                                            invoice.total_amount = int(
                                                invoice.total_amount) + amount
                                            ent_session.add(invoice)
                                            ent_session.commit()
                                else:
                                    return JSONResponse(
                                        content="There is no active contract for the institution of the employee",
                                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                        elif institution.invoicing_period_type == PeriodType.Monthly:
                            today = datetime.now()
                            start = get_first_date_of_current_month(today.year, today.month)
                            end = get_last_date_of_month(today.year, today.month)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if entry_period is not None:
                                checkNotPaid = True
                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                statement = select(Contract).where(
                                    Contract.institution_id == institution.id,
                                    Contract.deletedStatus == False, Contract.current == True)
                                contract = ent_session.exec(statement).first()

                                if invoice is not None:
                                    if invoice.payment_status != "Pending":
                                        checkNotPaid = False

                                if checkNotPaid:
                                    if contract is not None:
                                        new_otp = rand_num()
                                        new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                           employee_id=employee.id,
                                                                           entry_period_id=entry_period.id,
                                                                           doneAt=datetime.now(),
                                                                           branchName=branch.name,
                                                                           branchId=branch.id,
                                                                           signed=True,
                                                                           signedAt=datetime.now())
                                        ent_session.add(new_employee_entry)
                                        ent_session.commit()

                                        if os.path.exists(os.environ[
                                                              'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                            file_path = os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                new_employee_entry.uuid) + '_' + file.filename
                                            with open(f'{file_path}', 'wb') as buffer:
                                                shutil.copyfileobj(file.file, buffer)
                                        else:
                                            os.mkdir(os.environ[
                                                         'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                            file_path = os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                new_employee_entry.uuid) + '_' + file.filename
                                            with open(f'{file_path}', 'wb') as buffer:
                                                shutil.copyfileobj(file.file, buffer)

                                        new_employee_entry.image = file_path
                                        ent_session.add(new_employee_entry)
                                        ent_session.commit()

                                        # Checking for Incrementing Invoice Amount
                                        if employee_daily_entries(new_employee_entry) < 2:
                                            ins_statement = select(Institution).where(
                                                Institution.id == entry_period.institution_id,
                                                Institution.deletedStatus == False)
                                            institution = ent_session.exec(ins_statement).first()

                                            if institution.rate_type == 'Individual':
                                                amount = int(employee.individualRate)
                                            else:
                                                amount = int(contract.rate)

                                            statement = select(Invoice).where(
                                                Invoice.entry_period_id == entry_period.id,
                                                Invoice.deletedStatus == False)
                                            invoice = ent_session.exec(statement).first()
                                            if invoice is None:
                                                # Increment Invoice Amount
                                                new_invoice = Invoice(
                                                    invoice_number=generate_invoice_number(
                                                        institution),
                                                    entry_period_id=entry_period.id,
                                                    payment_status='Pending', total_amount=amount)
                                                ent_session.add(new_invoice)
                                                ent_session.commit()
                                            else:
                                                invoice.total_amount = update_invoice_amount(
                                                    entry_period.id, amount)
                                                ent_session.add(invoice)
                                                ent_session.commit()
                                    else:
                                        return JSONResponse(
                                            content="There is no active contract for the institution of the employee",
                                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                else:
                                    return JSONResponse(content="Can't Sign. Invoice looks paid",
                                                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                            else:

                                statement = select(Contract).where(
                                    Contract.institution_id == institution.id,
                                    Contract.deletedStatus == False, Contract.current == True)
                                contract = ent_session.exec(statement).first()

                                if contract is not None:
                                    new_entry_period = EntryPeriod(institution_id=institution.id,
                                                                   startDate=datetime.combine(start,
                                                                                              datetime.min.time()),
                                                                   endDate=datetime.combine(end,
                                                                                            datetime.min.time()))
                                    ent_session.add(new_entry_period)
                                    ent_session.commit()

                                    new_otp = rand_num()
                                    new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                       employee_id=employee.id,
                                                                       entry_period_id=new_entry_period.id,
                                                                       doneAt=datetime.now(),
                                                                       branchName=branch.name,
                                                                       branchId=branch.id,
                                                                       signed=True,
                                                                       signedAt=datetime.now())
                                    ent_session.add(new_employee_entry)
                                    ent_session.commit()

                                    if os.path.exists(os.environ[
                                                          'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                        file_path = os.environ[
                                                        'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                            new_employee_entry.uuid) + '_' + file.filename
                                        with open(f'{file_path}', 'wb') as buffer:
                                            shutil.copyfileobj(file.file, buffer)
                                    else:
                                        os.mkdir(os.environ[
                                                     'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                        file_path = os.environ[
                                                        'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                            new_employee_entry.uuid) + '_' + file.filename
                                        with open(f'{file_path}', 'wb') as buffer:
                                            shutil.copyfileobj(file.file, buffer)

                                    new_employee_entry.image = file_path
                                    ent_session.add(new_employee_entry)
                                    ent_session.commit()
                                    if employee_daily_entries(new_employee_entry) < 2:
                                        ins_statement = select(Institution).where(
                                            Institution.id == new_entry_period.institution_id,
                                            Institution.deletedStatus == False)
                                        institution = ent_session.exec(ins_statement).first()

                                        if institution.rate_type == 'Individual':
                                            amount = int(employee.individualRate)
                                        else:
                                            amount = int(contract.rate)

                                        statement = select(Invoice).where(
                                            Invoice.entry_period_id == new_entry_period.id,
                                            Invoice.deletedStatus == False)
                                        invoice = ent_session.exec(statement).first()
                                        if invoice is None:
                                            # Increment Invoice Amount
                                            new_invoice = Invoice(
                                                invoice_number=generate_invoice_number(institution),
                                                entry_period_id=new_entry_period.id,
                                                payment_status='Pending', total_amount=amount)
                                            ent_session.add(new_invoice)
                                            ent_session.commit()
                                        else:
                                            invoice.total_amount = update_invoice_amount(
                                                new_entry_period.id, amount)
                                            ent_session.add(invoice)
                                            ent_session.commit()
                                else:
                                    return JSONResponse(
                                        content="There is no active contract for the institution of the employee",
                                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                        elif institution.invoicing_period_type == 'Term':
                            current_date = datetime.now()
                            current_quarter = round((current_date.month - 1) / 3 + 1)
                            start = datetime(current_date.year, 3 * current_quarter - 2, 1)
                            end = datetime(current_date.year, 3 * current_quarter + 1,
                                           1) + timedelta(days=-1)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if not entry_period is None:
                                checkNotPaid = True
                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()

                                if not invoice is None:
                                    if invoice.payment_status != "Pending":
                                        checkNotPaid = False

                                if checkNotPaid:
                                    statement = select(Contract).where(
                                        Contract.institution_id == institution.id,
                                        Contract.deletedStatus == False, Contract.current == True)
                                    contract = ent_session.exec(statement).first()
                                    if not contract is None:
                                        new_otp = rand_num()
                                        new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                           employee_id=employee.id,
                                                                           entry_period_id=entry_period.id,
                                                                           doneAt=datetime.now(),
                                                                           branchName=branch.name,
                                                                           branchId=branch.id,
                                                                           signed=True,
                                                                           signedAt=datetime.now())
                                        ent_session.add(new_employee_entry)
                                        ent_session.commit()

                                        if os.path.exists(os.environ[
                                                              'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                            file_path = os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                new_employee_entry.uuid) + '_' + file.filename
                                            with open(f'{file_path}', 'wb') as buffer:
                                                shutil.copyfileobj(file.file, buffer)
                                        else:
                                            os.mkdir(os.environ[
                                                         'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                            file_path = os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                new_employee_entry.uuid) + '_' + file.filename
                                            with open(f'{file_path}', 'wb') as buffer:
                                                shutil.copyfileobj(file.file, buffer)

                                        new_employee_entry.image = file_path
                                        ent_session.add(new_employee_entry)
                                        ent_session.commit()

                                        # Checking for Incrementing Invoice Amount
                                        if len(get_employee_daily_entries(employee)) < 2:
                                            ins_statement = select(Institution).where(
                                                Institution.id == entry_period.institution_id,
                                                Institution.deletedStatus == False)
                                            institution = ent_session.exec(ins_statement).first()

                                            amount = 0
                                            if institution.rate_type == 'Individual':
                                                amount = int(employee.individualRate)
                                            else:

                                                amount = int(contract.rate)

                                            statement = select(Invoice).where(
                                                Invoice.entry_period_id == entry_period.id,
                                                Invoice.deletedStatus == False)
                                            invoice = ent_session.exec(statement).first()
                                            if invoice is None:
                                                # Increment Invoice Amount
                                                new_invoice = Invoice(
                                                    invoice_number=generate_invoice_number(
                                                        institution),
                                                    entry_period_id=entry_period.id,
                                                    payment_status='Pending', total_amount=amount)
                                                ent_session.add(new_invoice)
                                                ent_session.commit()
                                            else:
                                                invoice.total_amount = int(
                                                    invoice.total_amount) + amount
                                                ent_session.add(invoice)
                                                ent_session.commit()
                                    else:
                                        return JSONResponse(
                                            content="There is no active contract for the institution of the employee",
                                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                else:
                                    return JSONResponse(content="Can't Sign. Invoice looks paid",
                                                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                            else:

                                statement = select(Contract).where(
                                    Contract.institution_id == institution.id,
                                    Contract.deletedStatus == False)
                                contract = ent_session.exec(statement).first()

                                if not contract is None:

                                    new_entry_period = EntryPeriod(institution_id=institution.id,
                                                                   startDate=datetime.combine(start,
                                                                                              datetime.min.time()),
                                                                   endDate=datetime.combine(end,
                                                                                            datetime.min.time()))
                                    ent_session.add(new_entry_period)
                                    ent_session.commit()

                                    new_otp = rand_num()
                                    new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                       employee_id=employee.id,
                                                                       entry_period_id=new_entry_period.id,
                                                                       doneAt=datetime.now(),
                                                                       branchName=branch.name,
                                                                       branchId=branch.id,
                                                                       signed=True,
                                                                       signedAt=datetime.now())
                                    ent_session.add(new_employee_entry)
                                    ent_session.commit()

                                    if os.path.exists(os.environ[
                                                          'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                        file_path = os.environ[
                                                        'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                            new_employee_entry.uuid) + '_' + file.filename
                                        with open(f'{file_path}', 'wb') as buffer:
                                            shutil.copyfileobj(file.file, buffer)
                                    else:
                                        os.mkdir(os.environ[
                                                     'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                        file_path = os.environ[
                                                        'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                            new_employee_entry.uuid) + '_' + file.filename
                                        with open(f'{file_path}', 'wb') as buffer:
                                            shutil.copyfileobj(file.file, buffer)

                                    new_employee_entry.image = file_path
                                    ent_session.add(new_employee_entry)
                                    ent_session.commit()

                                    # Checking for Incrementing Invoice Amount
                                    if len(get_employee_daily_entries(employee)) < 2:
                                        ins_statement = select(Institution).where(
                                            Institution.id == new_entry_period.institution_id,
                                            Institution.deletedStatus == False)
                                        institution = ent_session.exec(ins_statement).first()

                                        amount = 0
                                        if institution.rate_type == 'Individual':
                                            amount = int(employee.individualRate)
                                        else:

                                            amount = int(contract.rate)

                                        statement = select(Invoice).where(
                                            Invoice.entry_period_id == new_entry_period.id,
                                            Invoice.deletedStatus == False)
                                        invoice = ent_session.exec(statement).first()
                                        if invoice is None:
                                            # Increment Invoice Amount
                                            new_invoice = Invoice(
                                                invoice_number=generate_invoice_number(institution),
                                                entry_period_id=new_entry_period.id,
                                                payment_status='Pending', total_amount=amount)
                                            ent_session.add(new_invoice)
                                            ent_session.commit()
                                        else:
                                            invoice.total_amount = int(
                                                invoice.total_amount) + amount
                                            ent_session.add(invoice)
                                            ent_session.commit()
                                else:
                                    return JSONResponse(
                                        content="There is no active contract for the institution of the employee",
                                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


                        elif institution.invoicing_period_type == 'Semester':
                            current_date = datetime.now()
                            start = ''
                            end = ''
                            current_quarter = round((current_date.month - 1))
                            if current_quarter < 6:
                                start = datetime(current_date.year, 1, 1)
                                end = datetime(current_date.year, 6, 30)
                            else:
                                start = datetime(current_date.year, 6, 1)
                                end = datetime(current_date.year, 12, 31)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if not entry_period is None:
                                checkNotPaid = True
                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if not invoice is None:
                                    if invoice.payment_status != "Pending":
                                        checkNotPaid = False
                                if checkNotPaid:
                                    statement = select(Contract).where(
                                        Contract.institution_id == institution.id,
                                        Contract.deletedStatus == False, Contract.current == True)
                                    contract = ent_session.exec(statement).first()
                                    if not contract is None:

                                        new_otp = rand_num()
                                        new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                           employee_id=employee.id,
                                                                           entry_period_id=entry_period.id,
                                                                           doneAt=datetime.now(),
                                                                           branchName=branch.name,
                                                                           branchId=branch.id,
                                                                           signed=True,
                                                                           signedAt=datetime.now())
                                        ent_session.add(new_employee_entry)
                                        ent_session.commit()

                                        if os.path.exists(os.environ[
                                                              'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                            file_path = os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                new_employee_entry.uuid) + '_' + file.filename
                                            with open(f'{file_path}', 'wb') as buffer:
                                                shutil.copyfileobj(file.file, buffer)
                                        else:
                                            os.mkdir(os.environ[
                                                         'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                            file_path = os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                new_employee_entry.uuid) + '_' + file.filename
                                            with open(f'{file_path}', 'wb') as buffer:
                                                shutil.copyfileobj(file.file, buffer)

                                        new_employee_entry.image = file_path
                                        ent_session.add(new_employee_entry)
                                        ent_session.commit()

                                        # Checking for Incrementing Invoice Amount
                                        if len(get_employee_daily_entries(employee)) < 2:
                                            ins_statement = select(Institution).where(
                                                Institution.id == entry_period.institution_id,
                                                Institution.deletedStatus == False)
                                            institution = ent_session.exec(ins_statement).first()

                                            amount = 0
                                            if institution.rate_type == 'Individual':
                                                amount = int(employee.individualRate)
                                            else:

                                                amount = int(contract.rate)

                                            statement = select(Invoice).where(
                                                Invoice.entry_period_id == entry_period.id,
                                                Invoice.deletedStatus == False)
                                            invoice = ent_session.exec(statement).first()
                                            if invoice is None:
                                                # Increment Invoice Amount
                                                new_invoice = Invoice(
                                                    invoice_number=generate_invoice_number(
                                                        institution),
                                                    entry_period_id=entry_period.id,
                                                    payment_status='Pending', total_amount=amount)
                                                ent_session.add(new_invoice)
                                                ent_session.commit()
                                            else:
                                                invoice.total_amount = int(
                                                    invoice.total_amount) + amount
                                                ent_session.add(invoice)
                                                ent_session.commit()
                                    else:
                                        return JSONResponse(
                                            content="There is no active contract for the institution of the employee",
                                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                else:
                                    return JSONResponse(content="Can't Sign. Invoice looks paid",
                                                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                            else:

                                statement = select(Contract).where(
                                    Contract.institution_id == institution.id,
                                    Contract.deletedStatus == False, Contract.current == True)
                                contract = ent_session.exec(statement).first()

                                if not contract is None:

                                    new_entry_period = EntryPeriod(institution_id=institution.id,
                                                                   startDate=datetime.combine(start,
                                                                                              datetime.min.time()),
                                                                   endDate=datetime.combine(end,
                                                                                            datetime.min.time()))
                                    ent_session.add(new_entry_period)
                                    ent_session.commit()

                                    new_otp = rand_num()
                                    new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                       employee_id=employee.id,
                                                                       entry_period_id=new_entry_period.id,
                                                                       doneAt=datetime.now(),
                                                                       branchName=branch.name,
                                                                       branchId=branch.id,
                                                                       signed=True,
                                                                       signedAt=datetime.now())
                                    ent_session.add(new_employee_entry)
                                    ent_session.commit()

                                    if os.path.exists(os.environ[
                                                          'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                        file_path = os.environ[
                                                        'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                            new_employee_entry.uuid) + '_' + file.filename
                                        with open(f'{file_path}', 'wb') as buffer:
                                            shutil.copyfileobj(file.file, buffer)
                                    else:
                                        os.mkdir(os.environ[
                                                     'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                        file_path = os.environ[
                                                        'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                            new_employee_entry.uuid) + '_' + file.filename
                                        with open(f'{file_path}', 'wb') as buffer:
                                            shutil.copyfileobj(file.file, buffer)

                                    new_employee_entry.image = file_path
                                    ent_session.add(new_employee_entry)
                                    ent_session.commit()

                                    # Checking for Incrementing Invoice Amount
                                    if len(get_employee_daily_entries(employee)) < 2:
                                        ins_statement = select(Institution).where(
                                            Institution.id == new_entry_period.institution_id,
                                            Institution.deletedStatus == False)
                                        institution = ent_session.exec(ins_statement).first()

                                        amount = 0
                                        if institution.rate_type == 'Individual':
                                            amount = int(employee.individualRate)
                                        else:

                                            amount = int(contract.rate)

                                        statement = select(Invoice).where(
                                            Invoice.entry_period_id == new_entry_period.id,
                                            Invoice.deletedStatus == False)
                                        invoice = ent_session.exec(statement).first()
                                        if invoice is None:
                                            # Increment Invoice Amount
                                            new_invoice = Invoice(
                                                invoice_number=generate_invoice_number(institution),
                                                entry_period_id=new_entry_period.id,
                                                payment_status='Pending', total_amount=amount)
                                            ent_session.add(new_invoice)
                                            ent_session.commit()
                                        else:
                                            invoice.total_amount = int(
                                                invoice.total_amount) + amount
                                            ent_session.add(invoice)
                                            ent_session.commit()
                                else:
                                    return JSONResponse(
                                        content="There is no active contract for the institution of the employee",
                                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                        elif institution.invoicing_period_type == 'Annaly':
                            today = datetime.now()
                            start = date(date.today().year, 1, 1)
                            end = date(date.today().year, 12, 31)

                            statement = select(EntryPeriod).where(
                                EntryPeriod.institution_id == institution.id,
                                EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                Institution.deletedStatus == False)
                            entry_period = ent_session.exec(statement).first()
                            if not entry_period is None:
                                checkNotPaid = True
                                statement = select(Invoice).where(
                                    Invoice.entry_period_id == entry_period.id,
                                    Invoice.deletedStatus == False)
                                invoice = ent_session.exec(statement).first()
                                if not invoice is None:
                                    if invoice.payment_status != "Pending":
                                        checkNotPaid = False

                                if checkNotPaid:

                                    statement = select(Contract).where(
                                        Contract.institution_id == institution.id,
                                        Contract.deletedStatus == False, Contract.current == True)
                                    contract = ent_session.exec(statement).first()

                                    if not contract is None:

                                        new_otp = rand_num()
                                        new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                           employee_id=employee.id,
                                                                           entry_period_id=entry_period.id,
                                                                           doneAt=datetime.now(),
                                                                           branchName=branch.name,
                                                                           branchId=branch.id,
                                                                           signed=True,
                                                                           signedAt=datetime.now())
                                        ent_session.add(new_employee_entry)
                                        ent_session.commit()

                                        if os.path.exists(os.environ[
                                                              'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                            file_path = os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                new_employee_entry.uuid) + '_' + file.filename
                                            with open(f'{file_path}', 'wb') as buffer:
                                                shutil.copyfileobj(file.file, buffer)
                                        else:
                                            os.mkdir(os.environ[
                                                         'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                            file_path = os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                new_employee_entry.uuid) + '_' + file.filename
                                            with open(f'{file_path}', 'wb') as buffer:
                                                shutil.copyfileobj(file.file, buffer)

                                        new_employee_entry.image = file_path
                                        ent_session.add(new_employee_entry)
                                        ent_session.commit()

                                        # Checking for Incrementing Invoice Amount
                                        if len(get_employee_daily_entries(employee)) < 2:
                                            ins_statement = select(Institution).where(
                                                Institution.id == entry_period.institution_id,
                                                Institution.deletedStatus == False)
                                            institution = ent_session.exec(ins_statement).first()

                                            amount = 0
                                            if institution.rate_type == 'Individual':
                                                amount = int(employee.individualRate)
                                            else:
                                                statement = select(Contract).where(
                                                    Contract.institution_id == institution.id,
                                                    Contract.deletedStatus == False)
                                                contract = ent_session.exec(statement).first()
                                                amount = int(contract.rate)

                                            statement = select(Invoice).where(
                                                Invoice.entry_period_id == entry_period.id,
                                                Invoice.deletedStatus == False)
                                            invoice = ent_session.exec(statement).first()
                                            if invoice is None:
                                                # Increment Invoice Amount
                                                new_invoice = Invoice(
                                                    invoice_number=generate_invoice_number(
                                                        institution),
                                                    entry_period_id=entry_period.id,
                                                    payment_status='Pending', total_amount=amount)
                                                ent_session.add(new_invoice)
                                                ent_session.commit()
                                            else:
                                                invoice.total_amount = int(
                                                    invoice.total_amount) + amount
                                                ent_session.add(invoice)
                                                ent_session.commit()
                                    else:
                                        return JSONResponse(
                                            content="There is no active contract for the institution of the employee",
                                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                else:
                                    return JSONResponse(content="Can't Sign. Invoice looks paid",
                                                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                            else:

                                statement = select(Contract).where(
                                    Contract.institution_id == institution.id,
                                    Contract.deletedStatus == False, Contract.current == True)
                                contract = ent_session.exec(statement).first()

                                if not contract is None:
                                    new_entry_period = EntryPeriod(institution_id=institution.id,
                                                                   startDate=datetime.combine(start,
                                                                                              datetime.min.time()),
                                                                   endDate=datetime.combine(end,
                                                                                            datetime.min.time()))
                                    ent_session.add(new_entry_period)
                                    ent_session.commit()

                                    new_otp = rand_num()
                                    new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                       employee_id=employee.id,
                                                                       entry_period_id=new_entry_period.id,
                                                                       doneAt=datetime.now(),
                                                                       branchName=branch.name,
                                                                       branchId=branch.id,
                                                                       signed=True,
                                                                       signedAt=datetime.now())
                                    ent_session.add(new_employee_entry)
                                    ent_session.commit()

                                    if os.path.exists(os.environ[
                                                          'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                        file_path = os.environ[
                                                        'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                            new_employee_entry.uuid) + '_' + file.filename
                                        with open(f'{file_path}', 'wb') as buffer:
                                            shutil.copyfileobj(file.file, buffer)
                                    else:
                                        os.mkdir(os.environ[
                                                     'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                        file_path = os.environ[
                                                        'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                            new_employee_entry.uuid) + '_' + file.filename
                                        with open(f'{file_path}', 'wb') as buffer:
                                            shutil.copyfileobj(file.file, buffer)

                                    new_employee_entry.image = file_path
                                    ent_session.add(new_employee_entry)
                                    ent_session.commit()

                                    # Checking for Incrementing Invoice Amount
                                    if len(get_employee_daily_entries(employee)) < 2:
                                        ins_statement = select(Institution).where(
                                            Institution.id == new_entry_period.institution_id,
                                            Institution.deletedStatus == False)
                                        institution = ent_session.exec(ins_statement).first()

                                        amount = 0
                                        if institution.rate_type == 'Individual':
                                            amount = int(employee.individualRate)
                                        else:

                                            amount = int(contract.rate)

                                        statement = select(Invoice).where(
                                            Invoice.entry_period_id == new_entry_period.id,
                                            Invoice.deletedStatus == False)
                                        invoice = ent_session.exec(statement).first()
                                        if invoice is None:
                                            # Increment Invoice Amount
                                            new_invoice = Invoice(
                                                invoice_number=generate_invoice_number(institution),
                                                entry_period_id=new_entry_period.id,
                                                payment_status='Pending', total_amount=amount)
                                            ent_session.add(new_invoice)
                                            ent_session.commit()
                                        else:
                                            invoice.total_amount = int(
                                                invoice.total_amount) + amount
                                            ent_session.add(invoice)
                                            ent_session.commit()
                                else:
                                    return JSONResponse(
                                        content="There is no active contract for the institution of the employee",
                                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                        return JSONResponse(content="Entry Created Successfuly",
                                            status_code=status.HTTP_200_OK)
                    else:
                        return JSONResponse(content="Institution was Not Found",
                                            status_code=status.HTTP_404_NOT_FOUND)
                else:
                    return JSONResponse(content="Sorry, Employee is Not Active",
                                        status_code=status.HTTP_400_BAD_REQUEST)
            else:
                return JSONResponse(content="Employee  is Not Found",
                                    status_code=status.HTTP_404_NOT_FOUND)
        else:
            return JSONResponse(content="User Has no Permission To Perform This Action! ",
                                status_code=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@entries_router.get('/entries/{entry_id}/download/signature/')
async def download_entry_signature(entry_id: int, ent_session: Session = Depends(get_session),
                                   user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Upload Entry Signature """

    try:
        statement = select(EmployeeEntry).where(EmployeeEntry.id == entry_id,
                                                EmployeeEntry.deletedStatus == False)
        result = ent_session.exec(statement).first()

        if not result is None:
            return FileResponse(result.image)
        else:
            return JSONResponse(content="Employee Entry with " + entry_id + " Not Found",
                                status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


# GET INVOICES BY BETWEEN DATES
@entries_router.post('/invoices_by_date', response_model=InvoicesResponse,
                     status_code=status.HTTP_200_OK)
async def fetch_invoices_between_dates(start_date: date = date(1970, 1, 1),
                                       end_date: date = date.today(),
                                       ent_session: Session = Depends(get_session),
                                       user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Return invoices between start date and end date """

    try:
        first_date_of_the_month = start_date.replace(day=1)
        next_month = end_date.replace(day=28) + timedelta(days=4)
        last_date_of_the_month = next_month - timedelta(days=next_month.day)
        # Get the ids of all entry periods that falls between start date and end date
        entry_p_stmt = select(EntryPeriod.id).where(EntryPeriod.deletedStatus == False,
                                                    EntryPeriod.startDate >= first_date_of_the_month,
                                                    EntryPeriod.endDate <= last_date_of_the_month)
        entry_periods = ent_session.exec(entry_p_stmt).all()
        # Gel all invoices related to the array containing entry periods
        inv_stmt = select(Invoice).where(col(Invoice.entry_period_id).in_(entry_periods),
                                         Invoice.deletedStatus == False)
        invoices = ent_session.exec(inv_stmt).all()

        if len(invoices) < 1:
            return JSONResponse(content=f"There are no invoices from {start_date} to {end_date}",
                                status_code=status.HTTP_200_OK)
        # Manipulate response data
        invoice_list = []
        for i in invoices:
            invoice = OneInvoiceResponse(**i.dict())
            statement = select(EntryPeriod).where(EntryPeriod.id == i.entry_period_id,
                                                  EntryPeriod.deletedStatus == False)
            entry_p = ent_session.exec(statement).first()
            if entry_p:
                invoice.start_date = entry_p.startDate.date()
                invoice.end_date = entry_p.endDate.date()
                invoice.entry_period_id=entry_p.id
            
            invoice_list.append(invoice)
        return {"results": len(invoices), "invoices": invoice_list}
    except Exception as e:
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


# GET INSTITUTIONS NUMBER OF ATTENDANCES AND AMOUNT
@entries_router.post('/institutions_attendance_by_date')
async def institution_attendance_between_dates(start_date: date = date(1970, 1, 1),
                                               end_date: date = date.today(),
                                               ent_session: Session = Depends(get_session),
                                               user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Return institution's attendance between dates """

    first_date_of_the_month = start_date.replace(day=1)
    next_month = end_date.replace(day=28) + timedelta(days=4)
    last_date_of_the_month = next_month - timedelta(days=next_month.day)

    try:
        statement1 = select(Institution).where(Institution.deletedStatus == False)
        institutions = ent_session.exec(statement1).all()
        attendance_list = []
        for inst in institutions:
            statement = select(EntryPeriod).where(EntryPeriod.institution_id == inst.id,
                                                  EntryPeriod.startDate >= first_date_of_the_month,
                                                  EntryPeriod.endDate <= last_date_of_the_month,
                                                  EntryPeriod.deletedStatus == False)
            entry_periods = ent_session.exec(statement).all()
            inv_amounts = 0
            i = 0
            if len(entry_periods) > 0:
                start_date = datetime.combine(start_date, datetime.min.time())
                end_date = datetime.combine(end_date, datetime.max.time())
                for r in entry_periods:
                    inv_stmt = select(Invoice).where(Invoice.entry_period_id == r.id,
                                                     Invoice.deletedStatus == False)
                    inv = ent_session.exec(inv_stmt).first()
                    if inv:
                        emp_entry_statement = select(EmployeeEntry).where(
                            EmployeeEntry.entry_period_id == inv.entry_period_id,
                            EmployeeEntry.deletedStatus == False,
                            col(EmployeeEntry.signedAt).between(start_date, end_date),
                            EmployeeEntry.signed == True).order_by(EmployeeEntry.id.asc())
                        entries = ent_session.exec(emp_entry_statement).all()

                        if len(entries) > 0:
                            e_list = []
                            for e in entries:
                                if checkEmployeeRawAdded(e_list, e.employee_id, e.doneAt):
                                    pass
                                else:
                                    i += 1
                                    obj = checkEmployeeOnetimeEntry(emp_id=e.employee_id,
                                                                    doneAt=e.doneAt)
                                    e_list.append(obj)

                            inv_amounts = inv_amounts + float(inv.total_amount)
            data = {'institution': inst.name, 'amount': inv_amounts, 'number_of_attendances': i}
            attendance_list.append(data)
        return attendance_list
    except Exception as e:
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)



""""Endpoints do create employee entry with signature and service"""


@entries_router.post('/entries/{uuid}/{service_uuid}/create/withSignature_and_service')
async def create_employee_entry_with_signature_image_and_service(uuid: str,service_uuid:str, file: UploadFile,
                                                     ent_session: Session = Depends(get_session),
                                                     user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Create Employee Entry with signature and service"""
    try:
        statement1 = select(Service).where(Service.uuid == service_uuid, Service.deleted_status == False)
        service = ent_session.exec(statement1).first()

        statement = select(Employee).where(Employee.uuid == uuid, Employee.deletedStatus == False)
        employee = ent_session.exec(statement).first()

        if user.referenceName == 'Branch' and not user.referenceId is None:
            branch_statement = select(Branch).where(Branch.id == user.referenceId,
                                                    Branch.deletedStatus == False)
            branch = ent_session.exec(branch_statement).first()
           
            if not service is None:
                if not employee is None:
                    # Check if employee is allowed to use the service
                    services=employee.services
                    has_service=False
                    for s in services:
                        if s['service_id']==service.id:
                            has_service=True
                            break
                    if has_service:
                        if employee.active_status == 'Active':
                            statement = select(Institution).where(Institution.id == employee.institution_id,
                                                                Institution.deletedStatus == False)
                            institution = ent_session.exec(statement).first()

                            if not institution is None and institution.active_status == 'Active':
                                if institution.invoicing_period_type == 'Weekly':
                                    today = date.today()
                                    start = today - timedelta(days=today.weekday())
                                    end = start + timedelta(days=6)

                                    statement = select(EntryPeriod).where(
                                        EntryPeriod.institution_id == institution.id,
                                        EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                        Institution.deletedStatus == False)
                                    entry_period = ent_session.exec(statement).first()
                                    if not entry_period is None:

                                        # Check if invoice is still pending
                                        checkNotPaid = True
                                        statement = select(Invoice).where(
                                            Invoice.entry_period_id == entry_period.id,
                                            Invoice.deletedStatus == False)
                                        invoice = ent_session.exec(statement).first()
                                        if not invoice is None:
                                            if invoice.payment_status != "Pending":
                                                checkNotPaid = False

                                        if checkNotPaid:
                                            statement = select(Contract).where(
                                                Contract.institution_id == institution.id,
                                                Contract.deletedStatus == False, Contract.current == True)
                                            contract = ent_session.exec(statement).first()

                                            if not contract is None:

                                                new_otp = rand_num()
                                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                                employee_id=employee.id,
                                                                                entry_period_id=entry_period.id,
                                                                                doneAt=datetime.now(),
                                                                                branchName=branch.name,
                                                                                branchId=branch.id,
                                                                                signed=True,
                                                                                signedAt=datetime.now(),
                                                                                service_id=service.id)
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()
                                                path = os.environ[
                                                        'FILE_SOURCE'] + '/' + 'SignatureAttachments'
                                                obj = Path(path)
                                                if obj.exists():
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)
                                                    print('File Exists')
                                                else:
                                                    print('File was not existing but is being created')
                                                    os.mkdir(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)

                                                new_employee_entry.image = file_path
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                # Checking for Incrementing Invoice Amount
                                                if len(get_employee_daily_entries(employee)) < 2:
                                                    ins_statement = select(Institution).where(
                                                        Institution.id == entry_period.institution_id,
                                                        Institution.deletedStatus == False)
                                                    institution = ent_session.exec(ins_statement).first()

                                                    amount = 0
                                                    if institution.rate_type == 'Individual':
                                                        for s in employee.services:
                                                            serv_rate=s['service_rate']
                                                        amount = int(serv_rate)
                                                    else:
                                                        for sc in contract.services:
                                                            servic_rate=sc['service_rate']

                                                        amount = int(servic_rate)

                                                    statement = select(Invoice).where(
                                                        Invoice.entry_period_id == entry_period.id,
                                                        Invoice.deletedStatus == False)
                                                    invoice = ent_session.exec(statement).first()
                                                    if invoice is None:
                                                        # Increment Invoice Amount
                                                        new_invoice = Invoice(
                                                            invoice_number=generate_invoice_number(institution),
                                                            entry_period_id=entry_period.id,
                                                            payment_status='Pending', total_amount=amount)
                                                        ent_session.add(new_invoice)
                                                        ent_session.commit()
                                                    else:
                                                        invoice.total_amount = int(
                                                            invoice.total_amount) + amount
                                                        ent_session.add(invoice)
                                                        ent_session.commit()
                                            else:
                                                return JSONResponse(
                                                    content="There is no active contract for the institution of the employee",
                                                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                        else:
                                            return JSONResponse(content="Can't Sign. Invoice looks paid",
                                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                    else:
                                        statement = select(Contract).where(
                                            Contract.institution_id == institution.id,
                                            Contract.deletedStatus == False, Contract.current == True)
                                        contract = ent_session.exec(statement).first()

                                        if not contract is None:

                                            new_entry_period = EntryPeriod(institution_id=institution.id,
                                                                        startDate=datetime.combine(start,
                                                                                                    datetime.min.time()),
                                                                        endDate=datetime.combine(end,
                                                                                                    datetime.min.time()))
                                            ent_session.add(new_entry_period)
                                            ent_session.commit()

                                            new_otp = rand_num()
                                            new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                            employee_id=employee.id,
                                                                            entry_period_id=new_entry_period.id,
                                                                            doneAt=datetime.now(),
                                                                            branchName=branch.name,
                                                                            branchId=branch.id,
                                                                            signed=True,
                                                                            signedAt=datetime.now(),
                                                                            service_id=service.id)
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            if os.path.exists(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)
                                            else:
                                                os.mkdir(os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)

                                            new_employee_entry.image = file_path
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            # Checking for Incrementing Invoice Amount
                                            if len(get_employee_daily_entries(employee)) < 2:
                                                ins_statement = select(Institution).where(
                                                    Institution.id == new_entry_period.institution_id,
                                                    Institution.deletedStatus == False)
                                                institution = ent_session.exec(ins_statement).first()

                                                amount = 0
                                                if institution.rate_type == 'Individual':
                                                    for s1 in employee.services:
                                                        service_ra=s1['service_rate']
                                                    amount = int(service_ra)
                                                else:
                                                    for sc1 in contract.services:
                                                        serv_rat=sc1['service_rate']

                                                    amount = int(serv_rat)

                                                statement = select(Invoice).where(
                                                    Invoice.entry_period_id == new_entry_period.id,
                                                    Invoice.deletedStatus == False)
                                                invoice = ent_session.exec(statement).first()
                                                if invoice is None:
                                                    # Increment Invoice Amount
                                                    new_invoice = Invoice(
                                                        invoice_number=generate_invoice_number(institution),
                                                        entry_period_id=new_entry_period.id,
                                                        payment_status='Pending', total_amount=amount)
                                                    ent_session.add(new_invoice)
                                                    ent_session.commit()
                                                else:
                                                    invoice.total_amount = int(
                                                        invoice.total_amount) + amount
                                                    ent_session.add(invoice)
                                                    ent_session.commit()
                                        else:
                                            return JSONResponse(
                                                content="There is no active contract for the institution of the employee",
                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                elif institution.invoicing_period_type == PeriodType.Monthly:
                                    today = datetime.now()
                                    start = get_first_date_of_current_month(today.year, today.month)
                                    end = get_last_date_of_month(today.year, today.month)

                                    statement = select(EntryPeriod).where(
                                        EntryPeriod.institution_id == institution.id,
                                        EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                        Institution.deletedStatus == False)
                                    entry_period = ent_session.exec(statement).first()
                                    if entry_period is not None:
                                        checkNotPaid = True
                                        statement = select(Invoice).where(
                                            Invoice.entry_period_id == entry_period.id,
                                            Invoice.deletedStatus == False)
                                        invoice = ent_session.exec(statement).first()
                                        statement = select(Contract).where(
                                            Contract.institution_id == institution.id,
                                            Contract.deletedStatus == False, Contract.current == True)
                                        contract = ent_session.exec(statement).first()

                                        if invoice is not None:
                                            if invoice.payment_status != "Pending":
                                                checkNotPaid = False

                                        if checkNotPaid:
                                            if contract is not None:
                                                new_otp = rand_num()
                                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                                employee_id=employee.id,
                                                                                entry_period_id=entry_period.id,
                                                                                doneAt=datetime.now(),
                                                                                branchName=branch.name,
                                                                                branchId=branch.id,
                                                                                signed=True,
                                                                                signedAt=datetime.now(),
                                                                                service_id=service.id)
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                if os.path.exists(os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)
                                                else:
                                                    os.mkdir(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)

                                                new_employee_entry.image = file_path
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                # Checking for Incrementing Invoice Amount
                                                if employee_daily_entries(new_employee_entry) < 2:
                                                    ins_statement = select(Institution).where(
                                                        Institution.id == entry_period.institution_id,
                                                        Institution.deletedStatus == False)
                                                    institution = ent_session.exec(ins_statement).first()

                                                    if institution.rate_type == 'Individual':
                                                        for se in employee.services:
                                                            service_r=se['service_rate']
                                                        amount = int(service_r)
                                                    else:
                                                        for sco in contract.services:
                                                            service_ratc=sco['service_rate']
                                                        amount = int(service_ratc)

                                                    statement = select(Invoice).where(
                                                        Invoice.entry_period_id == entry_period.id,
                                                        Invoice.deletedStatus == False)
                                                    invoice = ent_session.exec(statement).first()
                                                    if invoice is None:
                                                        # Increment Invoice Amount
                                                        new_invoice = Invoice(
                                                            invoice_number=generate_invoice_number( institution),
                                                            entry_period_id=entry_period.id,
                                                            payment_status='Pending', total_amount=amount)
                                                        ent_session.add(new_invoice)
                                                        ent_session.commit()
                                                    else:
                                                        invoice.total_amount = update_invoice_amount(entry_period.id, amount)
                                                        ent_session.add(invoice)
                                                        ent_session.commit()
                                            else:
                                                return JSONResponse(
                                                    content="There is no active contract for the institution of the employee",
                                                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                        else:
                                            return JSONResponse(content="Can't Sign. Invoice looks paid",
                                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                    else:

                                        statement = select(Contract).where(
                                            Contract.institution_id == institution.id,
                                            Contract.deletedStatus == False, Contract.current == True)
                                        contract = ent_session.exec(statement).first()

                                        if contract is not None:
                                            new_entry_period = EntryPeriod(institution_id=institution.id,
                                                                        startDate=datetime.combine(start,
                                                                                                    datetime.min.time()),
                                                                        endDate=datetime.combine(end,
                                                                                                    datetime.min.time()))
                                            ent_session.add(new_entry_period)
                                            ent_session.commit()

                                            new_otp = rand_num()
                                            new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                            employee_id=employee.id,
                                                                            entry_period_id=new_entry_period.id,
                                                                            doneAt=datetime.now(),
                                                                            branchName=branch.name,
                                                                            branchId=branch.id,
                                                                            signed=True,
                                                                            signedAt=datetime.now(),
                                                                            service_id=service.id)
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            if os.path.exists(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)
                                            else:
                                                os.mkdir(os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)

                                            new_employee_entry.image = file_path
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()
                                            if employee_daily_entries(new_employee_entry) < 2:
                                                ins_statement = select(Institution).where(
                                                    Institution.id == new_entry_period.institution_id,
                                                    Institution.deletedStatus == False)
                                                institution = ent_session.exec(ins_statement).first()

                                                if institution.rate_type == 'Individual':
                                                    for ser in employee.services:
                                                        ser_rate=ser['service_rate']
                                                    amount = int(ser_rate)
                                                else:
                                                    for sc1 in contract.services:
                                                        servi_rate1=sc1['service_rate']
                                                    amount = int(servi_rate1)
                                                statement = select(Invoice).where(
                                                    Invoice.entry_period_id == new_entry_period.id,
                                                    Invoice.deletedStatus == False)
                                                invoice = ent_session.exec(statement).first()
                                                if invoice is None:
                                                    # Increment Invoice Amount
                                                    new_invoice = Invoice(
                                                        invoice_number=generate_invoice_number(institution),
                                                        entry_period_id=new_entry_period.id,
                                                        payment_status='Pending', total_amount=amount)
                                                    ent_session.add(new_invoice)
                                                    ent_session.commit()
                                                else:
                                                    invoice.total_amount = update_invoice_amount(
                                                        new_entry_period.id, amount)
                                                    ent_session.add(invoice)
                                                    ent_session.commit()
                                        else:
                                            return JSONResponse(
                                                content="There is no active contract for the institution of the employee",
                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                elif institution.invoicing_period_type == 'Term':
                                    current_date = datetime.now()
                                    current_quarter = round((current_date.month - 1) / 3 + 1)
                                    start = datetime(current_date.year, 3 * current_quarter - 2, 1)
                                    end = datetime(current_date.year, 3 * current_quarter + 1,
                                                1) + timedelta(days=-1)

                                    statement = select(EntryPeriod).where(
                                        EntryPeriod.institution_id == institution.id,
                                        EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                        Institution.deletedStatus == False)
                                    entry_period = ent_session.exec(statement).first()
                                    if not entry_period is None:
                                        checkNotPaid = True
                                        statement = select(Invoice).where(
                                            Invoice.entry_period_id == entry_period.id,
                                            Invoice.deletedStatus == False)
                                        invoice = ent_session.exec(statement).first()

                                        if not invoice is None:
                                            if invoice.payment_status != "Pending":
                                                checkNotPaid = False

                                        if checkNotPaid:
                                            statement = select(Contract).where(
                                                Contract.institution_id == institution.id,
                                                Contract.deletedStatus == False, Contract.current == True)
                                            contract = ent_session.exec(statement).first()
                                            if not contract is None:
                                                new_otp = rand_num()
                                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                                employee_id=employee.id,
                                                                                entry_period_id=entry_period.id,
                                                                                doneAt=datetime.now(),
                                                                                branchName=branch.name,
                                                                                branchId=branch.id,
                                                                                signed=True,
                                                                                signedAt=datetime.now(),
                                                                                service_id=service.id)
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                if os.path.exists(os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)
                                                else:
                                                    os.mkdir(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)

                                                new_employee_entry.image = file_path
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                # Checking for Incrementing Invoice Amount
                                                if len(get_employee_daily_entries(employee)) < 2:
                                                    ins_statement = select(Institution).where(
                                                        Institution.id == entry_period.institution_id,
                                                        Institution.deletedStatus == False)
                                                    institution = ent_session.exec(ins_statement).first()

                                                    amount = 0
                                                    if institution.rate_type == 'Individual':
                                                        for sert in employee.services:
                                                            ser_ratet=sert['service_rate']
                                                    amount = int(ser_ratet)
                                                else:
                                                    for sct in contract.services:
                                                        servi_ratet=sct['service_rate']
                                                    amount = int(servi_ratet)

                                                    statement = select(Invoice).where(
                                                        Invoice.entry_period_id == entry_period.id,
                                                        Invoice.deletedStatus == False)
                                                    invoice = ent_session.exec(statement).first()
                                                    if invoice is None:
                                                        # Increment Invoice Amount
                                                        new_invoice = Invoice(
                                                            invoice_number=generate_invoice_number(
                                                                institution),
                                                            entry_period_id=entry_period.id,
                                                            payment_status='Pending', total_amount=amount)
                                                        ent_session.add(new_invoice)
                                                        ent_session.commit()
                                                    else:
                                                        invoice.total_amount = int(
                                                            invoice.total_amount) + amount
                                                        ent_session.add(invoice)
                                                        ent_session.commit()
                                            else:
                                                return JSONResponse(
                                                    content="There is no active contract for the institution of the employee",
                                                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                        else:
                                            return JSONResponse(content="Can't Sign. Invoice looks paid",
                                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                    else:

                                        statement = select(Contract).where(
                                            Contract.institution_id == institution.id,
                                            Contract.deletedStatus == False)
                                        contract = ent_session.exec(statement).first()

                                        if not contract is None:

                                            new_entry_period = EntryPeriod(institution_id=institution.id,
                                                                        startDate=datetime.combine(start,
                                                                                                    datetime.min.time()),
                                                                        endDate=datetime.combine(end,
                                                                                                    datetime.min.time()))
                                            ent_session.add(new_entry_period)
                                            ent_session.commit()

                                            new_otp = rand_num()
                                            new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                            employee_id=employee.id,
                                                                            entry_period_id=new_entry_period.id,
                                                                            doneAt=datetime.now(),
                                                                            branchName=branch.name,
                                                                            branchId=branch.id,
                                                                            signed=True,
                                                                            signedAt=datetime.now(),
                                                                            service_id=service.id)
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            if os.path.exists(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)
                                            else:
                                                os.mkdir(os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)

                                            new_employee_entry.image = file_path
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            # Checking for Incrementing Invoice Amount
                                            if len(get_employee_daily_entries(employee)) < 2:
                                                ins_statement = select(Institution).where(
                                                    Institution.id == new_entry_period.institution_id,
                                                    Institution.deletedStatus == False)
                                                institution = ent_session.exec(ins_statement).first()

                                                amount = 0
                                                if institution.rate_type == 'Individual':
                                                    for sero in employee.services:
                                                        ser_rateo=sero['service_rate']
                                                    amount = int(ser_rateo)
                                                else:
                                                    for sc2 in contract.services:
                                                        servi_rate2=sc2['service_rate']
                                                    amount = int(servi_rate2)

                                                statement = select(Invoice).where(
                                                    Invoice.entry_period_id == new_entry_period.id,
                                                    Invoice.deletedStatus == False)
                                                invoice = ent_session.exec(statement).first()
                                                if invoice is None:
                                                    # Increment Invoice Amount
                                                    new_invoice = Invoice(
                                                        invoice_number=generate_invoice_number(institution),
                                                        entry_period_id=new_entry_period.id,
                                                        payment_status='Pending', total_amount=amount)
                                                    ent_session.add(new_invoice)
                                                    ent_session.commit()
                                                else:
                                                    invoice.total_amount = int(
                                                        invoice.total_amount) + amount
                                                    ent_session.add(invoice)
                                                    ent_session.commit()
                                        else:
                                            return JSONResponse(
                                                content="There is no active contract for the institution of the employee",
                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


                                elif institution.invoicing_period_type == 'Semester':
                                    current_date = datetime.now()
                                    start = ''
                                    end = ''
                                    current_quarter = round((current_date.month - 1))
                                    if current_quarter < 6:
                                        start = datetime(current_date.year, 1, 1)
                                        end = datetime(current_date.year, 6, 30)
                                    else:
                                        start = datetime(current_date.year, 6, 1)
                                        end = datetime(current_date.year, 12, 31)

                                    statement = select(EntryPeriod).where(
                                        EntryPeriod.institution_id == institution.id,
                                        EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                        Institution.deletedStatus == False)
                                    entry_period = ent_session.exec(statement).first()
                                    if not entry_period is None:
                                        checkNotPaid = True
                                        statement = select(Invoice).where(
                                            Invoice.entry_period_id == entry_period.id,
                                            Invoice.deletedStatus == False)
                                        invoice = ent_session.exec(statement).first()
                                        if not invoice is None:
                                            if invoice.payment_status != "Pending":
                                                checkNotPaid = False
                                        if checkNotPaid:
                                            statement = select(Contract).where(
                                                Contract.institution_id == institution.id,
                                                Contract.deletedStatus == False, Contract.current == True)
                                            contract = ent_session.exec(statement).first()
                                            if not contract is None:

                                                new_otp = rand_num()
                                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                                employee_id=employee.id,
                                                                                entry_period_id=entry_period.id,
                                                                                doneAt=datetime.now(),
                                                                                branchName=branch.name,
                                                                                branchId=branch.id,
                                                                                signed=True,
                                                                                signedAt=datetime.now(),
                                                                                service_id=service.id)
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                if os.path.exists(os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)
                                                else:
                                                    os.mkdir(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)

                                                new_employee_entry.image = file_path
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                # Checking for Incrementing Invoice Amount
                                                if len(get_employee_daily_entries(employee)) < 2:
                                                    ins_statement = select(Institution).where(
                                                        Institution.id == entry_period.institution_id,
                                                        Institution.deletedStatus == False)
                                                    institution = ent_session.exec(ins_statement).first()

                                                    amount = 0
                                                    if institution.rate_type == 'Individual':
                                                        for sers in employee.services:
                                                            ser_rates=sers['service_rate']
                                                    amount = int(ser_rates)
                                                else:
                                                    for scs in contract.services:
                                                        servi_rates=scs['service_rate']
                                                    amount = int(servi_rates)
                                                    statement = select(Invoice).where(
                                                        Invoice.entry_period_id == entry_period.id,
                                                        Invoice.deletedStatus == False)
                                                    invoice = ent_session.exec(statement).first()
                                                    if invoice is None:
                                                        # Increment Invoice Amount
                                                        new_invoice = Invoice(
                                                            invoice_number=generate_invoice_number(
                                                                institution),
                                                            entry_period_id=entry_period.id,
                                                            payment_status='Pending', total_amount=amount)
                                                        ent_session.add(new_invoice)
                                                        ent_session.commit()
                                                    else:
                                                        invoice.total_amount = int(
                                                            invoice.total_amount) + amount
                                                        ent_session.add(invoice)
                                                        ent_session.commit()
                                            else:
                                                return JSONResponse(
                                                    content="There is no active contract for the institution of the employee",
                                                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                        else:
                                            return JSONResponse(content="Can't Sign. Invoice looks paid",
                                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                    else:

                                        statement = select(Contract).where(
                                            Contract.institution_id == institution.id,
                                            Contract.deletedStatus == False, Contract.current == True)
                                        contract = ent_session.exec(statement).first()

                                        if not contract is None:

                                            new_entry_period = EntryPeriod(institution_id=institution.id,
                                                                        startDate=datetime.combine(start,
                                                                                                    datetime.min.time()),
                                                                        endDate=datetime.combine(end,
                                                                                                    datetime.min.time()))
                                            ent_session.add(new_entry_period)
                                            ent_session.commit()

                                            new_otp = rand_num()
                                            new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                            employee_id=employee.id,
                                                                            entry_period_id=new_entry_period.id,
                                                                            doneAt=datetime.now(),
                                                                            branchName=branch.name,
                                                                            branchId=branch.id,
                                                                            signed=True,
                                                                            signedAt=datetime.now(),
                                                                            service_id=service.id)
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            if os.path.exists(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)
                                            else:
                                                os.mkdir(os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)

                                            new_employee_entry.image = file_path
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            # Checking for Incrementing Invoice Amount
                                            if len(get_employee_daily_entries(employee)) < 2:
                                                ins_statement = select(Institution).where(
                                                    Institution.id == new_entry_period.institution_id,
                                                    Institution.deletedStatus == False)
                                                institution = ent_session.exec(ins_statement).first()

                                                amount = 0
                                                if institution.rate_type == 'Individual':
                                                    for sery in employee.services:
                                                        sery_rate=sery['service_rate']
                                                    amount = int(sery_rate)
                                                else:
                                                    for scy in contract.services:
                                                        servi_ratey=scy['service_rate']
                                                    amount = int(servi_ratey)

                                                statement = select(Invoice).where(
                                                    Invoice.entry_period_id == new_entry_period.id,
                                                    Invoice.deletedStatus == False)
                                                invoice = ent_session.exec(statement).first()
                                                if invoice is None:
                                                    # Increment Invoice Amount
                                                    new_invoice = Invoice(
                                                        invoice_number=generate_invoice_number(institution),
                                                        entry_period_id=new_entry_period.id,
                                                        payment_status='Pending', total_amount=amount)
                                                    ent_session.add(new_invoice)
                                                    ent_session.commit()
                                                else:
                                                    invoice.total_amount = int(
                                                        invoice.total_amount) + amount
                                                    ent_session.add(invoice)
                                                    ent_session.commit()
                                        else:
                                            return JSONResponse(
                                                content="There is no active contract for the institution of the employee",
                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                elif institution.invoicing_period_type == 'Annaly':
                                    today = datetime.now()
                                    start = date(date.today().year, 1, 1)
                                    end = date(date.today().year, 12, 31)

                                    statement = select(EntryPeriod).where(
                                        EntryPeriod.institution_id == institution.id,
                                        EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                        Institution.deletedStatus == False)
                                    entry_period = ent_session.exec(statement).first()
                                    if not entry_period is None:
                                        checkNotPaid = True
                                        statement = select(Invoice).where(
                                            Invoice.entry_period_id == entry_period.id,
                                            Invoice.deletedStatus == False)
                                        invoice = ent_session.exec(statement).first()
                                        if not invoice is None:
                                            if invoice.payment_status != "Pending":
                                                checkNotPaid = False

                                        if checkNotPaid:

                                            statement = select(Contract).where(
                                                Contract.institution_id == institution.id,
                                                Contract.deletedStatus == False, Contract.current == True)
                                            contract = ent_session.exec(statement).first()

                                            if not contract is None:

                                                new_otp = rand_num()
                                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                                employee_id=employee.id,
                                                                                entry_period_id=entry_period.id,
                                                                                doneAt=datetime.now(),
                                                                                branchName=branch.name,
                                                                                branchId=branch.id,
                                                                                signed=True,
                                                                                signedAt=datetime.now(),
                                                                                service_id=service.id)
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                if os.path.exists(os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)
                                                else:
                                                    os.mkdir(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)

                                                new_employee_entry.image = file_path
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                # Checking for Incrementing Invoice Amount
                                                if len(get_employee_daily_entries(employee)) < 2:
                                                    ins_statement = select(Institution).where(
                                                        Institution.id == entry_period.institution_id,
                                                        Institution.deletedStatus == False)
                                                    institution = ent_session.exec(ins_statement).first()

                                                    amount = 0
                                                    if institution.rate_type == 'Individual':
                                                            for ser in employee.services:
                                                                 ser_rate=ser['service_rate']
                                                            amount = int(ser_rate)
                                                    
                                                    statement = select(Contract).where(
                                                            Contract.institution_id == institution.id,
                                                            Contract.deletedStatus == False)
                                                    contract = ent_session.exec(statement).first()
                                                    for sc1 in contract.services:
                                                        servi_rate1=sc1['service_rate']
                                                    amount = int(servi_rate1)

                                                    statement = select(Invoice).where(
                                                        Invoice.entry_period_id == entry_period.id,
                                                        Invoice.deletedStatus == False)
                                                    invoice = ent_session.exec(statement).first()
                                                    if invoice is None:
                                                        # Increment Invoice Amount
                                                        new_invoice = Invoice(
                                                            invoice_number=generate_invoice_number(
                                                                institution),
                                                            entry_period_id=entry_period.id,
                                                            payment_status='Pending', total_amount=amount)
                                                        ent_session.add(new_invoice)
                                                        ent_session.commit()
                                                    else:
                                                        invoice.total_amount = int(
                                                            invoice.total_amount) + amount
                                                        ent_session.add(invoice)
                                                        ent_session.commit()
                                            else:
                                                return JSONResponse(
                                                    content="There is no active contract for the institution of the employee",
                                                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                        else:
                                            return JSONResponse(content="Can't Sign. Invoice looks paid",
                                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                    else:

                                        statement = select(Contract).where(
                                            Contract.institution_id == institution.id,
                                            Contract.deletedStatus == False, Contract.current == True)
                                        contract = ent_session.exec(statement).first()

                                        if not contract is None:
                                            new_entry_period = EntryPeriod(institution_id=institution.id,
                                                                        startDate=datetime.combine(start,
                                                                                                    datetime.min.time()),
                                                                        endDate=datetime.combine(end,
                                                                                                    datetime.min.time()))
                                            ent_session.add(new_entry_period)
                                            ent_session.commit()

                                            new_otp = rand_num()
                                            new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                            employee_id=employee.id,
                                                                            entry_period_id=new_entry_period.id,
                                                                            doneAt=datetime.now(),
                                                                            branchName=branch.name,
                                                                            branchId=branch.id,
                                                                            signed=True,
                                                                            signedAt=datetime.now(),
                                                                            service_id=service.id)
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            if os.path.exists(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)
                                            else:
                                                os.mkdir(os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)

                                            new_employee_entry.image = file_path
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            # Checking for Incrementing Invoice Amount
                                            if len(get_employee_daily_entries(employee)) < 2:
                                                ins_statement = select(Institution).where(
                                                    Institution.id == new_entry_period.institution_id,
                                                    Institution.deletedStatus == False)
                                                institution = ent_session.exec(ins_statement).first()

                                                amount = 0
                                                if institution.rate_type == 'Individual':
                                                    for ser in employee.services:
                                                        ser_rate=ser['service_rate']
                                                    amount = int(ser_rate)
                                                else:
                                                    for sc1 in contract.services:
                                                        servi_rate1=sc1['service_rate']
                                                    amount = int(servi_rate1)
                                                
                                                statement = select(Invoice).where(
                                                    Invoice.entry_period_id == new_entry_period.id,
                                                    Invoice.deletedStatus == False)
                                                invoice = ent_session.exec(statement).first()
                                                if invoice is None:
                                                    # Increment Invoice Amount
                                                    new_invoice = Invoice(
                                                        invoice_number=generate_invoice_number(institution),
                                                        entry_period_id=new_entry_period.id,
                                                        payment_status='Pending', total_amount=amount)
                                                    ent_session.add(new_invoice)
                                                    ent_session.commit()
                                                else:
                                                    invoice.total_amount = int(
                                                        invoice.total_amount) + amount
                                                    ent_session.add(invoice)
                                                    ent_session.commit()
                                        else:
                                            return JSONResponse(
                                                content="There is no active contract for the institution of the employee",
                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                return JSONResponse(content="Entry Created Successfuly",
                                                    status_code=status.HTTP_200_OK)
                            else:
                                return JSONResponse(content="Institution was Not Found",
                                                    status_code=status.HTTP_404_NOT_FOUND)
                        else:
                            return JSONResponse(content="Sorry, Employee is Not Active",
                                                status_code=status.HTTP_400_BAD_REQUEST)
                    else:
                        return JSONResponse(content="Sorry, Employee is not allowed to access selected service",
                                                status_code=status.HTTP_400_BAD_REQUEST)
                else:
                    return JSONResponse(content="Employee  is Not Found",
                                        status_code=status.HTTP_404_NOT_FOUND)
            else:
                return JSONResponse(content="Service  is Not Found",
                                        status_code=status.HTTP_404_NOT_FOUND)
        else:
            return JSONResponse(content="User Has no Permission To Perform This Action! ",
                                status_code=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)





""""Endpoints do create employee entry with signature and serviceId"""


@entries_router.post('/entries/{uuid}/{service_id}/create/withSignature_and_service_id')
async def create_employee_entry_with_signature_image_and_serviceId(uuid: str,service_id:str, file: UploadFile,
                                                     ent_session: Session = Depends(get_session),
                                                     user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Create Employee Entry with signature and serviceId"""
    try:
        statement1 = select(Service).where(Service.id == int(service_id), Service.deleted_status == False)
        service = ent_session.exec(statement1).first()

        statement = select(Employee).where(Employee.uuid == uuid, Employee.deletedStatus == False)
        employee = ent_session.exec(statement).first()

        if user.referenceName == 'Branch' and not user.referenceId is None:
            branch_statement = select(Branch).where(Branch.id == user.referenceId,
                                                    Branch.deletedStatus == False)
            branch = ent_session.exec(branch_statement).first()
           
            if not service is None:
                if not employee is None:
                    # Check if employee is allowed to use the service
                    services=employee.services
                    has_service=False
                    for s in services:
                        if not s['service_id'] is None:
                            if s['service_id']==service.id:
                                has_service=True
                                break
                    if has_service:
                        if employee.active_status == 'Active':
                            statement = select(Institution).where(Institution.id == employee.institution_id,
                                                                Institution.deletedStatus == False)
                            institution = ent_session.exec(statement).first()

                            if not institution is None and institution.active_status == 'Active':
                                if institution.invoicing_period_type == 'Weekly':
                                    today = date.today()
                                    start = today - timedelta(days=today.weekday())
                                    end = start + timedelta(days=6)

                                    statement = select(EntryPeriod).where(
                                        EntryPeriod.institution_id == institution.id,
                                        EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                        Institution.deletedStatus == False)
                                    entry_period = ent_session.exec(statement).first()
                                    if not entry_period is None:

                                        # Check if invoice is still pending
                                        checkNotPaid = True
                                        statement = select(Invoice).where(
                                            Invoice.entry_period_id == entry_period.id,
                                            Invoice.deletedStatus == False)
                                        invoice = ent_session.exec(statement).first()
                                        if not invoice is None:
                                            if invoice.payment_status != "Pending":
                                                checkNotPaid = False

                                        if checkNotPaid:
                                            statement = select(Contract).where(
                                                Contract.institution_id == institution.id,
                                                Contract.deletedStatus == False, Contract.current == True)
                                            contract = ent_session.exec(statement).first()

                                            if not contract is None:

                                                new_otp = rand_num()
                                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                                employee_id=employee.id,
                                                                                entry_period_id=entry_period.id,
                                                                                doneAt=datetime.now(),
                                                                                branchName=branch.name,
                                                                                branchId=branch.id,
                                                                                signed=True,
                                                                                signedAt=datetime.now(),
                                                                                service_id=service.id)
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()
                                                path = os.environ[
                                                        'FILE_SOURCE'] + '/' + 'SignatureAttachments'
                                                obj = Path(path)
                                                if obj.exists():
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)
                                                    print('File Exists')
                                                else:
                                                    print('File was not existing but is being created')
                                                    os.mkdir(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)

                                                new_employee_entry.image = file_path
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                # Checking for Incrementing Invoice Amount
                                                if len(get_employee_daily_entries_by_serviceId(employee,service.id)) < 2:
                                                    ins_statement = select(Institution).where(
                                                        Institution.id == entry_period.institution_id,
                                                        Institution.deletedStatus == False)
                                                    institution = ent_session.exec(ins_statement).first()

                                                    amount = 0
                                                    ser_rate=''
                                                    if institution.rate_type == 'Individual':
                                                        for ser in employee.services:
                                                            if not ser['service_rate'] is None:
                                                                if ser['service_id']==service.id:
                                                                    ser_rate=ser['service_rate']
                                                                    break
                                                        #amount = int(ser_rate)
                                                    else:
                                                        for sc1 in contract.services:
                                                            if not sc1['service_rate'] is None:
                                                                if not sc1['service_id'] is None:
                                                                    if sc1['service_id']==service.id:
                                                                        ser_rate=sc1['service_rate']
                                                                        break
                                                    amount = float(ser_rate)

                                                    statement = select(Invoice).where(
                                                        Invoice.entry_period_id == entry_period.id,
                                                        Invoice.deletedStatus == False)
                                                    invoice = ent_session.exec(statement).first()
                                                    if invoice is None:
                                                        # Increment Invoice Amount
                                                        new_invoice = Invoice(
                                                            invoice_number=generate_invoice_number(
                                                                institution),
                                                            entry_period_id=entry_period.id,
                                                            payment_status='Pending', total_amount=amount)
                                                        ent_session.add(new_invoice)
                                                        ent_session.commit()
                                                    else:
                                                        # invoice.total_amount = int(
                                                        #     invoice.total_amount) + amount
                                                        invoice.total_amount=str((float(invoice.total_amount)+amount))
                                                        ent_session.add(invoice)
                                                        ent_session.commit()
                                            else:
                                                return JSONResponse(
                                                    content="There is no active contract for the institution of the employee",
                                                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                        else:
                                            return JSONResponse(content="Can't Sign. Invoice looks paid",
                                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                    else:
                                        statement = select(Contract).where(
                                            Contract.institution_id == institution.id,
                                            Contract.deletedStatus == False, Contract.current == True)
                                        contract = ent_session.exec(statement).first()

                                        if not contract is None:

                                            new_entry_period = EntryPeriod(institution_id=institution.id,
                                                                        startDate=datetime.combine(start,
                                                                                                    datetime.min.time()),
                                                                        endDate=datetime.combine(end,
                                                                                                    datetime.min.time()))
                                            ent_session.add(new_entry_period)
                                            ent_session.commit()

                                            new_otp = rand_num()
                                            new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                            employee_id=employee.id,
                                                                            entry_period_id=new_entry_period.id,
                                                                            doneAt=datetime.now(),
                                                                            branchName=branch.name,
                                                                            branchId=branch.id,
                                                                            signed=True,
                                                                            signedAt=datetime.now(),
                                                                            service_id=service.id)
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            if os.path.exists(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)
                                            else:
                                                os.mkdir(os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)

                                            new_employee_entry.image = file_path
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            # Checking for Incrementing Invoice Amount
                                            if len(get_employee_daily_entries_by_serviceId(employee,service.id)) < 2:
                                                ins_statement = select(Institution).where(
                                                    Institution.id == new_entry_period.institution_id,
                                                    Institution.deletedStatus == False)
                                                institution = ent_session.exec(ins_statement).first()

                                                amount = 0
                                                ser_rate=''
                                                if institution.rate_type == 'Individual':
                                                    for ser in employee.services:
                                                        if not ser['service_rate'] is None:
                                                            if ser['service_id']==service.id:
                                                                ser_rate=ser['service_rate']
                                                                break
                                                    #amount = int(ser_rate)
                                                else:
                                                    for sc1 in contract.services:
                                                        if not sc1['service_rate'] is None:
                                                            if not sc1['service_id'] is None:
                                                                if sc1['service_id']==service.id:
                                                                    ser_rate=sc1['service_rate']
                                                                    break
                                                amount = float(ser_rate)

                                                statement = select(Invoice).where(
                                                    Invoice.entry_period_id == new_entry_period.id,
                                                    Invoice.deletedStatus == False)
                                                invoice = ent_session.exec(statement).first()
                                                if invoice is None:
                                                    # Increment Invoice Amount
                                                    new_invoice = Invoice(
                                                        invoice_number=generate_invoice_number(institution),
                                                        entry_period_id=new_entry_period.id,
                                                        payment_status='Pending', total_amount=amount)
                                                    ent_session.add(new_invoice)
                                                    ent_session.commit()
                                                else:
                                                    # invoice.total_amount = int(
                                                    #     invoice.total_amount) + amount
                                                    invoice.total_amount=str((int(invoice.total_amount)+amount))
                                                    ent_session.add(invoice)
                                                    ent_session.commit()
                                        else:
                                            return JSONResponse(
                                                content="There is no active contract for the institution of the employee",
                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                elif institution.invoicing_period_type == PeriodType.Monthly:
                                    today = datetime.now()
                                    start = get_first_date_of_current_month(today.year, today.month)
                                    end = get_last_date_of_month(today.year, today.month)

                                    statement = select(EntryPeriod).where(
                                        EntryPeriod.institution_id == institution.id,
                                        EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                        Institution.deletedStatus == False)
                                    entry_period = ent_session.exec(statement).first()
                                    if entry_period is not None:
                                        checkNotPaid = True
                                        statement = select(Invoice).where(
                                            Invoice.entry_period_id == entry_period.id,
                                            Invoice.deletedStatus == False)
                                        invoice = ent_session.exec(statement).first()
                                        statement = select(Contract).where(
                                            Contract.institution_id == institution.id,
                                            Contract.deletedStatus == False, Contract.current == True)
                                        contract = ent_session.exec(statement).first()

                                        if invoice is not None:
                                            if invoice.payment_status != "Pending":
                                                checkNotPaid = False

                                        if checkNotPaid:
                                            if contract is not None:
                                                new_otp = rand_num()
                                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                                employee_id=employee.id,
                                                                                entry_period_id=entry_period.id,
                                                                                doneAt=datetime.now(),
                                                                                branchName=branch.name,
                                                                                branchId=branch.id,
                                                                                signed=True,
                                                                                signedAt=datetime.now(),
                                                                                service_id=service.id)
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                if os.path.exists(os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)
                                                else:
                                                    os.mkdir(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)

                                                new_employee_entry.image = file_path
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                # Checking for Incrementing Invoice Amount
                                                if len(get_employee_daily_entries_by_serviceId(employee,service.id)) < 2:
                                                    ins_statement = select(Institution).where(
                                                        Institution.id == entry_period.institution_id,
                                                        Institution.deletedStatus == False)
                                                    institution = ent_session.exec(ins_statement).first()
                                                    amount=0
                                                    ser_rate=''
                                                    if institution.rate_type == 'Individual':
                                                        for ser in employee.services:
                                                             if not ser['service_rate'] is None:
                                                                if ser['service_id'] ==service.id:
                                                                    ser_rate=ser['service_rate']
                                                                    break
                                                        #amount = int(ser_rate)
                                                    else:
                                                        for sc1 in contract.services:
                                                            if not sc1['service_rate'] is None:
                                                                if not sc1['service_id'] is None:
                                                                    if sc1['service_id']==service.id:
                                                                        ser_rate=sc1['service_rate']
                                                                        break
                                                    amount = float(ser_rate)

                                                    statement = select(Invoice).where(
                                                        Invoice.entry_period_id == entry_period.id,
                                                        Invoice.deletedStatus == False)
                                                    invoice = ent_session.exec(statement).first()
                                                    if invoice is None:
                                                        # Increment Invoice Amount
                                                        new_invoice = Invoice(
                                                            invoice_number=generate_invoice_number(
                                                                institution),
                                                            entry_period_id=entry_period.id,
                                                            payment_status='Pending', total_amount=amount)
                                                        ent_session.add(new_invoice)
                                                        ent_session.commit()
                                                    else:
                                                        # invoice.total_amount = update_invoice_amount(
                                                        #     entry_period.id, amount)
                                                        invoice.total_amount=str(float(invoice.total_amount)+amount)
                                                        ent_session.add(invoice)
                                                        ent_session.commit()
                                            else:
                                                return JSONResponse(
                                                    content="There is no active contract for the institution of the employee",
                                                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                        else:
                                            return JSONResponse(content="Can't Sign. Invoice looks paid",
                                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                    else:

                                        statement = select(Contract).where(
                                            Contract.institution_id == institution.id,
                                            Contract.deletedStatus == False, Contract.current == True)
                                        contract = ent_session.exec(statement).first()

                                        if contract is not None:
                                            new_entry_period = EntryPeriod(institution_id=institution.id,
                                                                        startDate=datetime.combine(start,
                                                                                                    datetime.min.time()),
                                                                        endDate=datetime.combine(end,
                                                                                                    datetime.min.time()))
                                            ent_session.add(new_entry_period)
                                            ent_session.commit()

                                            new_otp = rand_num()
                                            new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                            employee_id=employee.id,
                                                                            entry_period_id=new_entry_period.id,
                                                                            doneAt=datetime.now(),
                                                                            branchName=branch.name,
                                                                            branchId=branch.id,
                                                                            signed=True,
                                                                            signedAt=datetime.now(),
                                                                            service_id=service.id)
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            if os.path.exists(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)
                                            else:
                                                os.mkdir(os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)

                                            new_employee_entry.image = file_path
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()
                                            if len(get_employee_daily_entries_by_serviceId(employee,service.id)) < 2:
                                                ins_statement = select(Institution).where(
                                                    Institution.id == new_entry_period.institution_id,
                                                    Institution.deletedStatus == False)
                                                institution = ent_session.exec(ins_statement).first()
                                                ser_rate=''
                                                amount=0
                                                if institution.rate_type == 'Individual':
                                                    for ser in employee.services:
                                                         if not ser['service_rate'] is None:
                                                            if ser['service_id']==service.id:
                                                                ser_rate=ser['service_rate']
                                                                break
                                                    #amount = int(ser_rate)
                                                else:
                                                    for sc1 in contract.services:
                                                        if not sc1['service_rate'] is None:
                                                            if not sc1['service_id'] is None:
                                                                if sc1['service_id'] ==service.id:
                                                                    ser_rate=sc1['service_rate']
                                                                    break
                                                amount = float(ser_rate)

                                                statement = select(Invoice).where(
                                                    Invoice.entry_period_id == new_entry_period.id,
                                                    Invoice.deletedStatus == False)
                                                invoice = ent_session.exec(statement).first()
                                                if invoice is None:
                                                    # Increment Invoice Amount
                                                    new_invoice = Invoice(
                                                        invoice_number=generate_invoice_number(institution),
                                                        entry_period_id=new_entry_period.id,
                                                        payment_status='Pending', total_amount=amount)
                                                    ent_session.add(new_invoice)
                                                    ent_session.commit()
                                                else:
                                                    # invoice.total_amount = update_invoice_amount(
                                                    #     new_entry_period.id, amount)
                                                    invoice.total_amount=str((int(invoice.total_amount)+amount))
                                                    ent_session.add(invoice)
                                                    ent_session.commit()
                                        else:
                                            return JSONResponse(
                                                content="There is no active contract for the institution of the employee",
                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                elif institution.invoicing_period_type == 'Term':
                                    current_date = datetime.now()
                                    current_quarter = round((current_date.month - 1) / 3 + 1)
                                    start = datetime(current_date.year, 3 * current_quarter - 2, 1)
                                    end = datetime(current_date.year, 3 * current_quarter + 1,
                                                1) + timedelta(days=-1)

                                    statement = select(EntryPeriod).where(
                                        EntryPeriod.institution_id == institution.id,
                                        EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                        Institution.deletedStatus == False)
                                    entry_period = ent_session.exec(statement).first()
                                    if not entry_period is None:
                                        checkNotPaid = True
                                        statement = select(Invoice).where(
                                            Invoice.entry_period_id == entry_period.id,
                                            Invoice.deletedStatus == False)
                                        invoice = ent_session.exec(statement).first()

                                        if not invoice is None:
                                            if invoice.payment_status != "Pending":
                                                checkNotPaid = False

                                        if checkNotPaid:
                                            statement = select(Contract).where(
                                                Contract.institution_id == institution.id,
                                                Contract.deletedStatus == False, Contract.current == True)
                                            contract = ent_session.exec(statement).first()
                                            if not contract is None:
                                                new_otp = rand_num()
                                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                                employee_id=employee.id,
                                                                                entry_period_id=entry_period.id,
                                                                                doneAt=datetime.now(),
                                                                                branchName=branch.name,
                                                                                branchId=branch.id,
                                                                                signed=True,
                                                                                signedAt=datetime.now(),
                                                                                service_id=service.id)
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                if os.path.exists(os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)
                                                else:
                                                    os.mkdir(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)

                                                new_employee_entry.image = file_path
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                # Checking for Incrementing Invoice Amount
                                                if len(get_employee_daily_entries_by_serviceId(employee,service.id)) < 2:
                                                    ins_statement = select(Institution).where(
                                                        Institution.id == entry_period.institution_id,
                                                        Institution.deletedStatus == False)
                                                    institution = ent_session.exec(ins_statement).first()

                                                    amount = 0
                                                    ser_rate=''
                                                    if institution.rate_type == 'Individual':
                                                        for ser in employee.services:
                                                            if not ser['service_rate'] is None:
                                                                if ser['service_id']==service.id:
                                                                    ser_rate=ser['service_rate']
                                                                    break
                                                        #amount = int(ser_rate)
                                                    else:
                                                        for sc1 in contract.services:
                                                            if not sc1['service_rate'] is None:
                                                                if not sc1['service_id'] is None:
                                                                    if sc1['service_id']==service.id:
                                                                        ser_rate=sc1['service_rate']
                                                                        break
                                                    amount = float(ser_rate)

                                                    statement = select(Invoice).where(
                                                        Invoice.entry_period_id == entry_period.id,
                                                        Invoice.deletedStatus == False)
                                                    invoice = ent_session.exec(statement).first()
                                                    if invoice is None:
                                                        # Increment Invoice Amount
                                                        new_invoice = Invoice(
                                                            invoice_number=generate_invoice_number(
                                                                institution),
                                                            entry_period_id=entry_period.id,
                                                            payment_status='Pending', total_amount=amount)
                                                        ent_session.add(new_invoice)
                                                        ent_session.commit()
                                                    else:
                                                        # invoice.total_amount = int(
                                                        #     invoice.total_amount) + amount
                                                        invoice.total_amount=str((int(invoice.total_amount)+amount))
                                                        ent_session.add(invoice)
                                                        ent_session.commit()
                                            else:
                                                return JSONResponse(
                                                    content="There is no active contract for the institution of the employee",
                                                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                        else:
                                            return JSONResponse(content="Can't Sign. Invoice looks paid",
                                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                    else:

                                        statement = select(Contract).where(
                                            Contract.institution_id == institution.id,
                                            Contract.deletedStatus == False)
                                        contract = ent_session.exec(statement).first()

                                        if not contract is None:

                                            new_entry_period = EntryPeriod(institution_id=institution.id,
                                                                        startDate=datetime.combine(start,
                                                                                                    datetime.min.time()),
                                                                        endDate=datetime.combine(end,
                                                                                                    datetime.min.time()))
                                            ent_session.add(new_entry_period)
                                            ent_session.commit()

                                            new_otp = rand_num()
                                            new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                            employee_id=employee.id,
                                                                            entry_period_id=new_entry_period.id,
                                                                            doneAt=datetime.now(),
                                                                            branchName=branch.name,
                                                                            branchId=branch.id,
                                                                            signed=True,
                                                                            signedAt=datetime.now(),
                                                                            service_id=service.id)
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            if os.path.exists(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)
                                            else:
                                                os.mkdir(os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)

                                            new_employee_entry.image = file_path
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            # Checking for Incrementing Invoice Amount
                                            if len(get_employee_daily_entries_by_serviceId(employee,service.id)) < 2:
                                                ins_statement = select(Institution).where(
                                                    Institution.id == new_entry_period.institution_id,
                                                    Institution.deletedStatus == False)
                                                institution = ent_session.exec(ins_statement).first()

                                                amount = 0
                                                ser_rate=''
                                                if institution.rate_type == 'Individual':
                                                    for ser in employee.services:
                                                        if not ser['service_rate'] is None:
                                                            if ser['service_id']==service.id:
                                                                ser_rate=ser['service_rate']
                                                                break
                                                    #amount = int(ser_rate)
                                                else:
                                                    for sc1 in contract.services:
                                                        if not sc1['service_rate'] is None:
                                                            if not sc1['service_id'] is None:
                                                                if sc1['service_id']==service.id:
                                                                    ser_rate=sc1['service_rate']
                                                
                                                amount = float(ser_rate)

                                                statement = select(Invoice).where(
                                                    Invoice.entry_period_id == new_entry_period.id,
                                                    Invoice.deletedStatus == False)
                                                invoice = ent_session.exec(statement).first()
                                                if invoice is None:
                                                    # Increment Invoice Amount
                                                    new_invoice = Invoice(
                                                        invoice_number=generate_invoice_number(institution),
                                                        entry_period_id=new_entry_period.id,
                                                        payment_status='Pending', total_amount=amount)
                                                    ent_session.add(new_invoice)
                                                    ent_session.commit()
                                                else:
                                                    # invoice.total_amount = int(
                                                    #     invoice.total_amount) + amount
                                                    invoice.total_amount=str((int(invoice.total_amount)+amount))
                                                    ent_session.add(invoice)
                                                    ent_session.commit()
                                        else:
                                            return JSONResponse(
                                                content="There is no active contract for the institution of the employee",
                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


                                elif institution.invoicing_period_type == 'Semester':
                                    current_date = datetime.now()
                                    start = ''
                                    end = ''
                                    current_quarter = round((current_date.month - 1))
                                    if current_quarter < 6:
                                        start = datetime(current_date.year, 1, 1)
                                        end = datetime(current_date.year, 6, 30)
                                    else:
                                        start = datetime(current_date.year, 6, 1)
                                        end = datetime(current_date.year, 12, 31)

                                    statement = select(EntryPeriod).where(
                                        EntryPeriod.institution_id == institution.id,
                                        EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                        Institution.deletedStatus == False)
                                    entry_period = ent_session.exec(statement).first()
                                    if not entry_period is None:
                                        checkNotPaid = True
                                        statement = select(Invoice).where(
                                            Invoice.entry_period_id == entry_period.id,
                                            Invoice.deletedStatus == False)
                                        invoice = ent_session.exec(statement).first()
                                        if not invoice is None:
                                            if invoice.payment_status != "Pending":
                                                checkNotPaid = False
                                        if checkNotPaid:
                                            statement = select(Contract).where(
                                                Contract.institution_id == institution.id,
                                                Contract.deletedStatus == False, Contract.current == True)
                                            contract = ent_session.exec(statement).first()
                                            if not contract is None:

                                                new_otp = rand_num()
                                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                                employee_id=employee.id,
                                                                                entry_period_id=entry_period.id,
                                                                                doneAt=datetime.now(),
                                                                                branchName=branch.name,
                                                                                branchId=branch.id,
                                                                                signed=True,
                                                                                signedAt=datetime.now(),
                                                                                service_id=service.id)
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                if os.path.exists(os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)
                                                else:
                                                    os.mkdir(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)

                                                new_employee_entry.image = file_path
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                # Checking for Incrementing Invoice Amount
                                                if len(get_employee_daily_entries_by_serviceId(employee,service.id)) < 2:
                                                    ins_statement = select(Institution).where(
                                                        Institution.id == entry_period.institution_id,
                                                        Institution.deletedStatus == False)
                                                    institution = ent_session.exec(ins_statement).first()

                                                    amount = 0
                                                    ser_rate=''
                                                    if institution.rate_type == 'Individual':
                                                        for ser in employee.services:
                                                            if not ser['service_rate'] is None:
                                                                if ser['service_id']==service.id: 
                                                                    ser_rate=ser['service_rate']
                                                                    break
                                                        #amount = int(ser_rate)
                                                    else:
                                                        for sc1 in contract.services:
                                                            if not sc1['service_rate'] is None:
                                                                if not sc1['service_id'] is None:
                                                                    if sc1['service_id']==service.id:
                                                                        ser_rate=sc1['service_rate']
                                                                        break
                                                    
                                                    amount = float(ser_rate)

                                                    statement = select(Invoice).where(
                                                        Invoice.entry_period_id == entry_period.id,
                                                        Invoice.deletedStatus == False)
                                                    invoice = ent_session.exec(statement).first()
                                                    if invoice is None:
                                                        # Increment Invoice Amount
                                                        new_invoice = Invoice(
                                                            invoice_number=generate_invoice_number(
                                                                institution),
                                                            entry_period_id=entry_period.id,
                                                            payment_status='Pending', total_amount=amount)
                                                        ent_session.add(new_invoice)
                                                        ent_session.commit()
                                                    else:
                                                        # invoice.total_amount = int(
                                                        #     invoice.total_amount) + amount
                                                        invoice.total_amount=str((float(invoice.total_amount)+amount))
                                                        ent_session.add(invoice)
                                                        ent_session.commit()
                                            else:
                                                return JSONResponse(
                                                    content="There is no active contract for the institution of the employee",
                                                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                        else:
                                            return JSONResponse(content="Can't Sign. Invoice looks paid",
                                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                    else:

                                        statement = select(Contract).where(
                                            Contract.institution_id == institution.id,
                                            Contract.deletedStatus == False, Contract.current == True)
                                        contract = ent_session.exec(statement).first()

                                        if not contract is None:

                                            new_entry_period = EntryPeriod(institution_id=institution.id,
                                                                        startDate=datetime.combine(start,
                                                                                                    datetime.min.time()),
                                                                        endDate=datetime.combine(end,
                                                                                                    datetime.min.time()))
                                            ent_session.add(new_entry_period)
                                            ent_session.commit()

                                            new_otp = rand_num()
                                            new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                            employee_id=employee.id,
                                                                            entry_period_id=new_entry_period.id,
                                                                            doneAt=datetime.now(),
                                                                            branchName=branch.name,
                                                                            branchId=branch.id,
                                                                            signed=True,
                                                                            signedAt=datetime.now(),
                                                                            service_id=service.id)
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            if os.path.exists(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)
                                            else:
                                                os.mkdir(os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)

                                            new_employee_entry.image = file_path
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            # Checking for Incrementing Invoice Amount
                                            if len(get_employee_daily_entries_by_serviceId(employee,service.id)) < 2:
                                                ins_statement = select(Institution).where(
                                                    Institution.id == new_entry_period.institution_id,
                                                    Institution.deletedStatus == False)
                                                institution = ent_session.exec(ins_statement).first()

                                                amount = 0
                                                ser_rate=''
                                                if institution.rate_type == 'Individual':
                                                    for ser in employee.services:
                                                        if not ser['service_rate'] is None:
                                                            if ser['service_id'] ==service.id:
                                                                ser_rate=ser['service_rate']
                                                    #amount = int(ser_rate)
                                                else:
                                                    for sc1 in contract.services:
                                                        if not sc1['service_rate'] is None:
                                                            if not sc1['service_id'] is None:
                                                                if sc1['service_id']==service.id:
                                                                    ser_rate=sc1['service_rate']
                                                amount = float(ser_rate)

                                                statement = select(Invoice).where(
                                                    Invoice.entry_period_id == new_entry_period.id,
                                                    Invoice.deletedStatus == False)
                                                invoice = ent_session.exec(statement).first()
                                                if invoice is None:
                                                    # Increment Invoice Amount
                                                    new_invoice = Invoice(
                                                        invoice_number=generate_invoice_number(institution),
                                                        entry_period_id=new_entry_period.id,
                                                        payment_status='Pending', total_amount=amount)
                                                    ent_session.add(new_invoice)
                                                    ent_session.commit()
                                                else:
                                                    # invoice.total_amount = int(
                                                    #     invoice.total_amount) + amount
                                                    invoice.total_amount=str((float(invoice.total_amount)+amount))
                                                    ent_session.add(invoice)
                                                    ent_session.commit()
                                        else:
                                            return JSONResponse(
                                                content="There is no active contract for the institution of the employee",
                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                elif institution.invoicing_period_type == 'Annaly':
                                    today = datetime.now()
                                    start = date(date.today().year, 1, 1)
                                    end = date(date.today().year, 12, 31)

                                    statement = select(EntryPeriod).where(
                                        EntryPeriod.institution_id == institution.id,
                                        EntryPeriod.startDate == start, EntryPeriod.endDate == end,
                                        Institution.deletedStatus == False)
                                    entry_period = ent_session.exec(statement).first()
                                    if not entry_period is None:
                                        checkNotPaid = True
                                        statement = select(Invoice).where(
                                            Invoice.entry_period_id == entry_period.id,
                                            Invoice.deletedStatus == False)
                                        invoice = ent_session.exec(statement).first()
                                        if not invoice is None:
                                            if invoice.payment_status != "Pending":
                                                checkNotPaid = False

                                        if checkNotPaid:

                                            statement = select(Contract).where(
                                                Contract.institution_id == institution.id,
                                                Contract.deletedStatus == False, Contract.current == True)
                                            contract = ent_session.exec(statement).first()

                                            if not contract is None:

                                                new_otp = rand_num()
                                                new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                                employee_id=employee.id,
                                                                                entry_period_id=entry_period.id,
                                                                                doneAt=datetime.now(),
                                                                                branchName=branch.name,
                                                                                branchId=branch.id,
                                                                                signed=True,
                                                                                signedAt=datetime.now(),
                                                                                service_id=service.id)
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                if os.path.exists(os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)
                                                else:
                                                    os.mkdir(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                    file_path = os.environ[
                                                                    'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                        new_employee_entry.uuid) + '_' + file.filename
                                                    with open(f'{file_path}', 'wb') as buffer:
                                                        shutil.copyfileobj(file.file, buffer)

                                                new_employee_entry.image = file_path
                                                ent_session.add(new_employee_entry)
                                                ent_session.commit()

                                                # Checking for Incrementing Invoice Amount
                                                if len(get_employee_daily_entries_by_serviceId(employee,service.id)) < 2:
                                                    ins_statement = select(Institution).where(
                                                        Institution.id == entry_period.institution_id,
                                                        Institution.deletedStatus == False)
                                                    institution = ent_session.exec(ins_statement).first()

                                                    amount = 0
                                                    ser_rate=''
                                                    if institution.rate_type == 'Individual':
                                                        for ser in employee.services:
                                                            if not ser['service_rate'] is None:
                                                                if ser['service_id'] ==service.id:
                                                                    ser_rate=ser['service_rate']
                                                        #amount = int(ser_rate)
                                                    else:
                                                        statement = select(Contract).where(
                                                                Contract.institution_id == institution.id,
                                                                Contract.deletedStatus == False)
                                                        contract = ent_session.exec(statement).first()

                                                        for sc in contract.services:
                                                            if not sc['service_rate'] is None:
                                                                if not sc['service_id'] is None:
                                                                    if sc['service_id'] ==service.id:
                                                                        ser_rate=sc['service_rate']
                                                    amount = float(ser_rate)

                                                    statement = select(Invoice).where(
                                                        Invoice.entry_period_id == entry_period.id,
                                                        Invoice.deletedStatus == False)
                                                    invoice = ent_session.exec(statement).first()
                                                    if invoice is None:
                                                        # Increment Invoice Amount
                                                        new_invoice = Invoice(
                                                            invoice_number=generate_invoice_number(
                                                                institution),
                                                            entry_period_id=entry_period.id,
                                                            payment_status='Pending', total_amount=amount)
                                                        ent_session.add(new_invoice)
                                                        ent_session.commit()
                                                    else:
                                                        # invoice.total_amount = int(
                                                        #     invoice.total_amount) + amount
                                                        invoice.total_amount=str((float(invoice.total_amount)+amount))
                                                        ent_session.add(invoice)
                                                        ent_session.commit()
                                            else:
                                                return JSONResponse(
                                                    content="There is no active contract for the institution of the employee",
                                                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
                                        else:
                                            return JSONResponse(content="Can't Sign. Invoice looks paid",
                                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                    else:

                                        statement = select(Contract).where(
                                            Contract.institution_id == institution.id,
                                            Contract.deletedStatus == False, Contract.current == True)
                                        contract = ent_session.exec(statement).first()

                                        if not contract is None:
                                            new_entry_period = EntryPeriod(institution_id=institution.id,
                                                                        startDate=datetime.combine(start,
                                                                                                    datetime.min.time()),
                                                                        endDate=datetime.combine(end,
                                                                                                    datetime.min.time()))
                                            ent_session.add(new_entry_period)
                                            ent_session.commit()

                                            new_otp = rand_num()
                                            new_employee_entry = EmployeeEntry(signature=new_otp,
                                                                            employee_id=employee.id,
                                                                            entry_period_id=new_entry_period.id,
                                                                            doneAt=datetime.now(),
                                                                            branchName=branch.name,
                                                                            branchId=branch.id,
                                                                            signed=True,
                                                                            signedAt=datetime.now(),
                                                                            service_id=service.id)
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            if os.path.exists(os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments'):
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)
                                            else:
                                                os.mkdir(os.environ[
                                                            'FILE_SOURCE'] + '/' + 'SignatureAttachments')
                                                file_path = os.environ[
                                                                'FILE_SOURCE'] + '/' + 'SignatureAttachments/' + str(
                                                    new_employee_entry.uuid) + '_' + file.filename
                                                with open(f'{file_path}', 'wb') as buffer:
                                                    shutil.copyfileobj(file.file, buffer)

                                            new_employee_entry.image = file_path
                                            ent_session.add(new_employee_entry)
                                            ent_session.commit()

                                            # Checking for Incrementing Invoice Amount
                                            if len(get_employee_daily_entries_by_serviceId(employee,service.id)) < 2:
                                                ins_statement = select(Institution).where(
                                                    Institution.id == new_entry_period.institution_id,
                                                    Institution.deletedStatus == False)
                                                institution = ent_session.exec(ins_statement).first()

                                                amount = 0
                                                ser_rate=''
                                                if institution.rate_type == 'Individual':
                                                    for ser in employee.services:
                                                        if not ser['service_rate'] is None:
                                                            if ser['service_id'] ==service.id:
                                                                ser_rate=ser['service_rate']
                                                                break
                                                    #amount = int(ser_rate)
                                                else:
                                                    for sc1 in contract.services:
                                                        if not sc1['service_rate'] is None:
                                                            if not sc1['service_id'] is None:
                                                                if sc1['service_id'] ==service.id:
                                                                    ser_rate=sc1['service_rate']
                                                                    break

                                                amount = float(ser_rate)

                                                statement = select(Invoice).where(
                                                    Invoice.entry_period_id == new_entry_period.id,
                                                    Invoice.deletedStatus == False)
                                                invoice = ent_session.exec(statement).first()
                                                if invoice is None:
                                                    # Increment Invoice Amount
                                                    new_invoice = Invoice(
                                                        invoice_number=generate_invoice_number(institution),
                                                        entry_period_id=new_entry_period.id,
                                                        payment_status='Pending', total_amount=amount)
                                                    ent_session.add(new_invoice)
                                                    ent_session.commit()
                                                else:
                                                    # invoice.total_amount = int(
                                                    #     invoice.total_amount) + amount
                                                    invoice.total_amount=str((float(invoice.total_amount)+amount))
                                                    ent_session.add(invoice)
                                                    ent_session.commit()
                                        else:
                                            return JSONResponse(
                                                content="There is no active contract for the institution of the employee",
                                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

                                return JSONResponse(content="Entry Created Successfuly",
                                                    status_code=status.HTTP_200_OK)
                            else:
                                return JSONResponse(content="Institution was Not Found",
                                                    status_code=status.HTTP_404_NOT_FOUND)
                        else:
                            return JSONResponse(content="Sorry, Employee is Not Active",
                                                status_code=status.HTTP_400_BAD_REQUEST)
                    else:
                        return JSONResponse(content="Sorry, Employee is not allowed to access selected service",
                                                status_code=status.HTTP_400_BAD_REQUEST)
                else:
                    return JSONResponse(content="Employee  is Not Found",
                                        status_code=status.HTTP_404_NOT_FOUND)
            else:
                return JSONResponse(content="Service  is Not Found",
                                        status_code=status.HTTP_404_NOT_FOUND)
        else:
            return JSONResponse(content="User Has no Permission To Perform This Action! ",
                                status_code=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)



def get_employee_daily_entries_by_serviceId(employee,serviceId):
    list_entries = []
    with Session(engine) as ent_session:
        try:
            statement = select(EmployeeEntry).where(EmployeeEntry.deletedStatus == False,
                                                    EmployeeEntry.employee_id == employee.id,EmployeeEntry.service_id==serviceId)
            result = ent_session.exec(statement).all()
            
            if len(result) > 0:
                for r in result:
                    check_date = r.signedAt
                    if check_date.strftime('%Y-%m-%d') == datetime.now().strftime('%Y-%m-%d'):
                        list_entries.append(r)
                return list_entries
            else:
                return list_entries
        except Exception as e:
            print(e)
            return list_entries
