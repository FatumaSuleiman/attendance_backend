from typing import List, Dict, Union

from fastapi import APIRouter, Security, security, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import select,Session
from starlette.responses import JSONResponse
from models import Institution,InstitutionBase,Employee,InstitutionDeactivate
from fastapi import FastAPI, status
from database import engine
from auth import AuthHandler

institution_router = APIRouter()
#institution_session=Session(bind=engine)

auth_handler = AuthHandler()


def get_session():
    with Session(engine) as session:
        yield session

@institution_router.post('/institutions/save',response_model=Institution,tags=["Institution"])
async def register_institution(institution:InstitutionBase,institution_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Create Institution""" 

    try:
       
            new_institution =Institution(name=institution.name,email=institution.email,phone=institution.phone,address=institution.address,commissionType=institution.commissionType,commission=institution.commission,rate_type=institution.rate_type,invoicing_period_type=institution.invoicing_period_type,active_status='Active')
            institution_session.add(new_institution)
            institution_session.commit()
            return new_institution
    except Exception as e:
        print(e)
        return JSONResponse(content="Error:"+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@institution_router.get('/institutions',tags=["Institution"])
async def fetch_institutions(institution_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Return Institutions """

    try:
        statement = select(Institution).where(Institution.deletedStatus==False)
        result = institution_session.exec(statement).all()
        if result is not None:
            return result
        else:
            return JSONResponse(content="Institution  Not Found",status_code=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        print(e)
        return JSONResponse(content="Error:"+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@institution_router.get('/institutions/{institution_id}/',response_model=Institution,tags=["Institution"])
async def fetch_institution_detail(institution_id:int,institution_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Return Institution_id Detail """

    try:
        statement = select(Institution).where(Institution.id==institution_id,Institution.deletedStatus==False)
        result = institution_session.exec(statement).first()
        if result is not None:
            return result
        else:
            return JSONResponse(content="Institution with"+str(institution_id)+"Not Found",status_code=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        print(e)
        return JSONResponse(content="Error:"+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@institution_router.put('/institutions/{institution_id}/update',response_model=Institution,tags=["Institution"])
async def update_institution_app(institution_id:int,institution:InstitutionBase,institution_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Update Institution Data """

    try:
        statement = select(Institution).where(Institution.id==institution_id,Institution.deletedStatus==False)
        result = institution_session.exec(statement).first()

        if not result is None:
            result.name=institution.name
            result.email=institution.email
            result.phone= institution.phone
            result.address=institution.address
            result.rate_type= institution.rate_type
            result.commissionType=institution.commissionType
            result.commission= institution.commission
            result.invoicing_period_type=institution.invoicing_period_type
        
            institution_session.add(result)
            institution_session.commit()
            return result
        else:
            return JSONResponse(content="Institution with "+str(institution_id)+" Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error:"+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)



@institution_router.get('/institutions/{institution_id}/employees/',tags=["Institution"])
async def fetch_institution_employees(institution_id:int,institution_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):

    """ Endpoint to Fetch Institution Employees """

    statement = select(Employee).where(Employee.institution_id==institution_id,Employee.deletedStatus==False)
    results = institution_session.exec(statement).all()
  
    return results
   

@institution_router.delete('/institutions/{institution_id}/delete/',response_model=Institution,tags=["Institution"])
async def delete_institution(institution_id:int,institution_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to delete Institution """ 

    try:
        statement = select(Institution).where(Institution.id==institution_id,Institution.deletedStatus==False)
        result = institution_session.exec(statement).first()

        if not result is None:
            result.deletedStatus=True
            institution_session.add(result)
            institution_session.commit()

            return result
        else:
            return JSONResponse(content="Institution with "+str(institution_id)+" Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error:"+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@institution_router.put('/institutions/{institution_id}/activate',response_model=Institution,tags=["Institution"])
async def Activate_Institution(institution_id:int,institution_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Activate Institution  """

    try:
        statement = select(Institution).where(Institution.id==institution_id,Institution.deletedStatus==False)
        result = institution_session.exec(statement).first()

        if not result is None:
            result.active_status = 'Active'
            institution_session.add(result)
            institution_session.commit()
            return result
        else:
            return JSONResponse(content="Contract  Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@institution_router.put('/institutions/{institution_id}/deactivate/',response_model=Institution,tags=["Institution"])
async def Deactivate_Institution(institution_id:int,ins:InstitutionDeactivate,institution_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Deactivate Institution  """

    try:
        statement = select(Institution).where(Institution.id==institution_id,Institution.deletedStatus==False)
        result = institution_session.exec(statement).first()

        if not result is None:
            result.active_status = 'Suspended'
            result.active_status_reason=ins.deactivation_reason
            institution_session.add(result)
            institution_session.commit()
            return result
        else:
            return JSONResponse(content="Contract  Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
