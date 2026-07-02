# Banking Demo — Final

A microservices banking demo: Kong API gateway → async RabbitMQ message bus → Python consumers → RabbitMQ Direct Reply-to RPC. Includes a React 19 + Vite frontend, Helm chart for Kubernetes, and Docker Compose for local development.

## Architecture

```
Browser
  │
  ├─ GET /  ──────────────────────────────── frontend (nginx :80)
  │                                               │
  ├─ /api/* ──────────────────────────────── Kong :8000
  │                                               │
  └─ /ws   ─────────────────────────────────┐    │
                                            │    ▼
                                            │  api-producer :8080
                                            │    │  publishes JSON payload
                                            │    │  reply_to = amq.rabbitmq.reply-to
                                            │    ▼
                                            │  RabbitMQ :5672
                                            │    ├─ auth.requests     → auth-service :8001
                                            │    ├─ account.requests  → account-service :8002
                                            │    ├─ transfer.requests → transfer-service :8003
                                            │    └─ notification.*    → notification-service :8004
                                            │                               │
                                            │                         Redis pub/sub
                                            │                         (WebSocket notify only)
                                            │
                                            └── notification-service :8004 (WebSocket, direct)
```

**Request flow for REST calls:**
1. Browser → nginx → Kong → `api-producer`
2. `api-producer` maps the URL path to a queue name, subscribes to `amq.rabbitmq.reply-to`, then publishes `{action, path, method, payload, headers}` with a `correlation_id` and `reply_to="amq.rabbitmq.reply-to"`
3. Consumer processes the message and publishes `{status, body}` back to `message.reply_to`
4. `api-producer`'s `asyncio.Future` is resolved by the reply callback and the response is returned to the browser — no polling, no Redis in the request path

**WebSocket flow:** Browser → Kong → `notification-service` directly (bypasses the queue bus).

---

## Repository layout

```
final/
├── common/                  # Shared Python library (imported by all services)
│   ├── auth.py              # bcrypt password hashing, JWT session tokens
│   ├── db.py                # SQLAlchemy async engine + session factory
│   ├── models.py            # ORM models: User, Account, Transfer, Notification
│   ├── rabbitmq_utils.py    # path_to_queue(), publish_and_wait(), consumer helpers
│   ├── redis_utils.py       # Async Redis client factory
│   ├── logging_utils.py     # Structured JSON logger + RequestLogMiddleware
│   ├── observability.py     # OpenTelemetry tracing + Prometheus /metrics
│   └── health_server.py     # Lightweight health check HTTP server
│
├── producer/                # api-producer: stateless HTTP → RabbitMQ proxy
│   ├── main.py
│   └── Dockerfile
│
├── services/
│   ├── auth-service/        # register, login  (port 8001)
│   ├── account-service/     # me, balance, lookup, admin/*  (port 8002)
│   ├── transfer-service/    # transfer  (port 8003)
│   └── notification-service/ # GET /notifications, WebSocket /ws  (port 8004)
│
├── frontend/                # React 19 + Vite + Tailwind CSS v4 SPA
│   ├── src/
│   ├── vite.config.js
│   ├── Dockerfile           # multi-stage: node:24 build → nginx:alpine serve
│   └── nginx.conf           # SPA fallback + /api/* and /ws proxy → Kong
│
├── backend/                 # Legacy monolith (reference only, not deployed)
│
├── docker-compose.yml       # Local dev: all services + infra in one command
├── kong-compose.yml         # Kong DB-less declarative config for Compose
│
├── rabbitmq/
│   ├── k8s-rabbitmq-standalone.yaml   # RabbitMQ in its own namespace (k8s)
│   └── values-rabbitmq-ha.yaml        # RabbitMQ HA Helm values (production)
│
├── kong-ha/
│   └── kong-import-job.yaml           # Kong DB-mode config import job (HA)
│
└── helm/                    # Helm chart — single chart, all services
    ├── Chart.yaml
    ├── values.yaml          # Image repos/tags + shared defaults (edit this)
    ├── values-phase8.yaml   # Phase 8 Kong routes + RabbitMQ wiring
    ├── charts/              # Per-service default values
    └── templates/           # All Deployment/Service/Ingress/ConfigMap/Secret templates
```

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite 8, Tailwind CSS 4 |
| API Gateway | Kong 3.9 (DB-less in Compose, DB-mode option in k8s HA) |
| HTTP Entry | FastAPI (api-producer) |
| Message Bus | RabbitMQ 4 (AMQP, Direct Reply-to RPC) |
| Session / Cache / Notify | Redis 8 |
| Consumers | FastAPI + aio-pika (Python async) |
| Database | PostgreSQL 18 |
| Observability | OpenTelemetry (OTLP/gRPC) + Prometheus `/metrics` |
| Container Runtime | Docker / Kubernetes (k3d, minikube, EKS, EC2 k3s) |
| Packaging | Helm |

