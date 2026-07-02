FROM python:3.13-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY common /app/common
COPY services/auth-service /app

RUN pip install --no-cache-dir -r common/requirements.txt \
 && chmod +x entrypoint.sh

EXPOSE 8001
CMD ["./entrypoint.sh"]
