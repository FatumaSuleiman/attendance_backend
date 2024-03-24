import uvicorn
from fastapi import FastAPI,Depends,status
from database import engine,create_db_and_tables,find_user
from sqlmodel import Session,select
from models import Contract,Institution,Employee,EntryPeriod,EmployeeEntry,Invoice, Base
from sqlalchemy import Column, Integer, String
from auth import AuthHandler
from fastapi.middleware.cors import CORSMiddleware
from models import User,UserLogin
from starlette.responses import JSONResponse
from endpoints.institution_endpoints import institution_router
from endpoints.employee_endpoints import emp_router
from endpoints.contract_endpoints import cont_router
from endpoints.user_endpoints import user_router
from endpoints.entries_endpoints import entries_router
from endpoints.report_endpoints import report_router
from endpoints.branch_endpoints import branch_router
from endpoints.document_endpoints import document_router
from endpoints.invoice_endpoints import invoice_router
from endpoints.service_endpoints import service_router


tags_metadata =[
    {
        "name": "Branches",
        "description": "Operations with Branches.",
    },
        {
        "name": "Documents",
        "description": "Operations with Supporting Documents.",
    },
    {
        "name": "Institution",
        "description": "Operations with Institution.",
    },
     {
        "name": "Employees",
        "description": "Operations with Employee.",
    },
    {
        "name": "Contracts",
        "description": "Operations with Contracts.",
    },
    {
        "name": "Users",
        "description": "Operations with Users.",
    },
    {
        "name": "Services",
        "description": "Operations with Services.",
    },
    {
        "name": "Entries",
        "description": "Operations with Employee Entries.",
    },
    {
        "name": "Invoice",
        "description": "Operations with Invoice.",
    },
    

]


app = FastAPI(openapi_tags=tags_metadata)
session=Session(bind=engine)
auth_handler = AuthHandler()

app.include_router(institution_router)
app.include_router(emp_router)
app.include_router(cont_router)
app.include_router(user_router)
app.include_router(service_router)
app.include_router(entries_router)
app.include_router(report_router)
app.include_router(branch_router)
app.include_router(document_router)
app.include_router(invoice_router)


origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "https://attendancebackend.hexakomb.com/",
    "https://attendance.hexakomb.com/",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    statement = select(User).where(User.email =="admin@gmail.com")
    result = session.exec(statement).first()
    if  result is None:
        hashed_pwd = auth_handler.get_password_hash("admin")
        new_user=User(firstName="Admin",lastName="Admin",email="admin@gmail.com",userName="admin",password=hashed_pwd,is_superuser=True)
        session.add(new_user)
        session.commit()




# @app.get("/")
# async def root():
#     return {"message": "hello world"}





# Login The User

@app.post('/login')
def login(user: UserLogin):
    user_found = find_user(user.username)
    if not user_found:
        # raise HTTPException(status_code=401, detail='Invalid username and/or password')
        return JSONResponse(content="Invalid username and/or password",status_code=status.HTTP_401_UNAUTHORIZED)
    verified = auth_handler.verify_password(user.password, user_found.password)
    if not verified:
        # raise HTTPException(status_code=401, detail='Invalid username and/or password')
        return JSONResponse(content="Invalid username and/or password",status_code=status.HTTP_401_UNAUTHORIZED)
    token = auth_handler.encode_token(user_found.userName)
    return {'token': token}


@app.get('/users/profile/')
def get_user_profile(user=Depends(auth_handler.get_current_user)):
    context={
        "user": user
    }
    return context






# To run locally
if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)