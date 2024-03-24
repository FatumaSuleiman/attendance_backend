from decimal import Decimal
from typing import List, Dict, Union

from fastapi import APIRouter, Security, security, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import select, Session
from starlette.responses import JSONResponse
from endpoints.employee_endpoints import getEmployee
from models import (Institution, InstitutionBase, Employee, InstitutionDeactivate, EmployeeEntry,
                    Invoice, EntryPeriod, Contract, SupportingDocument, checkEmployeeOnetimeEntry,Service )
from fastapi import FastAPI, status
from database import engine
from auth import AuthHandler
import os
from fastapi.responses import FileResponse
from datetime import datetime, timedelta

report_session = Session(bind=engine)

from xhtml2pdf import pisa

import smtplib
from os.path import basename
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate

from dotenv import load_dotenv

load_dotenv(".env")


def convert_html_to_pdf(source_html, output_filename):
    # open output file for writing (truncated binary)
    result_file = open(output_filename, "w+b")

    # convert HTML to PDF
    pisa_status = pisa.CreatePDF(source_html, dest=result_file  # the HTML to convert
                                 )  # file handle to recieve result

    # close output file
    result_file.close()  # close output file

    # return False on success and True on errors
    # return pisa_status.err
    return pisa_status.getFile(output_filename)


