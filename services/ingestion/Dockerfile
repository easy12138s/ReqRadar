FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY reqradar/ reqradar/
COPY services/ingestion/ services/ingestion/

RUN pip install --no-cache-dir --break-system-packages --timeout 300 -r services/ingestion/requirements.txt

CMD ["uvicorn", "services.ingestion.app:app", "--host", "0.0.0.0", "--port", "8007"]
