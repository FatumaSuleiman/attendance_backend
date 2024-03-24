from typing import List, Dict, Union

from fastapi import APIRouter, Security, security, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import select,Session
from starlette.responses import JSONResponse
from models import Institution,Session,Contract,BranchBase,Branch,Service,ServiceCon,BranchS
from fastapi import FastAPI, status, UploadFile
from database import engine
from auth import AuthHandler
import shutil
import os
from fastapi.responses import FileResponse

branch_router = APIRouter()
#branch_session=Session(bind=engine)
def get_session():
    with Session(engine) as session:
        yield session


auth_handler = AuthHandler()

@branch_router.post('/branches/save',response_model=Branch,tags=["Branches"])
async def create_branch(branch:BranchBase,branch_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Create Branch """ 
    try:
            service_list=[]
            for serv in branch.services:
                servic_i=serv.service_id
                statement1=select(Service).where(Service.id==servic_i)
                service=branch_session.exec(statement1).first()
                context={
                    "service_id":servic_i,
                    "name":service.name
                }
                service_list.append(context)

            new_branch =Branch(name=branch.name,description=branch.description,services=service_list)
            branch_session.add(new_branch)
            branch_session.commit()

            return new_branch
    except Exception as e:
        print(e)
        return JSONResponse(content="Error:"+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@branch_router.get('/branches/{branch_id}/',response_model=Branch,tags=["Branches"])
async def fetch_branch_detail(branch_id:int,branch_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Return Branch Detail """

    try:
        statement = select(Branch).where(Branch.id==branch_id,Branch.deletedStatus==False)
        result = branch_session.exec(statement).first()
        if result is not None:
            return result
        else:
            return JSONResponse(content="Branch with" +str(branch_id)+ "Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error:"+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@branch_router.put('/branches/{branch_id}/update',response_model=Branch,tags=["Branches"])
async def update_branch(branch_id:int,branch:BranchBase,branch_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Update  Branch Data """

    try:
        statement = select(Branch).where(Branch.id==branch_id,Branch.deletedStatus==False)
        result = branch_session.exec(statement).first()

        if not result is None:
            service_list=[]
            for serv in branch.services:
                servic_i=serv.service_id
                service_statement=select(Service).where(Service.id==servic_i)
                service=branch_session.exec(service_statement).first()
                context={
                    "service_id":servic_i,
                    "name":service.name
                }
                service_list.append(context)
            result.name=branch.name
            result.description=branch.description
            result.services=service_list
            branch_session.add(result)
            branch_session.commit()
            return result
        else:
            return JSONResponse(content="Branch with" +str(branch_id)+ "Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)



@branch_router.get('/branches',tags=["Branches"])
async def fetch_branches(branch_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):

    """ Endpoint to Fetch  Branches """

    statement = select(Branch).where(Branch.deletedStatus==False)
    results = branch_session.exec(statement).all()
  
    return results
   

@branch_router.delete('/branches/{branch_id}/delete/',response_model=Branch,tags=["Branches"])
async def delete_branch(branch_id:int,branch_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to delete a Branch  """ 

    try:
        statement = select(Branch).where(Branch.id==branch_id,Branch.deletedStatus==False)
        result = branch_session.exec(statement).first()

        if not result is None:
            result.deletedStatus=True
            branch_session.add(result)
            branch_session.commit()

            return result
        else:
            return JSONResponse(content="Branch with" +str(branch_id)+ "Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@branch_router.get('/branches/{branch_id}/available_services',tags=["Branches"])
async def fetch_branch_available_services(branch_id:int,branch_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to fetch available services for a branch """

    try:
        statement = select(Branch).where(Branch.id==branch_id,Branch.deletedStatus==False)
        result = branch_session.exec(statement).first()
        available_services=[]
        if result is not None:
            sevices1=result.services
            if not result.services is None:
                for service in sevices1:
                    available_services.append(service)
            return available_services
        else:
            return JSONResponse(content="Branch with " +str(branch_id)+ "Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@branch_router.get('/branch/{branch_id}/assigned_and_unassigned_servces',response_model=List[ServiceCon],tags=["Branches"])
async def assigned_and_unassigned_branch_services(branch_id:int,branch_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to fetch assigned and unassigned  branch services """ 

    try:
        statement = select(Branch).where(Branch.id==branch_id,Branch.deletedStatus==False)
        result = branch_session.exec(statement).first()
        serv_list=[]
        if not result is None:
            statements=select(Service).where(Service.is_available==True,Service.deleted_status==False)
            serv=branch_session.exec(statements).all()
            print('-------')
            print(serv)
            print(result.services)
            for s in serv:
                servi_i=s.id
                state=select(Service).where(Service.id==servi_i)
                servic=branch_session.exec(state).first()
                service=ServiceCon()
                service.service_id=s.id
                service.service_name=servic.name
                check=False
                if not result.services is None:
                    for sb in result.services:
                        if s.id==sb['service_id']:
                            check=True
                            break
                if check:
                    service.assigned=True
                else:
                    service.assigned=False
                serv_list.append(service)
            return serv_list

        else:
            return JSONResponse(content=" Branch with" +str(branch_id)+ " Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@branch_router.put('/branch/{branch_id}/update_branch_servces',response_model=Branch,tags=["Branches"])
async def  update_branch_services(branch_id:int,branch:BranchS,branch_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to update Branch  services """ 

    try:
        statement = select(Branch).where(Branch.id==branch_id,Branch.deletedStatus==False)
        result = branch_session.exec(statement).first()
        serv_list=[]
        if not result is None:
            statements=select(Service).where(Service.is_available==True,Service.deleted_status==False)
            servi=branch_session.exec(statements).all()
            servi=branch.services
            for s in servi:
                    servi_i=s.service_id
                    statement1=select(Service).where(Service.id==servi_i)
                    service=branch_session.exec(statement1).first()
                    servi_n=service.name
                    context={
                        "service_id":servi_i,
                        "name":servi_n

                    }
                    serv_list.append(context)
            result.services=serv_list    
           
            branch_session.add(result)
            branch_session.commit()
            return result
                   

        else:
            return JSONResponse(content="Branch with "+str(branch_id)+" Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

    


       
""""
    check = False
    available_services=[]
    if not result is None:
        service=result.services
        for s in service:
            check=True
            available_services.append(s)
    return available_services
"""

         
    




       