def generate_invoice(period_id):
    statement = select(EntryPeriod).where(EntryPeriod.id == period_id,
                                          EntryPeriod.deletedStatus == False)
    result = report_session.exec(statement).first()
    if not result is None:
        institution_statement = select(Institution).where(Institution.id == result.institution_id,
                                                          Institution.deletedStatus == False)
        institution = report_session.exec(institution_statement).first()

        contract_statement = select(Contract).where(Contract.institution_id == institution.id,
                                                    Contract.deletedStatus == False)
        contract = report_session.exec(contract_statement).first()
        due_days = datetime.now().date() + timedelta(days=contract.due_date_days)
        unitPrice = 0
        if institution.rate_type == "Universal":
            if not contract.services is None:
                for sc in contract.services:
                    servic_rate=sc['service_rate']
                unitPrice =float(str(servic_rate))
            else:
                unitPrice=contract.rate
        emp_entry_statement = select(EmployeeEntry).where(
            EmployeeEntry.entry_period_id == result.id, EmployeeEntry.deletedStatus == False,
            EmployeeEntry.signed == True, )
        entries = report_session.exec(emp_entry_statement).all()
        service_list=[]
        for en in entries:
            serv_id=en.service_id
            statement1=select(Service).where(Service.id==serv_id)
            service=report_session.exec(statement1).first()
            if not service is None:
                context={
                    'service_name':service.name
                }
                service_list.append(context)

        statement = select(Invoice).where(Invoice.entry_period_id == result.id,
                                          Invoice.deletedStatus == False)
        invoice = report_session.exec(statement).first()
        l = ""
        m = ""
        v = ""
        t = ""
        if len(entries) > 0:
            quantity = len(fetch_list_entry_period_employee_entries(period_id=period_id))
            if institution.rate_type == "Universal":
                # quantity=float(invoice.total_amount)/float(unitPrice)
                totalAmount = 0
                removeunitPriceVat = float(str(unitPrice)) - ((float(str(unitPrice)) * 18) / 100)

                # totalAmount=quantity*(removeunitPriceVat)
                #totalAmount = quantity * float(str(unitPrice))
                #servnames:str = ""
                if not contract.services is None:
                    for sc in contract.services:
                        if not sc['service_id'] is None:
                            attendances=fetch_list_of_employee_entries__service_and_entry_period(period_id=period_id,serviceId=sc['service_id'])
                            if not attendances is None:
                                service_qu=len(attendances)
                                service_t_amount=0
                                if not sc['service_rate'] is None:
                                    service_t_amount=float(str(sc['service_rate']))*service_qu
                                    totalAmount=totalAmount+service_t_amount
                                if service_qu>0:
                                    l += ('<tr>\
                                        \
                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-left:1px solid #333; border-right:1px solid #333;" align="center">'+ sc['name'] +'</td>\
                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333;" align="center">' + str(
                                        int(service_qu)) + '</td>\
                                                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333;" align="center">' +str( sc['service_rate']) + '</td>\
                                                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333;" align="center">18%</td>\
                                                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333;" align="center">' + str(
                                        service_t_amount) + "</td>\
                                        </tr>")
            else:
                l += ('<tr>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-left:1px solid #333; border-right:1px solid #333;" height="32" align="center">Gym services from ' + str(
                    result.startDate.date()) + " to " + str(result.endDate.date()) + '</td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333;" align="center">' + str(
                    len(entries)) + '</td>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333;" align="center">xxxxxxxxx</td>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333;" align="center">18%</td>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333;" align="center">' + invoice.total_amount + "</td>\
                    </tr>")
        if len(entries) > 0:
            totalAmount = 0
            totalAmount = quantity * (float(str(unitPrice)))

            removeunitPriceVat = float(str(unitPrice)) - ((float(str(unitPrice)) * 18) / 100)
            total=0
            if not contract.services is None:
                for sc in contract.services:
                    if not sc['service_id'] is None:
                        attendances=fetch_list_of_employee_entries__service_and_entry_period(period_id=period_id,serviceId=sc['service_id'])
                        if not attendances is None:
                            service_qu=len(attendances)
                            service_t_amount=0
                            if not sc['service_rate'] is None:
                                service_t_amount=float(str(sc['service_rate']))*service_qu
                                total = total+service_t_amount
                            
            vat = (total) - (total / 1.18)
            vatstr = str(round(vat, 2))
            m += ('<tr>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px " height="32" align="center"></td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center"></td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center"></td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center">SubTotal</td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center">' + str() + "</td>\
                </tr>")
            v += ('<tr>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px " height="32" align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center">Total VAT 18%</td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center">' + vatstr + "</td>\
                    </tr>")
            t += ('<tr>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px " height="32" align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center"><strong>Total RWF</strong></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center"><strong>' + str(
                total) + "</strong></td>\
                    </tr>")
        else:
            m += '<tr>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px " height="32" align="center"></td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center"></td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center"></td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center">SubTotal</td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center">0</td>\
                </tr>'

            v += '<tr>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px " height="32" align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center">Total VAT 18%</td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center">0</td>\
                    </tr>'
            t += '<tr>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px " height="32" align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center"><strong>Total RWF</strong></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center"><strong>0</strong></td>\
                    </tr>'

        output_filename = "invoice.pdf"
        source_html = ('<div style="margin-left:570px; margin-top: 10px;">\
                <img style="display:none" src="htmlDocs/img/rwandaful_launch_logo.png" width="80"  />\
                </div>\
                <div style="margin-left:565px;">\
                <img src="htmlDocs/img/Waka_Logo.png" width="135"/>\
                </div>\
                    <table width="100%" border="0" cellspacing="0" cellpadding="0">\
                    <tr>\
                        <td>\
                                <table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                    <tr>\
                                        <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                            <tr>\
                                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;"><h1>Invoice</h1></td>\
                                            </tr>\
                                            <tr>\
                                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">' + institution.name + '</td>\
                                            </tr>\
                                        </table>\
                                        </td>\
                                    </tr>\
                                </table>\
                        </td>\
                        <td colspan="2"></td>\
                        <td width="80%">\
                                <table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                    <tr>\
                                    <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                            <tr>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;">Invoice Date</td>\
                                            </tr>\
                                            <tr>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">' + str(
            datetime.now().date()) + '</td>\
                                            </tr>\
                                        </td>\
                                    </tr>\
                                    <tr>\
                                        <td colspan="2"> </td>\
                                    </tr>\
                                    <tr>\
                                        <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                            <tr>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;">Invoice Number</td>\
                                            </tr>\
                                            <tr>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">' + invoice.invoice_number + '</td>\
                                            </tr>\
                                            </table>\
                                        </td>\
                                    </tr>\
                                    </table>\
                        </td>\
                        <td></td>\
                        <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                            <tr>\
                                <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                    <tr>\
                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;">WAKA FITNESS LTD</td>\
                                    </tr>\
                                    <tr>\
                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">18 KG 674 St</td>\
                                    </tr>\
                                    <tr>\
                                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">Kimihurura</td>\
                                    </tr>\
                                    <tr>\
                                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">KIGALI</td>\
                                    </tr>\
                                    <tr>\
                                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">RWANDA</td>\
                                    </tr>\
                                </table>\
                                </td>\
                            </tr>\
                        </table>\
                    </td>\
                </tr>\
                    </table>\
                </tr>\
                <tr>\
                    <td colspan="2"> </td>\
                </tr>\
                <tr>\
                    <td width="40%"><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                        <tr>\
                        <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                <tr>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;">Reference</td>\
                                </tr>\
                                <tr>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">' + invoice.invoice_number + '</td>\
                                </tr>\
                            </td>\
                        </tr>\
                        <tr>\
                            <td colspan="2"> </td>\
                        </tr>\
                        <tr>\
                            <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                <tr>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;">TIN Number</td>\
                                </tr>\
                                <tr>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">103006692</td>\
                                </tr>\
                                <tr>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px;">Description</td>\
                                </tr>\
                                <tr>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">services from '+str(result.startDate.date()) + " to " + str(result.endDate.date())+'</td>\
                                </tr>\
                            </td>\
                        </tr>\
                    </table>\
                    </table>\
                    </td>\
                    </tr>\
                    </table></td>\
                </tr>\
                <tr>\
                    <td colspan="2"> </td>\
                </tr>\
                <tr>\
                    <td colspan="4"><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                    <tr>\
                        \
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-left:1px solid #333; border-right:1px solid #333; padding-top:0.2em;" width="15%" align="center">Service Name</td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333; padding-top:0.2em;" width="15%" align="center">Quantity</td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333; padding-top:0.2em;" width="15%" align="center">Unit Price</td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333; padding-top:0.2em; border-right:1px solid #333;" width="15%" align="center">Tax</td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333;padding-top:0.2em; border-right:1px solid #333;" width="20%" align="center">Amount RWF</td>\
                    </tr>\
                    ' + l + '\
                    <tr>\
                        <td colspan="2"> </td>\
                    </tr>\
                        ' + m + '\
                    <tr>\
                        <td colspan="2"> </td>\
                    </tr>\
                    ' + v + '\
                    <tr>\
                        <td colspan="2"> </td>\
                        <td></td>\
                        <td>----------------------------------------</td>\
                        <td>----------------------------------------</td>\
                    </tr>\
                    ' + t + '\
                    </table></td>\
                </tr>\
                <tr>\
                    <td colspan="2"> </td>\
                </tr>\
                <tr>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" colspan="2"><strong>Due Date: ' + str(
            due_days) + '</strong></td>\
                </tr>\
                <tr>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px;" colspan="2">Account Holder: WAKA FITNESS LTD</td>\
                </tr>\
                <tr>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" colspan="2">Account number: 4490363605</td>\
                </tr>\
                <tr>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px;" colspan="2">Bank Name: BPR Bank Rwanda Plc</td>\
                </tr>\
                </table>\
                    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin-top: 20px;">\
                            <tr>\
                                <td colspan="2">\
                                    <table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                    <tr>\
                                        <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                            <tr>\
                                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;"><h1>PAYMENT ADVICE</h1></td>\
                                            </tr>\
                                            <tr>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:15px;">To: WAKA FITNESS LTD</td>\
                                            </tr>\
                                            <tr>\
                                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">18 KG 674 St,</td>\
                                            </tr>\
                                            <tr>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">Kimihurura</td>\
                                            </tr>\
                                        <tr>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">KIGALI</td>\
                                        </tr>\
                                        <tr>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">RWANDA</td>\
                                        </tr>\
                                        </table>\
                                    </td>\
                                    </tr>\
                                </table>\
                                </td>\
                                <td colspan="2">\
                                    <table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                        <tr>\
                                            <td>\
                                                <table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                                        <tr>\
                                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:15px;"><strong>Customer</strong> <span style="margin-left: 50px;">' + institution.name + '</span></td>\
                                                        </tr>\
                                                        <tr>\
                                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:15px;"><strong>Invoice Number</strong> <span style="margin-left: 50px;">' + invoice.invoice_number + '</span></td>\
                                                        </tr>\
                                                        <tr>\
                                                            <td colspan="2">----------------------------------------------------------------------------</td>\
                                                        </tr>\
                                                        <tr>\
                                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:15px;"><strong>Amount Due</strong> <span style="margin-left: 50px;">' + invoice.total_amount + '</span></td>\
                                                        </tr>\
                                                        <tr>\
                                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:15px;"><strong>Due Date</strong> <span style="margin-left: 50px;">' + str(
            due_days) + '</span></td>\
                                                        </tr>\
                                                        <tr>\
                                                        <td colspan="2">----------------------------------------------------------------------------</td>\
                                                        </tr>\
                                                        <tr>\
                                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:15px;"><strong>Amount Enclosed </strong> <span style="margin-left: 50px;"></span></td>\
                                                        </tr>\
                                                </table>\
                                            </td>\
                                        </tr>\
                                    </table>\
                                </td>\
                            </tr>\
                        </table>\
                    <div style="margin-top: 10px;">\
                    <p style="margin-left: 50px;">Company Registration No: 103006692. Phone:+250786601749. Registered Office: Attention: Dennis Dybdal, 18 KG 674 St,, Kimihurura, Kigali, Rwanda.</p>\
                    </div>')

    return convert_html_to_pdf(source_html, output_filename).uri


