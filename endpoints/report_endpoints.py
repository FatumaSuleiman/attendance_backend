from typing import List, Dict, Union

from fastapi import APIRouter, Security, security, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import select, Session
from starlette.responses import JSONResponse
from models import Institution, InstitutionBase, Employee, InstitutionDeactivate, EmployeeEntry, \
    Invoice, EntryPeriod, Contract, SupportingDocument, checkEmployeeOnetimeEntry
from fastapi import FastAPI, status
from database import engine
from auth import AuthHandler
import os
from fastapi.responses import FileResponse
from datetime import datetime, timedelta

report_router = APIRouter()
# report_session=Session(bind=engine)

auth_handler = AuthHandler()
from xhtml2pdf import pisa

import smtplib
from os.path import basename
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate

from dotenv import load_dotenv

load_dotenv('.env')

from invoice_report import (checkEmployeeRawAdded, generate_invoice, generate_invoice_attendance,fetch_list_of_employee_entries__service_and_entry_period,
                            generate_invoice_without_services,generate_invoice_attendance_with_services_or_rate)


def convert_html_to_pdf(source_html, output_filename):
    # open output file for writing (truncated binary)
    result_file = open(output_filename, "w+b")

    # convert HTML to PDF
    pisa_status = pisa.CreatePDF(source_html,  # the HTML to convert
        dest=result_file)  # file handle to recieve result

    # close output file
    result_file.close()  # close output file

    # return False on success and True on errors
    # return pisa_status.err
    return pisa_status.getFile(output_filename)


def send_expiration_Email(docs_list):
    msg = MIMEMultipart()
    msg['From'] = os.environ['WAKA_EMAIL']
    # msg['To'] = COMMASPACE.join(institution.email)
    msg['To'] = os.environ['WAKA_EMAIL']
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = 'Waka Notification Email'

    text = "This Email is to Notify you that the following Supporting Document have Expired: \n"
    i = 1
    for d in docs_list:
        text += str(i) + " - " + d.name + "\n"
        i = i + 1
    msg.attach(MIMEText(text))
    smtp = smtplib.SMTP('smtp.gmail.com', '587')
    # smtp.set_debuglevel(False)
    smtp.ehlo()
    smtp.starttls()
    smtp.ehlo()
    smtp.login(os.environ['EMAIL_HOST_USER'], os.environ['EMAIL_HOST_PASSWORD'])
    # smtp.sendmail(os.environ['EMAIL_HOST_USER'], os.environ['WAKA_EMAIL'], msg.as_string())

    smtp.sendmail(os.environ['EMAIL_HOST_USER'], os.environ['WAKA_EMAIL'], msg.as_string())
    smtp.close()


def get_session():
    with Session(engine) as session:
        yield session


