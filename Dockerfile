FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY trading/ ./trading/
COPY run_trading_app.py .

EXPOSE 8080

ENV PORT=8080

CMD ["gunicorn", "trading.app.server:app", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "60"]
