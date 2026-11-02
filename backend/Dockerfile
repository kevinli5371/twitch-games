FROM python:3.14.3-slim@sha256:5e59aae31ff0e87511226be8e2b94d78c58f05216efda3b07dbbed938ec8583b
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY pyproject.toml requirements-dev.lock ./
COPY src ./src
RUN python -m pip install --no-cache-dir . -c requirements-dev.lock \
    && useradd --uid 10001 --create-home app
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts/check_supabase.py ./scripts/check_supabase.py
USER app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health/live',timeout=2)"
CMD ["python", "-m", "uvicorn", "twitch_games.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