@report_router.get('/entrie_periods/{period_id}/report', tags=["Invoice"])
async def generate_invoice_report(period_id: int, report_session: Session = Depends(get_session)):
    """ Endpoint to Return Invoice report """
    try:
        print('------->>>>')
        statement = select(EntryPeriod).where(EntryPeriod.id == period_id,
                                              EntryPeriod.deletedStatus == False)
        result = report_session.exec(statement).first()
        if not result is None:
            print(result)
            return FileResponse(generate_invoice(period_id))
        else:
            return JSONResponse(content="EntryPeriod with" + str(period_id )+ "Not Found",
                                status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@report_router.get('/entrie_periods/{period_id}/send/invoice_email/', tags=["Invoice"])
async def send_invoice_email(period_id: int, report_session: Session = Depends(get_session),
                             user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Return Institutions """
    try:
        print('Sending invoice to email')
        statement = select(EntryPeriod).where(EntryPeriod.id == period_id,
                                              EntryPeriod.deletedStatus == False)
        result = report_session.exec(statement).first()
        if not result is None:
            institution_statement = select(Institution).where(
                Institution.id == result.institution_id, Institution.deletedStatus == False)
            institution = report_session.exec(institution_statement).first()

            inv_statement = select(Invoice).where(Invoice.entry_period_id == result.id,
                                                  Invoice.deletedStatus == False)
            invoice = report_session.exec(inv_statement).first()

            document_statement = select(SupportingDocument).where(
                SupportingDocument.deletedStatus == False)
            documents = report_session.exec(document_statement).all()

            contr_statement = select(Contract).where(Contract.institution_id == institution.id,
                                                     Contract.deletedStatus == False)
            contract = report_session.exec(contr_statement).first()

            check = False
            check_ebm = False
            docs_list = []
            if not documents is None:
                for d in documents:
                    if d.is_active and d.expirationDate.date() < datetime.now().date():
                        check = True
                        docs_list.append(d)

                if not invoice is None and not invoice.invoice_ebm is None:
                    check_ebm = False
                else:
                    check_ebm = True

                if not check:
                    if not check_ebm:
                        text = "Dear " + institution.name + ", \n\nHere attached is your Invoice for Period from " + str(
                            result.startDate.date()) + " to " + str(result.endDate.date())
                        text = text + "\n"
                        msg = MIMEMultipart()
                        msg['From'] = os.environ['WAKA_EMAIL']
                        # msg['To'] = COMMASPACE.join(institution.email)
                        new_list = os.environ['COPY_EMAIL'].split(",")
                        new_list.append(institution.email)
                        msg['To'] = COMMASPACE.join(new_list)
                        msg['Date'] = formatdate(localtime=True)
                        msg['Subject'] = 'Invoice for ' + result.startDate.date().strftime("%B")
                        msg.attach(MIMEText(text))

                        for f in documents:
                            with open(f.path, "rb") as fil:
                                part = MIMEApplication(fil.read(), Name=basename(f.path))
                            # After the file is closed
                            part['Content-Disposition'] = 'attachment; filename="%s"' % basename(
                                f.path)
                            msg.attach(part)

                        if not contract is None:
                            # Attach Contract file

                            msg.attach(MIMEText('\n\n'))
                            with open(contract.attachment, "rb") as fil:
                                part3 = MIMEApplication(fil.read(),
                                    Name=basename(contract.attachment))
                            # After the file is closed
                            part3['Content-Disposition'] = 'attachment; filename="%s"' % basename(
                                contract.attachment)
                            msg.attach(part3)
                        msg.attach(MIMEText('\n\n'))
                        # Attach EBM
                        with open(invoice.invoice_ebm, "rb") as fil:
                            part2 = MIMEApplication(fil.read(), Name=basename(invoice.invoice_ebm))
                        # After the file is closed
                        part2['Content-Disposition'] = 'attachment; filename="%s"' % basename(
                            invoice.invoice_ebm)
                        msg.attach(part2)
                        msg.attach(MIMEText('\n\n'))
                        with open(generate_invoice(period_id), "rb") as fil:
                            part1 = MIMEApplication(fil.read(),
                                Name=basename(generate_invoice(period_id)))
                        # After the file is closed
                        part1['Content-Disposition'] = 'attachment; filename="%s"' % basename(
                            generate_invoice(period_id))
                        msg.attach(part1)

                        # Attach Invoice Attendance 
                        msg.attach(MIMEText('\n\n'))
                        with open(generate_invoice_attendance(period_id), "rb") as fil:
                            part10 = MIMEApplication(fil.read(),
                                Name=basename(generate_invoice_attendance(period_id)))
                        # After the file is closed
                        part10['Content-Disposition'] = 'attachment; filename="%s"' % basename(
                            generate_invoice_attendance(period_id))
                        msg.attach(part10)

                        smtp = smtplib.SMTP('smtp.gmail.com', '587')
                        # smtp.set_debuglevel(False)
                        smtp.ehlo()
                        smtp.starttls()
                        smtp.ehlo()
                        smtp.login(os.environ['EMAIL_HOST_USER'], os.environ['EMAIL_HOST_PASSWORD'])
                        smtp.sendmail(os.environ['EMAIL_HOST_USER'], new_list, msg.as_string())
                        smtp.close()
                        # show invoice email was sent
                        if not invoice is None:
                            invoice.invoiceEmailSent = True
                            invoice.invoiceEmailSentBy = user.userName
                            invoice.invoiceEmailSentAt = datetime.now()
                            report_session.add(invoice)
                            report_session.commit()

                        return JSONResponse(content=" Email was sent Successfuly",
                                            status_code=status.HTTP_200_OK)
                    else:
                        return JSONResponse(
                            content="Oops Email was not sent, Invoice EBM document was not set for " + str(
                                result.startDate.date()) + " to " + str(result.endDate.date()),
                            status_code=status.HTTP_400_BAD_REQUEST)
                else:
                    send_expiration_Email(docs_list)
                    return JSONResponse(
                        content="Oops Email was not sent, Some Supporting Documents Have Expired",
                        status_code=status.HTTP_400_BAD_REQUEST)
            else:
                return JSONResponse(content="Oops Email was not sent, No Supporting Document Found",
                                    status_code=status.HTTP_400_BAD_REQUEST)
        else:
            return JSONResponse(content="Entry Period Not Found",
                                status_code=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Method to generate invoice attendance report

@report_router.get('/entrie_periods/{period_id}/report/invoice_attendance', tags=["Invoice"])
async def generate_invoice_report(period_id: int, report_session: Session = Depends(get_session)):
    """ Endpoint to Return Institutions """
    try:
        statement = select(EntryPeriod).where(EntryPeriod.id == period_id,
                                              EntryPeriod.deletedStatus == False)
        result = report_session.exec(statement).first()
        if result is not None:
            return FileResponse(generate_invoice_attendance_with_services_or_rate(period_id))
        else:
            return JSONResponse(content=f"EntryPeriod with {period_id} Not Found",
                                status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@report_router.get('/invoices/total_amount/{period_id}/by_attended_services', tags=["Invoice"])
async def generate_total_amount_by_attended_services(period_id: int, report_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to generate total_amount by attended services """
    try:
        statement = select(EntryPeriod).where(EntryPeriod.id == period_id,
                                              EntryPeriod.deletedStatus == False)
        result = report_session.exec(statement).first()
        if not result is None:

            inst_statement=select(Institution).where(Institution.id==result.institution_id,Institution.deletedStatus==False)
            institution=report_session.exec(inst_statement).first()
            cont_statement=select(Contract).where(Contract.institution_id==institution.id,
                                                    Contract.current==True,Contract.deletedStatus==False)
            contract=report_session.exec(cont_statement).first()
            inv_statement=select(Invoice).where(Invoice.entry_period_id==result.id,
                                                            Invoice.deletedStatus==False)
            invoice=report_session.exec(inv_statement).first()
            if institution.rate_type=="Universal":
                sum_amount=0
                for sc in contract.services:
                        if not sc['service_id'] is None:
                            attendances=fetch_list_of_employee_entries__service_and_entry_period(period_id=period_id,serviceId=sc['service_id'])
                            if not attendances is None:
                                service_q=len(attendances)
                                service_total_amount=0
                                if  not sc['service_rate'] is None:
                                    service_total_amount=float(str(sc['service_rate']))* service_q
                                    sum_amount=sum_amount+service_total_amount
                return {"Amount":sum_amount}
        else:
            return JSONResponse(content="EntryPeriod with"+ str(period_id)+ "not found")
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@report_router.get('/entrie_periods/{period_id}/report/without_services', tags=["Invoice"])
async def generate_invoice_report_without_services(period_id: int, report_session: Session = Depends(get_session)):
    """ Endpoint to Return Invoice report by rate or services"""
    try:
        statement = select(EntryPeriod).where(EntryPeriod.id == period_id,
                                              EntryPeriod.deletedStatus == False)
        result = report_session.exec(statement).first()
        if not result is None:
            return FileResponse(generate_invoice_without_services(period_id))
        else:
            return JSONResponse(content="EntryPeriod with" + str(period_id )+ "Not Found",
                                status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: " + str(e),
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
