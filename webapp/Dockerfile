# Standalone Portfolio Mandate Builder
# Build from fast-demo-webapp root:
#   cd frontend && npm run build && cd ..
#   docker build -f agents/qport-agent/webapp/Dockerfile .
FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# Layer 1: FAST framework
COPY agents/fast-framework/ ./agents/fast-framework/
RUN pip install --no-cache-dir -e "agents/fast-framework[all]"

# Layer 2: qport packages (from quant-platform monorepo, vendored as submodule)
COPY agents/qport-agent/vendor/quant-platform/packages/qdata/ ./vendor/qdata/
COPY agents/qport-agent/vendor/quant-platform/packages/qport/ ./vendor/qport/
COPY agents/qport-agent/vendor/quant-platform/packages/qdata-mcp/ ./vendor/qdata-mcp/
COPY agents/qport-agent/vendor/quant-platform/packages/qport-mcp/ ./vendor/qport-mcp/
COPY agents/qport-agent/vendor/quant-platform/packages/qport-agent/ ./vendor/qport-agent/
RUN pip install --no-cache-dir -e vendor/qdata -e vendor/qport
RUN pip install --no-deps --no-cache-dir -e vendor/qdata-mcp -e vendor/qport-mcp
RUN pip install --no-deps --no-cache-dir -e vendor/qport-agent

# Layer 3: Webapp package + dependencies
COPY agents/qport-agent/ ./agents/qport-agent/
RUN pip install --no-cache-dir -e agents/qport-agent

COPY agents/qport-agent/webapp/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/qport-agent/webapp/ ./webapp/

# Layer 4: Pre-built frontend
COPY frontend/dist/ ./frontend/dist/

ENV PYTHONUNBUFFERED=1 PORT=8000
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", \
     "--worker-class", "uvicorn.workers.UvicornWorker", "--timeout", "120", \
     "webapp.app:app"]
