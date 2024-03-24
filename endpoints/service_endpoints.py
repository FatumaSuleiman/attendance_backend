from typing import List, Dict, Union
from fastapi import APIRouter, Security, security, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import select, Session, col
from starlette.responses import JSONResponse
from models import Service, ServiceBase
from fastapi import FastAPI, status, UploadFile
from database import engine
from auth import AuthHandler
import shutil
import os
import sqlalchemy

service_router = APIRouter()

auth_handler = AuthHandler()

def get_session():
    with Session(engine) as session:
        yield session
    
@service_router.post('/service/create',response_model= Service, tags=["Services"])
async def create_service(
    serv: ServiceBase,
    service_session: Session = Depends(get_session),
    user=Depends(auth_handler.get_current_user)
    ):
    """Endpoint to create a service"""

    try:
        new_service= Service(name=serv.name, description= serv.description)
        service_session.add(new_service)
        service_session.commit()
        return new_service
    except Exception as e:
        return JSONResponse(
            content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    


@service_router.put(
    '/service/{serv_id}/activate-deactivate', response_model=Service, tags=["Services"]
)
async def activate_deactivate_service(
    serv_id: int,
    service_session: Session = Depends(get_session),
    user=Depends(auth_handler.get_current_user),
):
    """Endpoint to Activate/deactivateservice"""

    try:
        statement=select(Service).where(Service.id==serv_id, Service.deleted_status == False)
        result = service_session.exec(statement).first()

        if not result is None:
            result.is_available=not result.is_available
            service_session.add(result)
            service_session.commit()

            return result
        else:
            return JSONResponse(
                content="Service with " + str(serv_id) + "Not Found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        
    except Exception as e:
        print(e)
        return JSONResponse(
            content="Error: " + str(e),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@service_router.put(
    "/service/update/{serv_id}", response_model=Service, tags=["Services"]
)
async def update_service(
    serv_id: int,service:ServiceBase,
    service_session: Session = Depends(get_session),
    user=Depends(auth_handler.get_current_user),
):
    """Endpoint to Update service"""

    try:
        statement=select(Service).where(Service.id==serv_id, Service.deleted_status == False)
        result = service_session.exec(statement).first()

        if not result is None:
            result.name=service.name,
            result.description=service.description
            service_session.add(result)
            service_session.commit()

            return result
        else:
            return JSONResponse(
                content="Service with " + str(serv_id) + "Not Found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        
    except Exception as e:
        print(e)
        return JSONResponse(
            content="Error: " + str(e),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    


@service_router.get("/services/all", tags=["Services"])
async def fetch_all_services(
    service_session: Session = Depends(get_session),
    user=Depends(auth_handler.get_current_user),
):
    """Endpoint to Fetch All Services"""

    statement= select(Service).where(Service.deleted_status == False)
    results=service_session.exec(statement).all()

    return results




@service_router.get("/services/{serv_id}/get/", tags=["Services"])
async def fetch_service_by_id(
    serv_id: int,
    service_session: Session = Depends(get_session),
    user=Depends(auth_handler.get_current_user),
):
    """Endpoint to Fetch A Service by ID"""

    statement= select(Service).where(
        Service.id == serv_id,
        Service.is_available == True,
        Service.deleted_status == False
    )
    results=service_session.exec(statement).first()

    return results

@service_router.delete('/services/{serv_id}/delete/',response_model=Service,tags=["Services"])
async def delete_service(
    serv_id:int, 
    service_session: Session = Depends(get_session),
    user=Depends(auth_handler.get_current_user),
):
    """Endpoint to delete a service"""

    try: 
        statement = select(Service).where(Service.id==serv_id,Service.deleted_status==False)
        result=service_session.exec(statement).first()
        
        if not result is None:
            result.deleted_status=True
            service_session.add(result)
            service_session.commit()

            return result
        else:
            return JSONResponse(content="Service with "+str(serv_id)+" Not Found",status_code=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
