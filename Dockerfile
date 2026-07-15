FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
# Longer timeout helps flaky networks when building on Windows Docker Desktop
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

COPY app ./app
COPY docs ./docs
COPY README.md .

EXPOSE 52999
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "52999"]
