#!/usr/bin/env bash
set -euo pipefail

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example — edit credentials as needed."
fi

mkdir -p data/demo data/artifacts

echo "Starting Ollama..."
docker compose up -d ollama

echo "Pulling base models via Ollama..."
sleep 2
curl -s http://localhost:11434/api/pull -d '{"name":"qwen2.5:7b"}' || true
curl -s http://localhost:11434/api/pull -d '{"name":"mistral:7b"}' || true
curl -s http://localhost:11434/api/pull -d '{"name":"olmo2:7b"}' || true

echo "Bringing up the full stack..."
docker compose up -d

echo "Done.
Grafana: http://localhost:3000  (user/pass from .env)
Broker:  http://localhost:${BROKER_PORT}
Ollama:  http://localhost:11434
Mode:    ${COUNCIL_MODE}"
