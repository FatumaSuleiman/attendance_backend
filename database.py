import os
from dotenv import load_dotenv
from sqlmodel import Field, Session, SQLModel, create_engine, select
from models import User

load_dotenv('.env')

DATABASE_URL = os.environ['DATABASE_URL']

engine = create_engine(DATABASE_URL, echo=True)


def create_db_and_tables():
    print("Creating tables...")
    SQLModel.metadata.create_all(engine)
    print("Tables created")


def get_session():
    """Create database session per request, close it after returning response"""
    with Session(engine) as session:
        yield session


def find_user(name):
    with Session(engine) as session:
        statement = select(User).where(User.userName == name)
        return session.exec(statement).first()


def verify_password(login, password):
    check = False
    if login == password:
        check = True
    return check
