from datetime import datetime
from sqlmodel import select, Session, col
from database import engine
from models import EmployeeEntry


def employee_daily_entries(employee_entry: EmployeeEntry) -> int:
    with Session(engine) as ent_session:
        start_date = datetime.combine(employee_entry.signedAt.date(), datetime.min.time())
        end_date = datetime.combine(employee_entry.signedAt.date(), datetime.max.time())
        statement = select(EmployeeEntry).where(EmployeeEntry.deletedStatus == False,
                                                EmployeeEntry.employee_id == employee_entry.employee_id,
                                                col(EmployeeEntry.signedAt).between(start_date,
                                                                                    end_date))
        result = ent_session.exec(statement).all()
        return len(result)
