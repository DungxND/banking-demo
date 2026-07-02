# Pod & Service Detection ΓÇö Why Services Don't Appear (and How to Fix It)

> Condensed from: https://www.ibm.com/docs/en/instana-observability
> Condensed for: k3s host-agent on EC2, banking-demo Phase 1 (`banking` namespace)
>
> **If you are seeing this after reviewing the agent log and pods are completely missing from
> Infrastructure ΓåÆ Kubernetes, start with [`10-host-agent-k8s-detection-fix.md`](./10-host-agent-k8s-detection-fix.md)
> which contains the root-cause diagnosis from the actual agent log.**

---

## What "Services" Means in Instana

Instana shows **two different things** that are both called "services":

| Instana View | What populates it | How |
|---|---|---|
| **Infrastructure ΓåÆ Kubernetes ΓåÆ Pods** | Containerd sensor auto-discovery | Immediately on agent start |
| **Applications ΓåÆ Services** | OTLP/trace data from the pods | Only after first trace arrives |

> **The core problem**: Infrastructure (pods, containerd entities) is detected automatically. Services in the Application Perspective appear **only after at least one distributed trace flows through the OTLP pipeline** from a pod to the Instana agent.

---

## Why Pods Are Visible but Services Show 0 Calls

The agent log from the current deployment confirms:

```
Activated Sensor for PID 105171   ΓåÉ generic Process sensor (Python pod)
Activated Sensor for PID 78468    ΓåÉ generic Process sensor (Python pod)
Activated Sensor for PID 78937    ΓåÉ generic Process sensor (Python pod)
Activated Sensor for PID 77374    ΓåÉ generic Process sensor (Python pod)
```

These PIDs are the FastAPI services (auth/account/transfer/notification). The **Process sensor** detects them as processes. They will appear in:
- **Infrastructure** ΓåÆ as processes on the EC2 host Γ£à
- **Kubernetes** ΓåÆ as pods (containerd entities) Γ£à
- **Applications ΓåÆ Services** ΓåÆ Γ¥î only if OTLP traces are flowing

If OTLP traces are not arriving at the agent (port 4317), services stay invisible at the application level.

---

## Checklist: Why OTLP Traces May Not Flow

### 1. Traefik tracing not active ΓåÆ no entry-point spans

The agent log shows:
```
Instana tracing is not enabled   ΓåÉ from Traefik sensor
FrameworkEvent ERROR: Service factory returned null (com.instana.agent.traefik.sensor.Traefik)
```

**Cause**: The `HelmChartConfig` was not applied, or Traefik was not restarted after it was applied.

**Fix**:
```bash
# Apply the HelmChartConfig (if not done yet)
kubectl apply -f phase1-docker-to-k8s/traefik-instana.yaml

# Restart Traefik to pick up the new config
kubectl -n kube-system rollout restart deployment/traefik
kubectl -n kube-system rollout status deployment/traefik

# Verify Traefik now has OTEL_EXPORTER_OTLP_ENDPOINT set
kubectl -n kube-system get pod -l app.kubernetes.io/name=traefik \
  -o jsonpath='{.items[0].spec.containers[0].env}' | python3 -m json.tool \
  | grep -A2 OTEL_EXPORTER
```

> The `FrameworkEvent ERROR: Service factory returned null` is **transient** ΓÇö it resolves automatically once Traefik is restarted with OTLP tracing configured. See [`05-traefik-sensor.md`](./05-traefik-sensor.md) for details.

---

### 2. Python services not sending OTLP spans

Each FastAPI service sets the following env vars (added to all 5 Deployment templates in `final/helm/templates/`):
```yaml
- name: NODE_IP
  valueFrom:
    fieldRef:
      fieldPath: status.hostIP
- name: OTEL_EXPORTER_OTLP_ENDPOINT
  value: "http://$(NODE_IP):4317"
- name: OTEL_SERVICE_NAME
  value: <service-name>           # unique per template
- name: OTEL_RESOURCE_ATTRIBUTES
  value: "service.namespace=banking-demo"
```

