FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NIC_CHAT_HOST=0.0.0.0 \
    NIC_CHAT_PORT=8765 \
    NIC_ACTIVITY_JOURNAL_DB=/data/nic_activity_journal.sqlite3

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY agents ./agents
COPY data/live ./data/live

RUN useradd --system --uid 10001 --create-home nic \
    && mkdir -p /data \
    && chown -R nic:nic /app /data
USER nic

EXPOSE 8765
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/healthz', timeout=3)"
CMD ["python", "-m", "src.nic_assistant_chat"]
