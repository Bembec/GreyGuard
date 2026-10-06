FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
ENV PYTHONPATH=/app
COPY backend/requirements.txt backend/requirements-dev.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt -r /tmp/requirements-dev.txt
COPY backend /app/backend
COPY scripts /app/scripts
CMD ["python", "scripts/verify_postgresql_parity.py"]



