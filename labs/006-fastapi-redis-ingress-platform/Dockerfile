FROM python:3.12-slim

WORKDIR /app

RUN groupadd --system appgroup && \
    useradd --system --gid appgroup appuser

RUN pip install --no-cache-dir \
    fastapi==0.115.12 \
    uvicorn==0.34.2

COPY --chown=appuser:appgroup app/ ./app/

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
