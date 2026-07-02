#!/bin/sh
set -e
echo "[entrypoint] Running seed..."
python3 seed.py
echo "[entrypoint] Starting auth-service..."
exec uvicorn main:app --host 0.0.0.0 --port 8001 --proxy-headers --forwarded-allow-ips='*'
