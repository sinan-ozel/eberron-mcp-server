FROM python:3.12-slim

WORKDIR /workspace

COPY pyproject.toml /workspace/pyproject.toml
COPY server/ /workspace/server/

RUN pip install --no-cache-dir -e ".[dev]"

COPY lint/lint.sh /workspace/lint.sh
RUN chmod +x /workspace/lint.sh

CMD ["/workspace/lint.sh"]
