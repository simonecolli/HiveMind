FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Dependencies first, from the committed lockfile: they change far less often
# than the source, so editing a node does not reinstall LangGraph.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

COPY main.py ./
COPY src ./src

ENV PATH="/app/.venv/bin:$PATH" \
    # Binding to loopback inside a container would leave it unreachable from
    # anywhere, including the frontend container next door.
    HIVEMIND_HOST=0.0.0.0 \
    HIVEMIND_DATA_DIR=/data

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
