from typing import List, Dict, Union

from fastapi import APIRouter, Security, security, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import select, Session
from starlette.responses import JSONResponse
from models import Institution, Session, SupportingDocument, DocumentBase
from fastapi import FastAPI, status, UploadFile, Form, File
from database import engine
from auth import AuthHandler
import shutil
import os
from fastapi.responses import FileResponse
from datetime import datetime, date

document_router = APIRouter()
# document_session=Session(bind=engine)

auth_handler = AuthHandler()


def get_session():
    with Session(engine) as session:
        yield session


@document_router.post(
    "/documents/save", response_model=SupportingDocument, tags=["Documents"]
)
async def save_supporting_document(
    doc: DocumentBase = Depends(),
    file: UploadFile = File(...),
    document_session: Session = Depends(get_session),
    user=Depends(auth_handler.get_current_user),
):
    """Endpoint to Create Supporting Document"""
    try:
        dt = datetime.combine(doc.expirationDate, datetime.min.time())
        result = SupportingDocument(
            name=doc.name,
            description=doc.description,
            expirationDate=dt,
            is_active=doc.is_active,
        )
        if os.path.exists(os.environ["FILE_SOURCE"] + "/" + "SupportingDocuments"):
            file_path = (
                os.environ["FILE_SOURCE"]
                + "/"
                + "SupportingDocuments/"
                + str(result.uuid)
                + "_"
                + file.filename
            )
            with open(f"{file_path}", "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        else:
            os.mkdir(os.environ["FILE_SOURCE"] + "/" + "SupportingDocuments")
            file_path = (
                os.environ["FILE_SOURCE"]
                + "/"
                + "SupportingDocuments/"
                + str(result.uuid)
                + "_"
                + file.filename
            )
            with open(f"{file_path}", "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        result.path = file_path
        document_session.add(result)
        document_session.commit()
        return result
    except Exception as e:
        print(e)
        return JSONResponse(
            content="Error: " + str(e),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@document_router.get(
    "/documents/{document_id}/", response_model=SupportingDocument, tags=["Documents"]
)
async def fetch_document_detail(
    document_id: int,
    document_session: Session = Depends(get_session),
    user=Depends(auth_handler.get_current_user),
):
    """Endpoint to Return Document Detail"""

    try:
        statement = select(SupportingDocument).where(
            SupportingDocument.id == document_id,
            SupportingDocument.deletedStatus == False,
        )
        result = document_session.exec(statement).first()
        if result is not None:
            return result
        else:
            return JSONResponse(
                content="SupportingDocument with " + document_id + " Not Found",
                status_code=status.HTTP_404_NOT_FOUND,
            )

    except Exception as e:
        print(e)
        return JSONResponse(
            content="Error: " + str(e),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@document_router.delete(
    "/documents/{document_id}/delete/",
    response_model=SupportingDocument,
    tags=["Documents"],
)
async def delete_document(
    document_id: int,
    document_session: Session = Depends(get_session),
    user=Depends(auth_handler.get_current_user),
):
    """Endpoint to delete a Document"""

    try:
        statement = select(SupportingDocument).where(
            SupportingDocument.id == document_id,
            SupportingDocument.deletedStatus == False,
        )
        result = document_session.exec(statement).first()

        if not result is None:
            result.deletedStatus = True
            document_session.add(result)
            document_session.commit()

            return result
        else:
            return JSONResponse(
                content="SupportingDocument with " + document_id + " Not Found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
    except Exception as e:
        print(e)
        return JSONResponse(
            content="Error: " + str(e),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@document_router.get("/documents/{document_id}/download/document/", tags=["Documents"])
async def download_supporting_document(
    document_id: int,
    document_session: Session = Depends(get_session),
    user=Depends(auth_handler.get_current_user),
):
    """Endpoint to Download Specific Supporting Document"""

    try:
        statement = select(SupportingDocument).where(
            SupportingDocument.id == document_id,
            SupportingDocument.deletedStatus == False,
        )
        result = document_session.exec(statement).first()

        if not result is None:

            return FileResponse(result.path)
        else:
            return JSONResponse(
                content="SupportingDocument with " + document_id + " Not Found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
    except Exception as e:
        print(e)
        return JSONResponse(
            content="Error: " + str(e),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@document_router.get("/documents", tags=["Documents"])
async def fetch_all_documents(
    document_session: Session = Depends(get_session),
    user=Depends(auth_handler.get_current_user),
):
    """Endpoint to Return Document Detail"""

    try:
        statement = select(SupportingDocument).where(
            SupportingDocument.deletedStatus == False
        )
        result = document_session.exec(statement).all()
        if len(result) > 0:
            return result
        else:
            return JSONResponse(
                content="No documents found.", status_code=status.HTTP_204_NO_CONTENT
            )

    except Exception as e:
        print(e)
        return JSONResponse(
            content="Error: " + str(e),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@document_router.put(
    "/documents/{document_id}/chamge/status/",
    response_model=SupportingDocument,
    tags=["Documents"],
)
async def change_document_status(
    document_id: int,
    document_session: Session = Depends(get_session),
    user=Depends(auth_handler.get_current_user),
):
    """Endpoint to change a Document Status"""
    try:
        statement = select(SupportingDocument).where(
            SupportingDocument.id == document_id,
            SupportingDocument.deletedStatus == False,
        )
        result = document_session.exec(statement).first()

        if not result is None:
            if result.is_active:
                result.is_active = False
            else:
                result.is_active = True
            document_session.add(result)
            document_session.commit()

            return result
        else:
            return JSONResponse(
                content="SupportingDocument with " + document_id + " Not Found",
                status_code=status.HTTP_404_NOT_FOUND,
            )
    except Exception as e:
        print(e)
        return JSONResponse(
            content="Error: " + str(e),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
