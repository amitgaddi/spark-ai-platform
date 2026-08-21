FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and Chromium dependencies together
RUN python -m playwright install --with-deps chromium && \
    rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["sleep", "infinity"]