`$(NODE_IP)` must expand to the EC2 node's IP **as seen from the pod**. Without `NODE_IP` defined
via `fieldRef`, the `$(NODE_IP)` substitution produces a literal string and the OTLP exporter fails to connect.

**Verify the endpoint resolved correctly**:
```bash
# Pick any running pod
kubectl -n banking exec deploy/auth-service -- env | grep -E 'NODE_IP|OTEL'
# Expected:
# NODE_IP=10.0.x.x
# OTEL_EXPORTER_OTLP_ENDPOINT=http://10.0.x.x:4317
# OTEL_SERVICE_NAME=auth-service
# OTEL_RESOURCE_ATTRIBUTES=service.namespace=banking-demo
```

**Verify the agent is listening on 4317**:
```bash
# On the EC2 host
sudo ss -tlnp | grep 4317
# Expected: LISTEN 0.0.0.0:4317
```

**Verify traces are arriving at the agent**:
```bash
sudo grep -i "otlp\|opentelemetry\|span" /opt/instana/agent/log/agent.log | tail -20
```

---

### 3. OTel plugin not explicitly enabled

Ensure the Instana agent has OTLP ingestion enabled in [`instana/configuration.yaml`](../configuration.yaml):

```yaml
com.instana.plugin.opentelemetry:
  enabled: true
```

This is already set. If it was missing, spans would be silently dropped.

---

### 4. No traffic hitting the services

Even if OTLP is wired correctly, services appear in Instana **only after a request creates a trace**. Send a test request:

```bash
# Get the EC2 public IP
curl -s http://<EC2-IP>/api/auth/health
curl -s http://<EC2-IP>/api/account/health
```

Within 30ΓÇô60 s, the services should appear under **Applications ΓåÆ Services** in the Instana UI.

---

## What Each Service Should Look Like in Instana

After traces flow, the Application Perspective shows:

| Service name | Source | Instana entity type |
|---|---|---|
| `auth-service` | `OTEL_SERVICE_NAME=auth-service` | Application Service |
| `account-service` | `OTEL_SERVICE_NAME=account-service` | Application Service |
| `transfer-service` | `OTEL_SERVICE_NAME=transfer-service` | Application Service |
| `notification-service` | `OTEL_SERVICE_NAME=notification-service` | Application Service |
| `traefik` | Traefik sensor + OTLP | Infrastructure + Application |
| `kong` | Kong Prometheus sensor | Infrastructure metrics only |
| `postgres` | PostgreSQL JDBC sensor | Infrastructure metrics only |
| `redis` | Redis sensor | Infrastructure metrics only |
| `frontend` (Nginx) | Nginx process sensor | Infrastructure only ΓÇö no OTLP |

> **Note**: `frontend` (plain Nginx) and `kong` will **never** appear as Application Services because they don't emit OTLP traces. They appear in **Infrastructure** only. Services in "Applications ΓåÆ Services" require trace data.

---

## End-to-End Trace Flow (Banking Demo)

```
Browser request
  ΓööΓöÇ Traefik (OTLP span ΓåÆ agent :4317, W3C traceparent propagated)
       Γö£ΓöÇ path /  ΓåÆ frontend (Nginx ΓÇö no tracing, infra only)
       ΓööΓöÇ path /api/* ΓåÆ Kong (proxy, no native OTLP) ΓåÆ auth/account/transfer-service
                              Γö£ΓöÇ FastAPI span (OTLP ΓåÆ agent :4317)
                              Γö£ΓöÇ SQLAlchemy span (PostgreSQL query)
                              ΓööΓöÇ Redis span (cache lookup)
```

When fully operational, a single browser request produces a **trace waterfall** in Instana that shows all hops.

---

## Application Perspective Setup (Phase 1)

The agent detects services automatically from OTLP `service.name` attributes. To group them into a single Application Perspective in the Instana UI:

1. Go to **Instana UI ΓåÆ Applications ΓåÆ + New Application Perspective**
2. Set a filter: `kubernetes.namespace.name = banking`  
   ΓÇö or ΓÇö  
   `service.namespace = banking-demo` (from `OTEL_RESOURCE_ATTRIBUTES`)