---

## Local development (Docker Compose)

```bash
# From the final/ directory
docker compose up --build
```

Services started:

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Kong proxy | http://localhost:8000 |
| Kong admin API | http://localhost:8001 |
| RabbitMQ management | http://localhost:15672 (user: `banking` / `bankingpass`) |
| PostgreSQL | localhost:5432 |

> **Note:** The `frontend` container proxies `/api/*` and `/ws` to Kong at `http://kong:8000`. All API traffic flows through Kong even in Compose.

---

## Frontend development (without Docker)

```bash
cd final/frontend
npm install
npm start        # Vite dev server on http://localhost:5173
```

The Vite dev server does **not** proxy to Kong. For full local API access, run `docker compose up` for the backend stack and point `VITE_API_BASE` at Kong, or use the Compose frontend container.

---

## Building Docker images

Build all images from `final/` as the Docker context root (shared `common/` lib is on the build path):

```bash
REGISTRY=ghcr.io/your-org/banking-demo

docker build -f final/producer/Dockerfile                  final/ -t $REGISTRY/api-producer:latest
docker build -f final/services/auth-service/Dockerfile     final/ -t $REGISTRY/auth-service:latest
docker build -f final/services/account-service/Dockerfile  final/ -t $REGISTRY/account-service:latest
docker build -f final/services/transfer-service/Dockerfile final/ -t $REGISTRY/transfer-service:latest
docker build -f final/services/notification-service/Dockerfile final/ -t $REGISTRY/notification-service:latest
docker build -f final/frontend/Dockerfile                  final/frontend/ -t $REGISTRY/frontend:latest

docker push $REGISTRY/api-producer:latest
docker push $REGISTRY/auth-service:latest
docker push $REGISTRY/account-service:latest
docker push $REGISTRY/transfer-service:latest
docker push $REGISTRY/notification-service:latest
docker push $REGISTRY/frontend:latest
```

Then update image repositories in `final/helm/values.yaml` (or pass `--set` at deploy time).

---

## Kubernetes deployment (Helm)

### 1. Prerequisites

- Kubernetes cluster (k3d, minikube, EKS, EC2 k3s)
- `kubectl` configured for the target cluster
- `helm` ≥ 3.12
- Images pushed to a registry accessible from the cluster

### 2. Namespace

```bash
kubectl create namespace banking
kubectl create namespace rabbit
```

### 3. Secrets

Secrets are created manually and **never committed to git**.

```bash
# Postgres + Redis credentials (referenced by all consumers)
kubectl create secret generic banking-db-secret \
  --from-literal=DATABASE_URL='postgresql://banking:<PASSWORD>@postgres:5432/banking' \
  --from-literal=REDIS_URL='redis://redis:6379/0' \
  -n banking

# RabbitMQ connection (referenced by api-producer + all consumers)
kubectl create secret generic rabbitmq-connection-secret \
  --from-literal=RABBITMQ_URL='amqp://banking:<PASSWORD>@rabbitmq.rabbit.svc.cluster.local:5672/' \
  -n banking

# RabbitMQ pod credentials (used by the RabbitMQ StatefulSet itself)
kubectl create secret generic rabbitmq-secret \
  --from-literal=rabbitmq-username=banking \
  --from-literal=rabbitmq-password='<PASSWORD>' \
  -n rabbit
```

