#!/bin/bash

alembic init alembic
alembic stamp head
alembic revision --autogenerate  -m "Add changes"
alembic upgrade head


exec uvicorn  main:app --host 0.0.0.0 --port 8000
