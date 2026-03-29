# FastAPI + RAG；知识库在镜像内 /app/macau_tower_demo_kb_v1.md（与 rag.py 解析路径一致）
FROM python:3.12-slim

WORKDIR /app

COPY macau_tower_demo_kb_v1.md /app/macau_tower_demo_kb_v1.md
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt

COPY server/ /app/server/

WORKDIR /app/server

EXPOSE 8000
ENV PYTHONUNBUFFERED=1

# 平台若注入 PORT，可在启动命令覆盖：uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
