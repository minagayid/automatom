FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    AUTOMATOM_AGENT_MODE=offline

WORKDIR /srv/app
COPY requirements-google.txt /srv/requirements-google.txt
RUN pip install --no-cache-dir -r /srv/requirements-google.txt
COPY app/ /srv/app/

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
