FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY maun.py .
CMD ["uvicorn", "maun:app", "--host", "0.0.0.0", "--port", "8080"]
