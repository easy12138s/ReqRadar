FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY reqradar/ reqradar/
COPY services/ingestion/ services/ingestion/

RUN pip install --no-cache-dir --timeout 300 \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com \
    -r services/ingestion/requirements.txt

# 构建时预下载嵌入模型（从 HF 镜像，不依赖 S3）
# ReqRadarEmbeddingFunction 会将模型缓存到 REQRADAR_EMBEDDING__MODEL_CACHE 目录
# 运行时如果模型已缓存，不需要网络连接
# 环境变量遵循 C-03 规范（REQRADAR_ 前缀 + __ 分隔），同时兼容旧变量名
ENV REQRADAR_EMBEDDING__HF_ENDPOINT=https://hf-mirror.com
ENV REQRADAR_EMBEDDING__MODEL_CACHE=/app/model_cache
RUN python -c "from reqradar.kernel.embedding import ReqRadarEmbeddingFunction; ef=ReqRadarEmbeddingFunction(); ef(['test']); print('Embedding model pre-downloaded successfully')" || echo "WARNING: Model pre-download failed, will download at runtime"

CMD ["uvicorn", "services.ingestion.app:app", "--host", "0.0.0.0", "--port", "8007"]