# Method to generate invoice attendances


def generate_invoice_attendance(period_id):
    statement = select(EntryPeriod).where(EntryPeriod.id == period_id,
                                          EntryPeriod.deletedStatus == False)
    result = report_session.exec(statement).first()
    if not result is None:
        institution_statement = select(Institution).where(Institution.id == result.institution_id,
                                                          Institution.deletedStatus == False)
        institution = report_session.exec(institution_statement).first()

        contract_statement = select(Contract).where(Contract.institution_id == institution.id,
                                                    Contract.deletedStatus == False)
        contract = report_session.exec(contract_statement).first()
        due_days = datetime.now().date() + timedelta(days=contract.due_date_days)
        unitPrice = 0
        if institution.rate_type == "Universal":
            servic=contract.services
            if not servic is None:
                for s in servic:
                    serv_r=s['service_rate']
                    servi_rate=float(serv_r)

        emp_entry_statement = (
            select(EmployeeEntry).where(EmployeeEntry.entry_period_id == result.id,
                                        EmployeeEntry.deletedStatus == False,
                                        EmployeeEntry.signed == True, ).order_by(
                EmployeeEntry.id.asc()))
        entries = report_session.exec(emp_entry_statement).all()  
        statement = select(Invoice).where(Invoice.entry_period_id == result.id,
                                          Invoice.deletedStatus == False)
        invoice = report_session.exec(statement).first()
        l = ""
        m = ""
        v = ""
        t = ""
        if len(entries) > 0:
            list = []
            show = True
            i = 1
            for e in entries:
                start_date = result.startDate.strftime("%d/%m/%Y")
                end_date = result.endDate.strftime("%d/%m/%Y")
                if checkEmployeeRawAdded(list, e.employee_id, e.doneAt):
                    show = False
                else:
                    show = True
                    obj = checkEmployeeOnetimeEntry(emp_id=e.employee_id, doneAt=e.doneAt)
                    list.append(obj)

                date_time = e.doneAt.strftime("%d/%m/%Y")

                if show and (getEmployee(e.employee_id) is not None):
                    image_available = e.image if e.image else ""
                    service_i=e.service_id
                    state=select(Service).where(Service.id==service_i)
                    service=report_session.exec(state).first()
                    l += ('<tr>\
                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-left:1px solid #333; border-right:1px solid #333;" height="32" align="center">' + str(
                        i) + '</td>\
                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-left:1px solid #333; border-right:1px solid #333;" height="32" align="center">' + getEmployee(
                        e.employee_id).firstName + " " + getEmployee(e.employee_id).lastName + '</td>\
                         <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333;" align="center">' +service.name+ '</td>\
                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333;" align="center">' + getEmployee(
                        e.employee_id).phone + '</td>\
                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333;" align="center">' + date_time + '</td>\
                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333;" align="center">' + e.branchName + '</td>\
                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333;" align="center"><img src="' + image_available + '" width="50"  /></td>\
                            </tr>')
                    i += 1
            list.clear()
        output_filename = "invoice_attendance.pdf"
        source_html = ('<div style="margin-left:570px; margin-top: 10px;">\
                <img src="htmlDocs/img/rwandaful_launch_logo.png" width="80"  />\
                </div>\
                <div style="margin-left:570px;">\
                <img src="htmlDocs/img/favicon-32x32.png" width="80"/>\
                </div>\
                    \
                </tr>\
                \
                <tr>\
                    <td width="40%"><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                        <tr>\
                        <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                \
                            </td>\
                        </tr>\
                        <tr>\
                            <td colspan="2"> </td>\
                        </tr>\
                        <tr>\
                            <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                <tr>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;">Attendance List for Invoice - ' + invoice.invoice_number + '</td>\
                                </tr>\
                                    <tr>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;">Period: ' + start_date + " - " + end_date + '</td>\
                                </tr>\
                                     <tr>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;">Institution: ' + institution.name + '</td>\
                                </tr>\
                                \
                            </td>\
                        </tr>\
                    </table>\
                    </table>\
                    </td>\
                    </tr>\
                    </table></td>\
                </tr>\
                <tr>\
                    <td colspan="2"> </td>\
                </tr>\
                <tr>\
                    <td colspan="4"><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                    <tr>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-left:1px solid #333; border-right:1px solid #333; padding-top:10px;" width="5%" height="32" align="center">#</td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-left:1px solid #333; border-right:1px solid #333; padding-top:10px;" width="30%" height="32" align="center">Names</td>\
                         <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333; padding-top:10px;" width="15%" align="center">Service Name</td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333; padding-top:10px;" width="15%" align="center">Phone</td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333; padding-top:10px;" width="15%" align="center">Attended At</td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333; padding-top:10px;" width="15%" align="center">Location</td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333; padding-top:10px;" width="20%" align="center">Signature</td>\
                    </tr>\
                    ' + l + '\
                    <tr>\
                        <td colspan="2"> </td>\
                    </tr>\
                        ' + m + '\
                    <tr>\
                        <td colspan="2"> </td>\
                    </tr>\
                    ' + v + '\
                    <tr>\
                        <td colspan="2"> </td>\
                        <td></td>\
                        \
                        <td></td>\
                    </tr>\
                    ' + t + '\
                    </table></td>\
                </tr>\
                <tr>\
                    <td colspan="2"> </td>\
                </tr>\
                \
                \
                \
                \
                \
                                </td>\
                            </tr>\
                        </table>\
                    <div style="margin-top: 10px;">\
                    <p style="margin-left: 30px;">Company Registration No: 103006692. Phone:+250786601749. Registered Office: Attention: Dennis Dybdal, 18 KG 674 St,, Kimihurura, Kigali, Rwanda.</p>\
                    </div>')

    return convert_html_to_pdf(source_html, output_filename).uri


