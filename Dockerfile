# High-Performance HTTP/WebSocket Proxy
# Python 3.10 slim base for production containerization
FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY config.py .
COPY main.py .
COPY middleware/ ./middleware/
COPY proxy/ ./proxy/

# Expose proxy port
EXPOSE 8000

# Run FastAPI with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
