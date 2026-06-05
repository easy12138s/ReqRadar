FROM python:3.12-slim

WORKDIR /app

COPY reqradar/kernel/ reqradar/kernel/
COPY reqradar/cognitive_rt/ reqradar/cognitive_rt/
COPY reqradar/infrastructure/ reqradar/infrastructure/

RUN pip install --no-cache-dir fastapi uvicorn httpx pyjwt

EXPOSE 8002

CMD ["uvicorn", "reqradar.cognitive_rt.runtime.session_api:app", "--host", "0.0.0.0", "--port", "8002"]