# Check How many times employee attended per day
def checkEmployeeAttendancePerday(entries_for_period, employe_id, entry_date):
    times = 0
    for e in entries_for_period:
        time_entry = e.doneAt.strftime("%d/%m/%Y")
        time_entry1 = datetime.strptime(time_entry, "%d/%m/%Y")

        time = entry_date.strftime("%d/%m/%Y")
        time1 = datetime.strptime(time, "%d/%m/%Y")

        if e.employee_id == employe_id and time_entry1 == time1:
            times = times + 1

    return times


def checkEmployeeRawAdded(list, emp_id, date):
    added = False

    for i in list:

        time = i.doneAt.strftime("%d/%m/%Y")
        time1 = datetime.strptime(time, "%d/%m/%Y")

        time_entry = date.strftime("%d/%m/%Y")
        time_entry1 = datetime.strptime(time_entry, "%d/%m/%Y")

        if i.emp_id == emp_id and time1 == time_entry1:
            added = True

    return added


# Method to count number of entries per period
def fetch_list_entry_period_employee_entries(period_id: int):
    with Session(engine) as ent_session:

        try:
            entry_list = []
            statement = (select(EmployeeEntry).where(EmployeeEntry.entry_period_id == period_id,
                                                     EmployeeEntry.deletedStatus == False,
                                                     EmployeeEntry.signed == True, ).order_by(
                EmployeeEntry.id.asc()))
            result = ent_session.exec(statement).all()
            if len(result) > 0:
                list = []
                for r in result:
                    show = True
                    if checkEmployeeRawAdded(list, r.employee_id, r.signedAt):
                        show = False
                    else:
                        show = True
                        obj = checkEmployeeOnetimeEntry(emp_id=r.employee_id, doneAt=r.signedAt)
                        list.append(obj)
                    if show:
                        st = select(Employee).where(Employee.id == r.employee_id,
                                                    Employee.deletedStatus == False)
                        emp = ent_session.exec(st).first()
                        if emp is not None:
                            data = {"id": r.id, "firstName": emp.firstName,
                                    "lastName": emp.lastName, "phone": emp.phone,
                                    "signedAt": str(r.signedAt), "signature": r.signature,
                                    "branchName": r.branchName, "image": r.image, }
                            entry_list.append(data)
                return entry_list
        except Exception as e:

            print(e)



