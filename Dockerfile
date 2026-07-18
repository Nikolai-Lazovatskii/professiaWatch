FROM python:3.12-slim

ENV TZ=Europe/Bratislava \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY jobwatch ./jobwatch
COPY config.yaml .

VOLUME ["/app/data"]
CMD ["python", "-m", "jobwatch.bot"]
