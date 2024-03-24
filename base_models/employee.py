from sqlmodel import SQLModel
class EmployeBase(SQLModel):
    firstName:str
    lastName:str
    gender:str
    email:str
    phone:str
    title:str
    
   