3. Name it `banking-demo`
4. All traces from `banking` namespace pods are grouped under this AP

> The AP is mandatory to see services together in one dashboard. Without it, services appear in "All Services" but are not grouped.

---

## Full Verification Sequence

Run these steps in order after initial deployment:

```bash
# Step 1 ΓÇö verify k8s sensor sees pods
kubectl -n banking get pods
# All Running

# Step 2 ΓÇö confirm OTLP endpoint resolves in pods
kubectl -n banking exec deploy/auth-service -- env | grep OTEL

# Step 3 ΓÇö restart Traefik (idempotent ΓÇö safe to repeat)
kubectl apply -f phase1-docker-to-k8s/traefik-instana.yaml
kubectl -n kube-system rollout restart deployment/traefik
kubectl -n kube-system rollout status deployment/traefik

# Step 4 ΓÇö send traffic to generate traces
for i in $(seq 1 10); do
  curl -s http://<EC2-IP>/api/auth/health > /dev/null
  curl -s http://<EC2-IP>/api/account/health > /dev/null
done

# Step 5 ΓÇö watch agent log for OTLP activity
sudo grep -i "span\|otlp\|auth-service\|account-service" \
  /opt/instana/agent/log/agent.log | tail -30

# Step 6 ΓÇö check Instana UI (allow 30-60s for data to propagate)
# Applications ΓåÆ Services ΓåÆ auth-service, account-service, transfer-service, notification-service
```

---

## Troubleshooting Quick Reference

| Symptom | Likely cause | Fix |
|---|---|---|
| **Zero pods in Infrastructure → Kubernetes** | `enabled: false` in k8s plugin config, or kubeconfig not readable | See [`10-host-agent-k8s-detection-fix.md`](./10-host-agent-k8s-detection-fix.md) |
| Services show 0 calls | No OTLP traces received | Send traffic; check OTEL endpoint in pods |
| `Instana tracing is not enabled` in agent log | Traefik HelmChartConfig not applied / pod not restarted | `kubectl rollout restart deployment/traefik -n kube-system` |
| `FrameworkEvent ERROR: Service factory returned null` | Traefik sensor init race with tracing-disabled Traefik | Transient; resolves after Traefik restart |
| `NODE_IP` not resolving in pod env | `fieldRef.fieldPath: status.hostIP` missing from Deployment | All 5 Python service templates now include the `NODE_IP` fieldRef env var |
| `python_sensor_not_installed` in Instana UI | `OTEL_EXPORTER_OTLP_ENDPOINT` not set → `observability.py:init_tracing()` skips silently | Fixed: `NODE_IP` + `OTEL_*` env vars added to all 5 Deployment templates |
| Agent not listening on 4317 | OTel plugin disabled | Add `com.instana.plugin.opentelemetry: enabled: true` |
| Pods visible in Infrastructure but not Applications | OTLP not flowing (no traffic, wrong endpoint) | Follow "Full Verification Sequence" above |
| Frontend not in Applications/Services | Nginx has no OTLP — expected | Normal: Nginx appears in Infrastructure only |
| `nginx_status_not_found` in Instana UI | `stub_status` location missing from `nginx.conf` | Fixed: `/nginx_status` location added to `final/frontend/nginx.conf` |
| `postgresql_connection_failed` with `user: postgres` | Agent auto-discovered Postgres process; defaulted to `postgres` user ignoring `configuration.yaml` | Pod is headless ClusterIP — agent cannot reach it. Error is cosmetic. `configuration.yaml` has correct `user: banking` for when a NodePort is added. |
| Kong not in Applications/Services | Kong has no OTLP — expected | Normal: Kong appears via Kong Prometheus sensor |
| Redis `SSL is disabled... Read timed out` | Transient SSL check timeout at sensor init | **Benign** — sensor retries; check sensor is connected with `grep -i redis agent.log` |
| Discovery timeout warnings in agent log | Normal on first boot — many sensors load simultaneously | **Benign** — sensors still activate; warnings go away after warm-up |