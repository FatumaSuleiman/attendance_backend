# 
FROM python:3.9

# 
WORKDIR /app

# 
COPY requirements.txt ./

# 
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# FOR ALEMBIC MIGRATIONS
COPY alembic.ini ./

# 
COPY . .

# 
RUN chmod +x ./start.sh
#CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
CMD ./start.sh
