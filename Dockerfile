FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    AUTOMATOM_AGENT_MODE=auto

WORKDIR /srv/app

COPY requirements-google.txt /srv/requirements-google.txt
RUN pip install --no-cache-dir -r /srv/requirements-google.txt \
    && useradd --create-home --uid 10001 appuser

COPY app/ /srv/app/
RUN chown -R appuser:appuser /srv/app
USER appuser

EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
