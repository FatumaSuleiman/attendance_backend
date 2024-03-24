
from typing import List, Dict, Union

from fastapi import APIRouter, Security, security, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import select,Session
from starlette.responses import JSONResponse
from models import UserBase,User,NewUserBase,ChangePasswordBase,Institution,StaffUserBase,branchData
from fastapi import FastAPI, status
from database import engine
from auth import AuthHandler


user_router = APIRouter()
#user_session=Session(bind=engine)

auth_handler = AuthHandler()

def get_session():
    with Session(engine) as session:
        yield session

@user_router.get('/institutions/{institution_id}/users',tags=["Users"])
async def fetch_institution_users(institution_id:int,user_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    user_list=[]
    statement = select(User).where(User.referenceId==str(institution_id),User.referenceName=='Institution',User.deletedStatus==False)
    results = user_session.exec(statement).all()
    if not results is None:
        return results
    else:
        return JSONResponse(content="Data Not Found",status_code=status.HTTP_404_NOT_FOUND)

@user_router.post('/institutions/{institution_id}/users/save', response_model=User,tags=["Users"])
async def save_institution_user(institution_id:int,user:NewUserBase,user_session: Session = Depends(get_session),user1=Depends(auth_handler.get_current_user)):
    statement = select(Institution).where(Institution.id==institution_id)
    result = user_session.exec(statement).first()
    if not result is None:
        hashed_pwd = auth_handler.get_password_hash("123456")
        new_user=User(firstName=user.firstName,lastName=user.lastName,email=user.email,userName=user.email,password=hashed_pwd,is_default_password=True,referenceId=institution_id,referenceName='Institution')
        user_session.add(new_user)
        user_session.commit()

        return new_user
    else:
        return JSONResponse(content="Data Not Found",status_code=status.HTTP_400_BAD_REQUEST)


@user_router.post('/users/{user_id}/disable/', response_model=User,tags=["Users"])
async def disable_user(user_id:int,user_session: Session = Depends(get_session)):
    statement = select(User).where(User.id==user_id)
    result = user_session.exec(statement).first()
    if not result is None:
        result.is_active = not result.is_active
        user_session.add(result)
        user_session.commit()
        
        return result
    else:
        return JSONResponse(content="Data Not Found",status_code=status.HTTP_400_BAD_REQUEST)

@user_router.post('/users/{user_id}/make_user_staff/', response_model=User,tags=["Users"])
async def make_user_staff(user_id:int,user_session: Session = Depends(get_session)):
    statement = select(User).where(User.id==user_id)
    result = user_session.exec(statement).first()
    if not result is None:
        result.is_staff = not result.is_staff
        user_session.add(result)
        user_session.commit()
        
        return result
    else:
        return JSONResponse(content="Data Not Found",status_code=status.HTTP_400_BAD_REQUEST)


@user_router.put('/users/{user_id}/change_password/', response_model=User,tags=["Users"])
async def change_user_password(user_id:int,data:ChangePasswordBase,user_session: Session = Depends(get_session)):
    statement = select(User).where(User.id==user_id)
    result = user_session.exec(statement).first()
    if not result is None:
        if data.password == data.confirm_password:
            hashed_pwd = auth_handler.get_password_hash(data.password)
            result.password=hashed_pwd
            result.is_default_password=False
            user_session.add(result)
            user_session.commit()
            
            return result
        else:
             return JSONResponse(content="Password Does Not Match",status_code=status.HTTP_400_BAD_REQUEST)
    else:
        return JSONResponse(content="Data Not Found",status_code=status.HTTP_400_BAD_REQUEST)


@user_router.post('/users/save', response_model=User,tags=["Users"])
async def save_user(user:StaffUserBase,user_session: Session = Depends(get_session),user1=Depends(auth_handler.get_current_user)):
    
    try:
        print('was called')
        statement = select(User).where(User.userName==user.email,User.deletedStatus==False)
        result = user_session.exec(statement).all()
        print('length')
        print(len(result))
        if len(result)>0:
             return JSONResponse(content="User with such email already exists. Try another email",status_code=status.HTTP_400_BAD_REQUEST)
        else:
            hashed_pwd = auth_handler.get_password_hash("123456")
            new_user=User(firstName=user.firstName,lastName=user.lastName,email=user.email,userName=user.email,password=hashed_pwd,is_default_password=True,is_staff=True,role=user.role)
            user_session.add(new_user)
            user_session.commit()
            return new_user
    except Exception as e:
        return JSONResponse(content="Data Not Found",status_code=status.HTTP_400_BAD_REQUEST)

@user_router.get('/users/staff/all/',tags=["Users"])
async def fetch_staff_users(user_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    user_list=[]
    statement = select(User).where(User.is_staff==True,User.deletedStatus==False)
    results = user_session.exec(statement).all()
    if not results is None:
        return results
    else:
        return JSONResponse(content="Data Not Found",status_code=status.HTTP_404_NOT_FOUND)

@user_router.delete('/users/{user_id}/delete/', response_model=User,tags=["Users"])
async def delete_user(user_id:int,user_session: Session = Depends(get_session)):
    statement = select(User).where(User.id==user_id)
    result = user_session.exec(statement).first()
    if not result is None:
            result.deletedStatus=True
            user_session.add(result)
            user_session.commit()
            return result
    else:
        return JSONResponse(content="Data Not Found",status_code=status.HTTP_400_BAD_REQUEST)

@user_router.get('/users/{branch_id}/staff/all/',tags=["Users"])
async def fetch_branch_staff_users(branch_id:str,user_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    try:
        user_list=[]
        statement = select(User).where(User.is_staff==True,User.deletedStatus==False,User.referenceId==branch_id,User.referenceName=='Branch')
        results = user_session.exec(statement).all()
        if not results is None:
            return results
        else:
            return JSONResponse(content="Data Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@user_router.put('/users/{user_id}/switch/branch', response_model=User,tags=["Users"])
async def swith_user_branch(user_id:int,data:branchData,user_session: Session = Depends(get_session)):
    statement = select(User).where(User.id==user_id)
    result = user_session.exec(statement).first()
    if not result is None:
            result.referenceId=data.branch_id
            result.referenceName='Branch'
            user_session.add(result)
            user_session.commit()
            return result
    else:
        return JSONResponse(content="Data Not Found",status_code=status.HTTP_400_BAD_REQUEST)
