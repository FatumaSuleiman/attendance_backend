from typing import List, Dict, Union

from fastapi import APIRouter, Security, security, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import select,Session
from starlette.responses import JSONResponse
from models import Institution,Session,Contract,ContractBase,Service,ContractS,ServiceCon
from fastapi import FastAPI, status, UploadFile
from database import engine
from auth import AuthHandler
import shutil
import os
from fastapi.responses import FileResponse
from datetime import datetime,date


cont_router = APIRouter()
#cont_session=Session(bind=engine)

def get_session():
    with Session(engine) as session:
        yield session

auth_handler = AuthHandler()

@cont_router.post('/institutions/{institution_id}/contract/save',response_model=Contract,tags=["Contracts"])
async def create_institution_contract(institution_id:int,cont:ContractBase,cont_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Create Institution Contract """ 
    try:
        statement = select(Institution).where(Institution.id==institution_id,Institution.deletedStatus==False)
        institution = cont_session.exec(statement).first()
        if not institution is None:
            dt = datetime.combine(cont.expirationDate, datetime.min.time())
            service_list=[]
            for s in cont.services:
                service_i=s.service_id
                service_r=s.service_rate
                statementS=select(Service).where(Service.id==service_i)
                sevice=cont_session.exec(statementS).first()
                service_n=sevice.name
                context={
                    "service_id":service_i,
                    "service_rate":service_r,
                    "name":service_n
                }
                service_list.append(context)
            new_contract =Contract(expirationDate=dt,institution_id=institution_id,due_date_days=cont.due_date_days,services=service_list,rate=cont.rate)
            cont_session.add(new_contract)
            cont_session.commit()

            return new_contract
        else:
            return JSONResponse(content="Institution with "+str(institution_id)+ "Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error:"+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@cont_router.get('/contracts/{contract_id}/',response_model=Contract,tags=["Contracts"])
async def fetch_contract_detail(contract_id:int,cont_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Return Contract Detail """

    try:
        statement = select(Contract).where(Contract.id==contract_id,Contract.deletedStatus==False)
        result = cont_session.exec(statement).first()
        if result is not None:
            return result
        else:
            return JSONResponse(content="Contract with"+str(contract_id)+" Not Found",status_code=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@cont_router.put('/contracts/{contract_id}/update',response_model=Contract,tags=["Contracts"])
async def update_contract(contract_id:int,cont:ContractBase,cont_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Update  Contract Data """

    try:
        statement = select(Contract).where(Contract.id==contract_id,Contract.deletedStatus==False)
        result = cont_session.exec(statement).first()

        if not result is None:
            service_list=[]
            for s in cont.services:
                service_i=s.service_id
                service_r=s.service_rate
                statement1=select(Service).where(Service.id==service_i)
                service1=cont_session.exec(statement1).first()
                name=service1.name
                context={
                    "service_id":service_i,
                    "service_rate":service_r,
                    "name":name

                }
                service_list.append(context)
            result.expirationDate=cont.expirationDate
            result.due_date_days=cont.due_date_days
            result.services=service_list
            cont_session.add(result)
            cont_session.commit()
            return result
        else:
            return JSONResponse(content="Contract with"+str(contract_id)+" Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)



@cont_router.get('/institutions/{institution_id}/contracts/',tags=["Contracts"])
async def fetch_institution_contracts(institution_id:int,cont_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):

    """ Endpoint to Fetch Institution Contracts """

    statement = select(Contract).where(Contract.institution_id==institution_id,Contract.deletedStatus==False)
    results = cont_session.exec(statement).all()
  
    return results
   

@cont_router.delete('/contracts/{contract_id}/delete/',response_model=Contract,tags=["Contracts"])
async def delete_contract(contract_id:int,cont_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to delete a Contract  """ 

    try:
        statement = select(Contract).where(Contract.id==contract_id,Contract.deletedStatus==False)
        result = cont_session.exec(statement).first()

        if not result is None:
            result.deletedStatus=True
            cont_session.add(result)
            cont_session.commit()

            return result
        else:
            return JSONResponse(content="Contract with"+str(contract_id)+" Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@cont_router.put('/contracts/{contract_id}/upload/document/',response_model=Contract,tags=["Contracts"])
async def upload_contract_attachment(contract_id:int,file: UploadFile,cont_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Upload Contract Documents """

    try:
        statement = select(Contract).where(Contract.id==contract_id,Contract.deletedStatus==False)
        result = cont_session.exec(statement).first()

        if not result is None:
            if os.path.exists(os.environ['FILE_SOURCE']+'/'+'ContractAttachments'):
                file_path=os.environ['FILE_SOURCE']+'/'+'ContractAttachments/'+str(result.uuid)+'_'+file.filename
                with open(f'{file_path}','wb') as buffer:
                    shutil.copyfileobj(file.file,buffer)
            else:
                os.mkdir(os.environ['FILE_SOURCE']+'/'+'ContractAttachments')
                file_path=os.environ['FILE_SOURCE']+'/'+'ContractAttachments/'+str(result.uuid)+'_'+file.filename
                with open(f'{file_path}','wb') as buffer:
                    shutil.copyfileobj(file.file,buffer)
            result.attachment =file_path
            cont_session.add(result)
            cont_session.commit()
            return result
        else:
            return JSONResponse(content="Contract with"+str(contract_id)+" Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@cont_router.post('/contracts/{contract_id}/set/current/status',response_model=Contract,tags=["Contracts"])
async def make_contract_current(contract_id:int,cont_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Make Contract Current """

    try:
        statement = select(Contract).where(Contract.id==contract_id,Contract.deletedStatus==False)
        result = cont_session.exec(statement).first()

        if not result is None:
            result.current = not result.current
            cont_session.add(result)
            cont_session.commit()
            return result
        else:
            return JSONResponse(content="Contract with"+str(contract_id)+" Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@cont_router.get('/contracts/{contract_id}/download/document/',tags=["Contracts"])
async def download_contract_attachment(contract_id:int,cont_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to Upload Contract Documents """

    try:
        statement = select(Contract).where(Contract.id==contract_id,Contract.deletedStatus==False)
        result = cont_session.exec(statement).first()

        if not result is None:
            
            return FileResponse(result.attachment)
        else:
            return JSONResponse(content="Contract with"+str(contract_id)+" Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@cont_router.get('/contracts/{contract_id}/services',tags=["Contracts"])
async def get_contract_services(contract_id:int,cont_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to fetch Contract services """

    try:
        statement = select(Contract).where(Contract.id==contract_id,Contract.deletedStatus==False,Contract.current==True)
        result = cont_session.exec(statement).first()

        if not result is None:
            service=result.services
            return service
        else:
            return JSONResponse(content="Contract with"+str(contract_id)+" Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@cont_router.get('/institution/{institution_id}/services',tags=["Contracts"])
async def institution_services(institution_id:int,cont_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to fetch institution  services """

    try:
        statement = select(Institution).where(Institution.id==institution_id,Institution.deletedStatus==False)
        institution = cont_session.exec(statement).first()

        if not institution is None:
            statementc=select(Contract).where(Contract.institution_id==institution.id,Contract.current==True,
                                              Contract.deletedStatus==False)
            contract=cont_session.exec(statementc).first()
            if  not contract is None:
                return contract.services
        else:
            return JSONResponse(content="Institution with "+str(institution_id)+" Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        
@cont_router.get('/contracts/{contract_id}/assigned_and_unassigned_servces',response_model=List[ServiceCon],tags=["Contracts"])
async def assigned_and_unassigned_contract_services(contract_id:int,cont_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to fetch assigned and unassigned  Contract  services """ 

    try:
        statement = select(Contract).where(Contract.id==contract_id,Contract.deletedStatus==False,Contract.current==True)
        result = cont_session.exec(statement).first()
        serv_list=[]
        if not result is None:
            statements=select(Service).where(Service.is_available==True,Service.deleted_status==False)
            serv=cont_session.exec(statements).all()
            for s in serv:
                service=ServiceCon()
                service.service_id=s.id
                service.service_name=s.name
                check=False
                if not result.services is None:
                    for sc in result.services:
                        if s.id==sc['service_id']:
                            check=True
                            break
                if check:
                    service.assigned=True
                else:
                    service.assigned=False
                serv_list.append(service)
            return serv_list

        else:
            return JSONResponse(content="Contract with "+str(contract_id)+" Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

            
@cont_router.put('/contracts/{contract_id}/update_contract_servces',response_model=Contract,tags=["Contracts"])
async def  update_contract_services(contract_id:int,conts:ContractS,cont_session: Session = Depends(get_session),user=Depends(auth_handler.get_current_user)):
    """ Endpoint to update Contract  services """ 

    try:
        statement = select(Contract).where(Contract.id==contract_id,Contract.deletedStatus==False,Contract.current==True)
        result = cont_session.exec(statement).first()
        serv_list=[]
        if not result is None:
            statements=select(Service).where(Service.is_available==True,Service.deleted_status==False)
            servi=cont_session.exec(statements).all()
            servi=conts.services
            for s in servi:
                    servi_i=s.service_id
                    servi_r=s.service_rate
                    statement1=select(Service).where(Service.id==servi_i)
                    service=cont_session.exec(statement1).first()
                    servi_n=service.name
                    context={
                        "service_id":servi_i,
                        "service_rate":servi_r,
                        "name":servi_n
                    }
                    serv_list.append(context)
            result.services=serv_list    
           
            cont_session.add(result)
            cont_session.commit()
            return result
        else:
            return JSONResponse(content="Contract with "+str(contract_id)+" Not Found",status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(e)
        return JSONResponse(content="Error: "+str(e),status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

        
            
    
       



        

        
            
    
       