# Method to count number of entries per period and service 
def fetch_list_of_employee_entries__service_and_entry_period(period_id: int,serviceId:int):
    with Session(engine) as ent_session:

        try:
            entry_list = []
            statement = (select(EmployeeEntry).where(EmployeeEntry.entry_period_id == period_id,
                                                     EmployeeEntry.deletedStatus == False,
                                                     EmployeeEntry.signed == True, EmployeeEntry.service_id==serviceId ).order_by(
                EmployeeEntry.id.asc()))
            result = ent_session.exec(statement).all()
            if len(result) > 0:
                list = []
                for r in result:
                    show = True
                    if checkEmployeeRawAdded(list, r.employee_id, r.signedAt):
                        show = False
                    else:
                        show = True
                        obj = checkEmployeeOnetimeEntry(emp_id=r.employee_id, doneAt=r.signedAt)
                        list.append(obj)
                    if show:
                        st = select(Employee).where(Employee.id == r.employee_id,
                                                    Employee.deletedStatus == False)
                        emp = ent_session.exec(st).first()
                        if emp is not None:
                            data = {"id": r.id, "firstName": emp.firstName,
                                    "lastName": emp.lastName, "phone": emp.phone,
                                    "signedAt": str(r.signedAt), "signature": r.signature,
                                    "branchName": r.branchName, "image": r.image, }
                            entry_list.append(data)
                return entry_list
        except Exception as e:

            print(e)

