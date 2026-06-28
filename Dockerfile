FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# только пакет бота (внутри лежит и data/shalun_corpus.json)
COPY bot ./bot

CMD ["python", "-m", "bot"]
