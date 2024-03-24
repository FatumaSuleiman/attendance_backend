from fastapi.testclient import TestClient
from fastapi import status,Depends,HTTPException,Query
from fastapi import Security
from main import app
from database import engine
from sqlmodel import select, Session
from starlette.responses import JSONResponse
from models import Service,EntryPeriod,EmployeeEntry,Employee,Branch,Invoice
import datetime
import json
from database import find_user
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from auth import AuthHandler
auth_handler=AuthHandler()
seurity=HTTPBearer()
import codecs


client=TestClient(app)

def test_get_invoice_total_amount_with_correct_period_id():
    data={"period_id":2,"total_amount":"5000",}
    response=client.get('invoices/2/amount/correct',json=data)
    assert response.status_code==200
    assert data["period_id"]==2
    assert data["total_amount"]=="5000"
 

def test_get_invoice_total_amount_with_incorrect_period_id():
    data={"period_id":9,"total_amount":5000,}
    response=client.get('invoices/9/amount/correct',json=data)
    assert response.status_code==404,response.text
    assert data["period_id"]==9
    assert{"detail":'EntryPeriod with 9 Not Found'}


def  test_generate_invoice_report_with_correct_period():
    headers = {
        "Authorization": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE2OTc1NTgzMTQsImlhdCI6MTY5NzUyOTUxNCwic3ViIjoiTXVnaXNoYUBnbWFpbC5jb20ifQ.v6xBErcOkUwOtcZgIGQE3sJkgGLEpJL9oHUGpcAM458" 
    }
    data={"id":2,"uuid":"2835b0f2-8264-4694-ae6e-b6c4e069f8f7","startDate":"2023-09-01 00:00:00","endDate":"2023-09-30 00:00:00","institution_id":2}
    response=client.get('/entrie_periods/2/report',json=data,headers=headers)
    assert response.status_code==status.HTTP_200_OK 
    assert data["id"]==2
    assert data["institution_id"]==2
  
def test_create_employee_entry_with_signature_image_and_serviceId():
    token='eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE2OTc0Nzc1NDUsImlhdCI6MTY5NzQ0ODc0NSwic3ViIjoiTXVnaXNoYUBnbWFpbC5jb20ifQ.vBYBMOJCkcjoLz2Xx3WmzmYFqDDLqRB7AwI24uDhpR4'
    response=client.post('/entries/10ebca09-9b41-4c97-acff-aaa2e92f9e74/2/create/withSignature_and_service_id',headers={"Authorization": f'Bearer {token}'})
    assert{'detail':'Entry Created Successfuly'}
      
def test_generate_total_amount_by_attended_services_with_correct_period_id():
    data={"entry_period_id":3,"total_amount":10000}
    response=client.get('/invoices/total_amount/3/by_attended_services',json=data)
    assert response.status_code==200,response.text
    assert data['entry_period_id']==3
    assert data['total_amount']==10000

def test_generate_total_amount_by_attended_services_with_incorrect_period_id():
    res =client.get('/invoices/total_amount/65/by_attended_services')
    assert res.status_code==200,res.text
    assert {"detail":"EntryPeriod with 65 not found"}