def generate_invoice_without_services(period_id):
    statement = select(EntryPeriod).where(EntryPeriod.id == period_id,
                                          EntryPeriod.deletedStatus == False)
    result = report_session.exec(statement).first()
    if not result is None:
        institution_statement = select(Institution).where(Institution.id == result.institution_id,
                                                          Institution.deletedStatus == False)
        institution = report_session.exec(institution_statement).first()

        contract_statement = select(Contract).where(Contract.institution_id == institution.id,
                                                    Contract.deletedStatus == False)
        contract = report_session.exec(contract_statement).first()
        due_days = datetime.now().date() + timedelta(days=contract.due_date_days)
        unitPrice = 0
        if institution.rate_type == "Universal":
                if not contract.services is None:
                    check=False
                    for s in contract.services:
                        if not s['service_rate'] is None:
                            check=True
                            break
                    if check:   
                        unitPrice=s['service_rate']
                    else:
                        unitPrice = contract.rate
                else:
                    unitPrice = contract.rate

                    print("333333333333333333333333333333333333333",unitPrice)
                
        emp_entry_statement = select(EmployeeEntry).where(
            EmployeeEntry.entry_period_id == result.id, EmployeeEntry.deletedStatus == False,
            EmployeeEntry.signed == True, )
        entries = report_session.exec(emp_entry_statement).all()

        statement = select(Invoice).where(Invoice.entry_period_id == result.id,
                                          Invoice.deletedStatus == False)
        invoice = report_session.exec(statement).first()
        l = ""
        m = ""
        v = ""
        t = ""
        if len(entries) > 0:
            quantity = len(fetch_list_entry_period_employee_entries(period_id=period_id))
            if institution.rate_type == "Universal":
                # quantity=float(invoice.total_amount)/float(unitPrice)
                totalAmount = 0
                removeunitPriceVat = float(str(unitPrice)) - ((float(str(unitPrice)) * 18) / 100)

                # totalAmount=quantity*(removeunitPriceVat)
                #totalAmount = quantity * float(str(unitPrice))
                totalAmount = quantity * float(str(unitPrice))
                l += ('<tr>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-left:1px solid #333; border-right:1px solid #333;" height="32" align="center">Gym services from ' + str(
                    result.startDate.date()) + " to " + str(result.endDate.date()) + '</td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333;" align="center">' + str(
                    int(quantity)) + '</td>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333;" align="center">' + unitPrice + '</td>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333;" align="center">18%</td>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333;" align="center">' + str(
                    totalAmount) + "</td>\
                    </tr>")
            else:
                l += ('<tr>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-left:1px solid #333; border-right:1px solid #333;" height="32" align="center">Gym services from ' + str(
                    result.startDate.date()) + " to " + str(result.endDate.date()) + '</td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333;" align="center">' + str(
                    len(entries)) + '</td>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333;" align="center">xxxxxxxxx</td>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333;" align="center">18%</td>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333;" align="center">' + invoice.total_amount + "</td>\
                    </tr>")
        if len(entries) > 0:
            totalAmount = 0
            totalAmount = quantity * (float(str(unitPrice)))

            removeunitPriceVat = float(str(unitPrice)) - ((float(str(unitPrice)) * 18) / 100)
            total = quantity * (float(str(unitPrice)))
            vat = (total) - (totalAmount / 1.18)
            vatstr = str(round(vat, 2))
            m += ('<tr>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px " height="32" align="center"></td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center"></td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center"></td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center">SubTotal</td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center">' + str() + "</td>\
                </tr>")
            v += ('<tr>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px " height="32" align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center">Total VAT 18%</td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center">' + vatstr + "</td>\
                    </tr>")
            t += ('<tr>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px " height="32" align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center"><strong>Total RWF</strong></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center"><strong>' + str(
                total) + "</strong></td>\
                    </tr>")
        else:
            m += '<tr>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px " height="32" align="center"></td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center"></td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center"></td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center">SubTotal</td>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center">0</td>\
                </tr>'

            v += '<tr>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px " height="32" align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center">Total VAT 18%</td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center">0</td>\
                    </tr>'
            t += '<tr>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px " height="32" align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center"></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" align="center"><strong>Total RWF</strong></td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; " align="center"><strong>0</strong></td>\
                    </tr>'

        output_filename = "invoice.pdf"
        source_html = ('<div style="margin-left:570px; margin-top: 10px;">\
                <img style="display:none" src="htmlDocs/img/rwandaful_launch_logo.png" width="80"  />\
                </div>\
                <div style="margin-left:565px;">\
                <img src="htmlDocs/img/Waka_Logo.png" width="135"/>\
                </div>\
                    <table width="100%" border="0" cellspacing="0" cellpadding="0">\
                    <tr>\
                        <td>\
                                <table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                    <tr>\
                                        <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                            <tr>\
                                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;"><h1>Invoice</h1></td>\
                                            </tr>\
                                            <tr>\
                                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">' + institution.name + '</td>\
                                            </tr>\
                                        </table>\
                                        </td>\
                                    </tr>\
                                </table>\
                        </td>\
                        <td colspan="2"></td>\
                        <td width="80%">\
                                <table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                    <tr>\
                                    <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                            <tr>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;">Invoice Date</td>\
                                            </tr>\
                                            <tr>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">' + str(
            datetime.now().date()) + '</td>\
                                            </tr>\
                                        </td>\
                                    </tr>\
                                    <tr>\
                                        <td colspan="2"> </td>\
                                    </tr>\
                                    <tr>\
                                        <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                            <tr>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;">Invoice Number</td>\
                                            </tr>\
                                            <tr>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">' + invoice.invoice_number + '</td>\
                                            </tr>\
                                            </table>\
                                        </td>\
                                    </tr>\
                                    </table>\
                        </td>\
                        <td></td>\
                        <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                            <tr>\
                                <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                    <tr>\
                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;">WAKA FITNESS LTD</td>\
                                    </tr>\
                                    <tr>\
                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">18 KG 674 St</td>\
                                    </tr>\
                                    <tr>\
                                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">Kimihurura</td>\
                                    </tr>\
                                    <tr>\
                                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">KIGALI</td>\
                                    </tr>\
                                    <tr>\
                                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">RWANDA</td>\
                                    </tr>\
                                </table>\
                                </td>\
                            </tr>\
                        </table>\
                    </td>\
                </tr>\
                    </table>\
                </tr>\
                <tr>\
                    <td colspan="2"> </td>\
                </tr>\
                <tr>\
                    <td width="40%"><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                        <tr>\
                        <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                <tr>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;">Reference</td>\
                                </tr>\
                                <tr>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">' + invoice.invoice_number + '</td>\
                                </tr>\
                            </td>\
                        </tr>\
                        <tr>\
                            <td colspan="2"> </td>\
                        </tr>\
                        <tr>\
                            <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                <tr>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;">TIN Number</td>\
                                </tr>\
                                <tr>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">103006692</td>\
                                </tr>\
                            </td>\
                        </tr>\
                    </table>\
                    </table>\
                    </td>\
                    </tr>\
                    </table></td>\
                </tr>\
                <tr>\
                    <td colspan="2"> </td>\
                </tr>\
                <tr>\
                    <td colspan="4"><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                    <tr>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-left:1px solid #333; border-right:1px solid #333; padding-top:0.2em;" width="35%" height="32" align="center">Description</td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333; padding-top:0.2em;" width="15%" align="center">Quantity</td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333; padding-top:0.2em;" width="15%" align="center">Unit Price</td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333; padding-top:0.2em; border-right:1px solid #333;" width="15%" align="center">Tax</td>\
                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333;padding-top:0.2em; border-right:1px solid #333;" width="20%" align="center">Amount RWF</td>\
                    </tr>\
                    ' + l + '\
                    <tr>\
                        <td colspan="2"> </td>\
                    </tr>\
                        ' + m + '\
                    <tr>\
                        <td colspan="2"> </td>\
                    </tr>\
                    ' + v + '\
                    <tr>\
                        <td colspan="2"> </td>\
                        <td></td>\
                        <td>----------------------------------------</td>\
                        <td>----------------------------------------</td>\
                    </tr>\
                    ' + t + '\
                    </table></td>\
                </tr>\
                <tr>\
                    <td colspan="2"> </td>\
                </tr>\
                <tr>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" colspan="2"><strong>Due Date: ' + str(
            due_days) + '</strong></td>\
                </tr>\
                <tr>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px;" colspan="2">Account Holder: WAKA FITNESS LTD</td>\
                </tr>\
                <tr>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;" colspan="2">Account number: 4490363605</td>\
                </tr>\
                <tr>\
                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px;" colspan="2">Bank Name: BPR Bank Rwanda Plc</td>\
                </tr>\
                </table>\
                    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="margin-top: 20px;">\
                            <tr>\
                                <td colspan="2">\
                                    <table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                    <tr>\
                                        <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                            <tr>\
                                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;"><h1>PAYMENT ADVICE</h1></td>\
                                            </tr>\
                                            <tr>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:15px;">To: WAKA FITNESS LTD</td>\
                                            </tr>\
                                            <tr>\
                                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">18 KG 674 St,</td>\
                                            </tr>\
                                            <tr>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">Kimihurura</td>\
                                            </tr>\
                                        <tr>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">KIGALI</td>\
                                        </tr>\
                                        <tr>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px;">RWANDA</td>\
                                        </tr>\
                                        </table>\
                                    </td>\
                                    </tr>\
                                </table>\
                                </td>\
                                <td colspan="2">\
                                    <table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                        <tr>\
                                            <td>\
                                                <table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                                        <tr>\
                                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:15px;"><strong>Customer</strong> <span style="margin-left: 50px;">' + institution.name + '</span></td>\
                                                        </tr>\
                                                        <tr>\
                                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:15px;"><strong>Invoice Number</strong> <span style="margin-left: 50px;">' + invoice.invoice_number + '</span></td>\
                                                        </tr>\
                                                        <tr>\
                                                            <td colspan="2">----------------------------------------------------------------------------</td>\
                                                        </tr>\
                                                        <tr>\
                                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:15px;"><strong>Amount Due</strong> <span style="margin-left: 50px;">' + invoice.total_amount + '</span></td>\
                                                        </tr>\
                                                        <tr>\
                                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:15px;"><strong>Due Date</strong> <span style="margin-left: 50px;">' + str(
            due_days) + '</span></td>\
                                                        </tr>\
                                                        <tr>\
                                                        <td colspan="2">----------------------------------------------------------------------------</td>\
                                                        </tr>\
                                                        <tr>\
                                                        <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:15px;"><strong>Amount Enclosed </strong> <span style="margin-left: 50px;"></span></td>\
                                                        </tr>\
                                                </table>\
                                            </td>\
                                        </tr>\
                                    </table>\
                                </td>\
                            </tr>\
                        </table>\
                    <div style="margin-top: 10px;">\
                    <p style="margin-left: 50px;">Company Registration No: 103006692. Phone:+250786601749. Registered Office: Attention: Dennis Dybdal, 18 KG 674 St,, Kimihurura, Kigali, Rwanda.</p>\
                    </div>')

    return convert_html_to_pdf(source_html, output_filename).uri

               
                                   
              

               
            
                        
