# Banking Demo — Phase 8 (Final)

Architecture: **Kong → API Producer → RabbitMQ → Consumers (auth/account/transfer/notification) → Redis response**

```
Browser → Kong:8000 → api-producer:8080 → RabbitMQ → auth/account/transfer/notification
                   ↘ /ws → notification-service:8004 (WebSocket, direct)
```

## Folder layout

```
final/
├── common/          # Shared Python lib (db, models, redis, rabbitmq_utils, observability)
├── producer/        # API Producer (FastAPI, HTTP entry point for all /api/* routes)
├── services/
│   ├── auth-service/
│   ├── account-service/
│   ├── transfer-service/
│   └── notification-service/
├── frontend/        # React app (served by nginx)
├── backend/         # Legacy monolith (reference only — not used in Phase 8 k8s deploy)
├── rabbitmq/        # k8s-rabbitmq-standalone.yaml — standalone RabbitMQ for k3d/minikube
├── kong-ha/         # kong-import-job.yaml — Kong DB-mode config import (HA setup only)
└── helm/            # Helm chart (self-contained, builds all k8s manifests)
    ├── Chart.yaml
    ├── values.yaml
    ├── values-phase8.yaml  ← Phase 8 overrides (apply last)
    ├── charts/             ← per-service defaults
    └── templates/          ← all Deployment/Service/Ingress/ConfigMap templates
```

---

## Build Docker images

Build from `final/` as the Docker context root:

```bash
# From repo root
docker build -f final/producer/Dockerfile        final/ -t <registry>/api-producer:latest
docker build -f final/services/auth-service/Dockerfile     final/ -t <registry>/auth-service:latest
docker build -f final/services/account-service/Dockerfile  final/ -t <registry>/account-service:latest
docker build -f final/services/transfer-service/Dockerfile final/ -t <registry>/transfer-service:latest
docker build -f final/services/notification-service/Dockerfile final/ -t <registry>/notification-service:latest
docker build -f final/frontend/Dockerfile         final/frontend/ -t <registry>/frontend:latest

docker push <registry>/api-producer:latest
# ... push all images
```

Update image repositories in `final/helm/charts/<service>/values.yaml` (or override with `--set`).

---

## Deploy on Kubernetes (Helm)

### 1. Namespace + Secrets

```bash
# Namespace (Helm creates it, or manually):
kubectl create namespace banking

# DB secret (Helm manages this via secret.yaml, but you can override password):
# Edit final/helm/charts/common/values.yaml → secret.postgresPassword

# RabbitMQ connection secret — create manually, NEVER commit to git:
kubectl create secret generic rabbitmq-connection-secret \
  --from-literal=RABBITMQ_URL='amqp://banking:<PASSWORD>@rabbitmq.rabbit.svc.cluster.local:5672/' \
  -n banking
```

### 2. Deploy RabbitMQ (standalone, separate namespace)

```bash
kubectl create namespace rabbit
kubectl create secret generic rabbitmq-secret \
  --from-literal=rabbitmq-username=banking \
  --from-literal=rabbitmq-password='<PASSWORD>' \
  -n rabbit

kubectl apply -f final/rabbitmq/k8s-rabbitmq-standalone.yaml
```

### 3. Deploy the app with Helm

```bash
cd final/helm

helm upgrade --install banking-demo . \
  -n banking --create-namespace \
  -f charts/common/values.yaml \
  -f charts/postgres/values.yaml \
  -f charts/redis/values.yaml \
  -f charts/kong/values.yaml \
  -f charts/auth-service/values.yaml \
  -f charts/account-service/values.yaml \
  -f charts/transfer-service/values.yaml \
  -f charts/notification-service/values.yaml \
  -f charts/api-producer/values.yaml \
  -f charts/frontend/values.yaml \
  -f values-phase8.yaml
```

### 4. Verify

```bash
kubectl get pods -n banking
kubectl get pods -n rabbit
```

### Ingress

Default `ingress.className` is `nginx`. For k3d with Traefik:

```bash
# Override inline:
helm upgrade ... --set ingress.className=traefik
```

For HAProxy (production cluster):
```bash
helm upgrade ... --set ingress.className=haproxy
```

---

## Environment variables (key overrides)

| Variable | Default | Where |
|---|---|---|
| `DATABASE_URL` | from `banking-db-secret` | all consumers, backend |
| `REDIS_URL` | from `banking-db-secret` | all services |
| `RABBITMQ_URL` | from `rabbitmq-connection-secret` | producer + all consumers |
| `LOG_LEVEL` | `INFO` | all services |
| `LOG_REQUEST_FLOW` | `true` | reduce noise: set `false` |
| `RABBITMQ_RESPONSE_TIMEOUT` | `60` | producer |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | _(unset)_ | all — enable tracing |

---

## Queues

| Queue | Consumer | Handles |
|---|---|---|
| `auth.requests` | auth-service | register, login |
| `account.requests` | account-service | me, balance, lookup, admin/* |
| `transfer.requests` | transfer-service | transfer |
| `notification.requests` | notification-service | GET /notifications |

WebSocket `/ws` bypasses queues → direct to notification-service:8004.

---

## Logging — trace a request end-to-end

```bash
# Watch producer publish + wait
kubectl logs -n banking -l app=api-producer -f | grep -E '"event":"(rmq_publish|redis_response|producer_error)"'

# Watch a consumer process
kubectl logs -n banking -l app=auth-service -f | grep -E '"event":"(rmq_message_received|login_success|login_failed|consumer_error)"'
```
