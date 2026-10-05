FROM python:3.12.15-slim-bookworm@sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /opt/shopsphere

# Dependencies stay cached when only application source changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 shopsphere \
    && useradd --uid 10001 --gid shopsphere --no-create-home \
       --shell /usr/sbin/nologin shopsphere

COPY app/ ./app/
COPY payment/ ./payment/
COPY postgres/init.sql ./postgres/init.sql

USER 10001:10001
EXPOSE 8000 8001
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
