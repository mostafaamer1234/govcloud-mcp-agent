FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY mcp_server ./mcp_server
COPY agents ./agents
RUN pip install --no-cache-dir .

COPY config ./config
COPY corpus ./corpus
COPY scripts ./scripts
COPY run_server.py ./

RUN useradd --create-home --uid 10001 app && mkdir -p /app/logs && chown app /app/logs
USER app

ENV HOST=0.0.0.0 PORT=8443 CERT_DIR=/certs ZERO_EGRESS=1
EXPOSE 8443
CMD ["python", "run_server.py"]
