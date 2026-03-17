#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=".env.prod"
COMPOSE_FILE="docker-compose.prod.yml"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE in $(pwd)"
  exit 1
fi

if [[ -z "${AWS_REGION:-}" || -z "${AWS_ACCOUNT_ID:-}" ]]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

if [[ -z "${AWS_REGION:-}" || -z "${AWS_ACCOUNT_ID:-}" ]]; then
  echo "AWS_REGION and AWS_ACCOUNT_ID must be set"
  exit 1
fi

ECR_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/easyinventory/api"

echo "Logging into ECR: $ECR_REPO"
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REPO"

echo "Pulling api image"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull api

echo "Restarting api container"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d api

echo "Running database migrations"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T api alembic upgrade head

echo "Pruning dangling images"
docker image prune -f

echo "Deploy complete"