> Replace `<PASSWORD>` with a strong random value. Use the same password in all three secrets that reference RabbitMQ.

### 4. Deploy RabbitMQ

RabbitMQ runs in its own namespace with a standalone StatefulSet:

```bash
kubectl apply -f final/rabbitmq/k8s-rabbitmq-standalone.yaml
# Wait for RabbitMQ to be ready before deploying the app
kubectl rollout status statefulset/rabbitmq -n rabbit
```

### 5. Deploy the app

```bash
cd final/helm

helm upgrade --install banking-demo . \
  --namespace banking --create-namespace \
  -f charts/common/values.yaml \
  -f charts/postgres/values.yaml \
  -f charts/redis/values.yaml \
  -f charts/kong/values.yaml \
  -f charts/auth-service/values.yaml \
  -f charts/account-service/values.yaml \
  -f charts/transfer-service/values.yaml \
  -f charts/notification-service/values.yaml \
  -f charts/api-producer/values.yaml \
  -f charts/frontend/values.yaml
```

Override specific values inline without editing files:

```bash
helm upgrade --install banking-demo . \
  ... \
  --set auth-service.image.tag=abc123 \
  --set ingress.className=nginx \
  --set ingress.host=banking.example.com
```

### 6. Verify

```bash
kubectl get pods -n banking
kubectl get pods -n rabbit
kubectl get ingress -n banking
```

All pods should reach `Running` state. RabbitMQ consumers will log `rabbitmq_connected` when they successfully connect.

### Ingress class

The default `ingress.className` in `charts/common/values.yaml` is `traefik` (k3d default).

| Cluster | Value |
|---------|-------|
| k3d / k3s | `traefik` |
| minikube with nginx addon | `nginx` |
| Production (HAProxy) | `haproxy` |

```bash
helm upgrade ... --set ingress.className=nginx
```

---

## Environment variables

All services read configuration from environment variables injected via Kubernetes Secrets or Compose `environment:` blocks.

| Variable | Default | Used by |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql://banking:bankingpass@postgres:5432/banking` | auth, account, transfer, notification |
| `REDIS_URL` | `redis://redis:6379/0` | auth, account, transfer, notification (session / cache / WebSocket notify) |
| `RABBITMQ_URL` | `amqp://banking:bankingpass@rabbitmq:5672/` | api-producer + all consumers |
| `RABBITMQ_RESPONSE_TIMEOUT` | `60` | api-producer — seconds to await RPC reply before 504 |
| `LOG_LEVEL` | `INFO` | all services |
| `LOG_REQUEST_FLOW` | `true` | set `false` to suppress per-request log lines |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | _(unset — tracing disabled)_ | all — e.g. `http://jaeger:4317` |
| `CORS_ORIGINS` | `http://localhost:3000` | all consumers |

---

## RabbitMQ queue routing

`api-producer` maps URL path prefixes to queues via `common/rabbitmq_utils.path_to_queue()`:

| URL prefix | Queue | Consumer |
|------------|-------|---------|
| `/api/auth/` | `auth.requests` | auth-service |
| `/api/account/` | `account.requests` | account-service |
| `/api/transfer/` | `transfer.requests` | transfer-service |
| `/api/notifications/` | `notification.requests` | notification-service |

The WebSocket endpoint `/ws` bypasses the queue entirely — Kong routes it directly to `notification-service:8004`.

---

## Observability

### Structured JSON logging

All services emit newline-delimited JSON logs. Key fields:

