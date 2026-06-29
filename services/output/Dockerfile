FROM python:3.12-slim

WORKDIR /app

COPY reqradar/ reqradar/
COPY services/output/ services/output/

RUN pip install --no-cache-dir --break-system-packages fastapi uvicorn httpx jinja2 pydantic pyyaml sqlalchemy aiosqlite

EXPOSE 8004

CMD ["uvicorn", "services.output.app:app", "--host", "0.0.0.0", "--port", "8004"]
