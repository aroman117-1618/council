FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
# single worker so Prometheus sees a consistent registry
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8080", "app:app"]