```json
{"timestamp":"...","level":"INFO","service":"api-producer","event":"rpc_publish","correlation_id":"...","path":"/api/auth/login"}
```

Useful `kubectl logs` one-liners:

```bash
# Trace an RPC round-trip through the producer
kubectl logs -n banking -l app=api-producer -f \
  | grep -E '"event":"(rpc_publish|rpc_reply_received|producer_error|producer_timeout)"'

# Watch auth-service process logins
kubectl logs -n banking -l app=auth-service -f \
  | grep -E '"event":"(rmq_message_received|login_success|login_failed|consumer_error)"'

# Watch all services for errors
kubectl logs -n banking --all-containers=true -f \
  | grep '"level":"ERROR"'
```

### Prometheus metrics

Every service exposes `GET /metrics` in Prometheus text format. Metrics:

- `http_requests_total{method, endpoint, status}` — request count
- `http_request_duration_seconds{method, endpoint}` — latency histogram

Point a Prometheus scrape config at each service's `/metrics` endpoint, or use a `ServiceMonitor` if you have the Prometheus Operator installed.

### OpenTelemetry tracing

Tracing is **disabled by default**. Enable by setting `OTEL_EXPORTER_OTLP_ENDPOINT`:

```bash
# Helm: add to each service block in values.yaml
auth-service:
  env:
    OTEL_EXPORTER_OTLP_ENDPOINT: "http://jaeger-collector.observability:4317"
```

Or inline at deploy time:

```bash
helm upgrade ... \
  --set 'auth-service.env.OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger-collector.observability:4317' \
  --set 'account-service.env.OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger-collector.observability:4317' \
  # ... repeat for all services
```

The exporter uses OTLP/gRPC. Any OpenTelemetry-compatible backend works (Jaeger, Grafana Tempo, Honeycomb, etc.).

---

## Helm values quick-reference

### Changing image tags (CI/CD)

```bash
# Deploy a specific commit SHA to production
helm upgrade banking-demo final/helm \
  -n banking \
  --reuse-values \
  --set auth-service.image.tag=sha-abc1234 \
  --set account-service.image.tag=sha-abc1234 \
  --set transfer-service.image.tag=sha-abc1234 \
  --set notification-service.image.tag=sha-abc1234 \
  --set api-producer.image.tag=sha-abc1234 \
  --set frontend.image.tag=sha-abc1234
```

### Using an external PostgreSQL (RDS, Cloud SQL, etc.)

```yaml
# In your override values file:
externalPostgres:
  enabled: true
  host: "mydb.us-east-1.rds.amazonaws.com"
  port: "5432"
  db: "banking"
  user: "banking"

# Disable the in-cluster postgres pod:
postgres:
  enabled: false
```

### Resource tuning

Default resource requests/limits per service pod (`values.yaml`):

```yaml
resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "500m"
```

Override per-service as needed:

```bash
--set auth-service.resources.limits.memory=1Gi
```

### Security context

All service pods run with hardened defaults:

```yaml
securityContext:
  pod:
    seccompProfile:
      type: RuntimeDefault
  container:
    allowPrivilegeEscalation: false
    capabilities:
      drop: ["ALL"]
```

---

## Common operations

```bash
# Restart a single service (e.g. after a config change)
kubectl rollout restart deployment/auth-service -n banking

# Scale a consumer horizontally
kubectl scale deployment/transfer-service --replicas=3 -n banking

# Check RabbitMQ queue depths
kubectl exec -n rabbit statefulset/rabbitmq -- rabbitmqctl list_queues name messages consumers

# Open a psql session to the in-cluster Postgres
kubectl exec -it -n banking deploy/postgres -- psql -U banking banking

# Port-forward the RabbitMQ management UI locally
kubectl port-forward -n rabbit statefulset/rabbitmq 15672:15672
# Then open http://localhost:15672

# Uninstall the app (keeps PVCs and secrets)
helm uninstall banking-demo -n banking
```