def generate_invoice_attendance_with_services_or_rate(period_id):
    statement = select(EntryPeriod).where(EntryPeriod.id == period_id,
                                          EntryPeriod.deletedStatus == False)
    result = report_session.exec(statement).first()
    if not result is None:
        institution_statement = select(Institution).where(Institution.id == result.institution_id,
                                                          Institution.deletedStatus == False)
        institution = report_session.exec(institution_statement).first()

        contract_statement = select(Contract).where(Contract.institution_id == institution.id,
                                                    Contract.deletedStatus == False)
        contract = report_session.exec(contract_statement).first()
        due_days = datetime.now().date() + timedelta(days=contract.due_date_days)
        unitPrice = 0
        if institution.rate_type == "Universal":
            check=False
            if contract.services:
                for s in contract.services:
                    if not s['service_rate'] is None:
                         check=True
                         break
                if check:
                   unitPrice=s['service_rate']
                else:
                    unitPrice = contract.rate
       
        emp_entry_statement = (
            select(EmployeeEntry).where(EmployeeEntry.entry_period_id == result.id,
                                        EmployeeEntry.deletedStatus == False,
                                        EmployeeEntry.signed == True, ).order_by(
                EmployeeEntry.id.asc()))
        entries = report_session.exec(emp_entry_statement).all()    
        statement = select(Invoice).where(Invoice.entry_period_id == result.id,
                                          Invoice.deletedStatus == False)
        invoice = report_session.exec(statement).first()
        l = ""
        m = ""
        v = ""
        t = ""
        if len(entries) > 0:
            list = []
            show = True
            i = 1
            for e in entries:
                start_date = result.startDate.strftime("%d/%m/%Y")
                end_date = result.endDate.strftime("%d/%m/%Y")
                if checkEmployeeRawAdded(list, e.employee_id, e.doneAt):
                    show = False
                else:
                    show = True
                    obj = checkEmployeeOnetimeEntry(emp_id=e.employee_id, doneAt=e.doneAt)
                    list.append(obj)

                date_time = e.doneAt.strftime("%d/%m/%Y")

                if show and (getEmployee(e.employee_id) is not None):
                    image_available = e.image if e.image else ""
                    if not e.service_id is None:
                        serv_id=e.service_id
                        ser_statement=select(Service).where(Service.id==serv_id)
                        service=report_session.exec(ser_statement).first()
                        l += ('<tr>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-left:1px solid #333; border-right:1px solid #333;" height="32" align="center">' + str(
                            i) + '</td>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-left:1px solid #333; border-right:1px solid #333;" height="32" align="center">' + getEmployee(
                            e.employee_id).firstName + " " + getEmployee(e.employee_id).lastName + '</td>\
                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333;" align="center">' +service.name+ '</td>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333;" align="center">' + getEmployee(
                            e.employee_id).phone + '</td>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333;" align="center">' + date_time + '</td>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333;" align="center">' + e.branchName + '</td>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333;" align="center"><img src="' + image_available + '" width="50"  /></td>\
                                </tr>')
                    else:
                         l += ('<tr>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-left:1px solid #333; border-right:1px solid #333;" height="32" align="center">' + str(
                            i) + '</td>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-left:1px solid #333; border-right:1px solid #333;" height="32" align="center">' + getEmployee(
                            e.employee_id).firstName + " " + getEmployee(e.employee_id).lastName + '</td>\
                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333;" align="center">' +str("")+ '</td>\
                                <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333;" align="center">' + getEmployee(
                            e.employee_id).phone + '</td>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333;" align="center">' + date_time + '</td>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333;" align="center">' + e.branchName + '</td>\
                                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:300; font-size:13px; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333;" align="center"><img src="' + image_available + '" width="50"  /></td>\
                                </tr>')
                         i += 1
                list.clear()
            output_filename = "invoice_attendance.pdf"
            source_html = ('<div style="margin-left:570px; margin-top: 10px;">\
                    <img src="htmlDocs/img/rwandaful_launch_logo.png" width="80"  />\
                    </div>\
                    <div style="margin-left:570px;">\
                    <img src="htmlDocs/img/favicon-32x32.png" width="80"/>\
                    </div>\
                        \
                    </tr>\
                    \
                    <tr>\
                        <td width="40%"><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                            <tr>\
                            <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                    \
                                </td>\
                            </tr>\
                            <tr>\
                                <td colspan="2"> </td>\
                            </tr>\
                            <tr>\
                                <td><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                                    <tr>\
                                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;">Attendance List for Invoice - ' + invoice.invoice_number + '</td>\
                                    </tr>\
                                        <tr>\
                                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;">Period: ' + start_date + " - " + end_date + '</td>\
                                    </tr>\
                                        <tr>\
                                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:15px;">Institution: ' + institution.name + '</td>\
                                    </tr>\
                                    \
                                </td>\
                            </tr>\
                        </table>\
                        </table>\
                        </td>\
                        </tr>\
                        </table></td>\
                    </tr>\
                    <tr>\
                        <td colspan="2"> </td>\
                    </tr>\
                    <tr>\
                        <td colspan="4"><table width="100%" border="0" cellspacing="0" cellpadding="0">\
                        <tr>\
                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-left:1px solid #333; border-right:1px solid #333; padding-top:10px;" width="5%" height="32" align="center">#</td>\
                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-left:1px solid #333; border-right:1px solid #333; padding-top:10px;" width="30%" height="32" align="center">Names</td>\
                                                    <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333; padding-top:10px;" width="15%" align="center">Service Names</td>\
                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333; padding-top:10px;" width="15%" align="center">Phone</td>\
                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333; padding-top:10px;" width="15%" align="center">Attended At</td>\
                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333; padding-top:10px;" width="15%" align="center">Location</td>\
                            <td style="font-family:Verdana, Geneva, sans-serif; font-weight:600; font-size:13px; border-top:1px solid #333; border-bottom:1px solid #333; border-right:1px solid #333; border-right:1px solid #333; padding-top:10px;" width="20%" align="center">Signature</td>\
                        </tr>\
                        ' + l + '\
                        <tr>\
                            <td colspan="2"> </td>\
                        </tr>\
                            ' + m + '\
                        <tr>\
                            <td colspan="2"> </td>\
                        </tr>\
                        ' + v + '\
                        <tr>\
                            <td colspan="2"> </td>\
                            <td></td>\
                            \
                            <td></td>\
                        </tr>\
                        ' + t + '\
                        </table></td>\
                    </tr>\
                    <tr>\
                        <td colspan="2"> </td>\
                    </tr>\
                    \
                    \
                    \
                    \
                    \
                                    </td>\
                                </tr>\
                            </table>\
                        <div style="margin-top: 10px;">\
                        <p style="margin-left: 30px;">Company Registration No: 103006692. Phone:+250786601749. Registered Office: Attention: Dennis Dybdal, 18 KG 674 St,, Kimihurura, Kigali, Rwanda.</p>\
                        </div>')

        return convert_html_to_pdf(source_html, output_filename).uri


