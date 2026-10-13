FROM python:3.12.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.10.11 /uv /bin/uv
COPY . .
RUN uv sync --frozen --no-dev
ENTRYPOINT ["uv", "run", "--frozen", "python", "-m", "aviscope.runner"]
