FROM python:3.12-slim

WORKDIR /app

COPY reqradar/kernel/ reqradar/kernel/
COPY reqradar/output_svc/ reqradar/output_svc/
COPY services/output/ services/output/

RUN pip install --no-cache-dir --break-system-packages -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com fastapi uvicorn jinja2

EXPOSE 8004

CMD ["uvicorn", "services.output.app:app", "--host", "0.0.0.0", "--port", "8004"]
