# k8s Pod & Service Detection ΓÇö Host-Agent on EC2 (Root Cause Fix)

> Condensed from:
> - https://www.ibm.com/docs/en/instana-observability/current?topic=kubernetes-checking-agent-prerequisites
> - https://www.ibm.com/docs/en/instana-observability/current?topic=kubernetes-administering-agent
> - https://www.ibm.com/docs/en/instana-observability/current?topic=cha-configuring-host-agents-by-using-agent-configuration-file
>
> Condensed for: k3s single-node on EC2, banking-demo Phase 1, host-agent (systemd) mode.

---

## Problem Summary (from agent log 2026-07-01)

The agent log shows **14 containers discovered** by the Containerd sensor but the
Kubernetes sensor does not confirm pod/service/namespace discovery. Four distinct issues
were found:

| # | Log evidence | Root cause |
|---|---|---|
| 1 | `Instana tracing is not enabled` (Traefik, twice) + `FrameworkEvent ERROR: Service factory returned null` | Traefik HelmChartConfig not applied / Traefik not restarted ΓÇö no OTLP entry spans, so Application Services never populate |
| 2 | `Discovery for com.instana.plugin.ebpf took too long (11854 ms)` `Discovery time (64254 ms)` | Discovery timeouts; k8s sensor races with eBPF/GCP/action plugins at startup |
| 3 | No `"Kubernetes sensor activated"` or `"Connected to Kubernetes API"` log line | The k8s plugin may not be reading the kubeconfig ΓÇö confirm `enabled: true` and kubeconfig permissions |
| 4 | Services in **Applications ΓåÆ Services** show 0 calls | Follows from issue 1: without Traefik OTLP spans there are no entry traces to build application services |

---

## Fix 1 ΓÇö Verify `enabled: true` in configuration.yaml (most common cause)

The host-agent on k3s **must** have:

```yaml
com.instana.plugin.kubernetes:
  enabled: true
  kubeconfig: /etc/rancher/k3s/k3s.yaml
```

**Why**: `enabled: true` is what switches on the k8s sensor in host-agent mode.
With `enabled: false` (or the key absent), the sensor is registered but immediately
deactivates. The Containerd sensor still discovers raw container IDs, but they are
never correlated to Kubernetes pods/deployments/services/namespaces.

> **Helm/Operator** installs are the opposite: they use `enabled: false` (the
> k8sensor Deployment handles k8s monitoring). If you copied config from a Helm
> example, you may have `false` when you need `true`.

Verify the live config on the EC2 host:

```bash
sudo grep -A3 "plugin.kubernetes" \
  /opt/instana/agent/etc/instana/configuration.yaml
# Expected:
# com.instana.plugin.kubernetes:
#   enabled: true
#   kubeconfig: /etc/rancher/k3s/k3s.yaml
```

After changing the file, restart the agent (the k8s plugin requires a restart to
reinitialise its connection):

```bash
sudo systemctl restart instana-agent
sudo journalctl -u instana-agent -f --no-pager | grep -i "kubernetes\|k3s\|Activated\|ERROR"
```

Expected log within ~60 s:

```
INFO  | Instana agent Discovery started.
INFO  | ... | Installed instana-kubernetes-...
INFO  | Kubernetes sensor activated. Connected to ...
```

---

## Fix 2 ΓÇö Kubeconfig permissions

The Instana agent process needs **read access** to the k3s kubeconfig:

```bash
sudo chmod 644 /etc/rancher/k3s/k3s.yaml
# Verify
ls -la /etc/rancher/k3s/k3s.yaml
# Expected: -rw-r--r-- ...

# Verify the agent can read it (agent runs as root, so this is a sanity check)
sudo -u root cat /etc/rancher/k3s/k3s.yaml | grep "server:"
# Expected: server: https://127.0.0.1:6443
```

> **k3s quirk**: k3s recreates `k3s.yaml` on each restart with `600` permissions.
> If the agent starts before the chmod runs, it silently fails to connect.
> Add the chmod to the EC2 User Data or a systemd `ExecStartPre` on the agent unit.

---

## Fix 3 ΓÇö Restart Traefik to enable OTLP tracing

The agent log shows the Traefik sensor with `Instana tracing is not enabled` twice,
plus a `FrameworkEvent ERROR: Service factory returned null`. This means Traefik is
running but the `HelmChartConfig` that enables OTLP tracing has not been applied, or
Traefik has not been restarted since the config was applied.

```bash
# 1 ΓÇö Apply the HelmChartConfig (safe to re-apply; idempotent)
kubectl apply -f phase1-docker-to-k8s/traefik-instana.yaml

# 2 ΓÇö Restart Traefik to pick up the new settings
kubectl -n kube-system rollout restart deployment/traefik
kubectl -n kube-system rollout status deployment/traefik --timeout=120s

# 3 ΓÇö Confirm Traefik has the OTLP env var
kubectl -n kube-system get pod -l app.kubernetes.io/name=traefik \
  -o jsonpath='{.items[0].spec.containers[0].env}' \
  | python3 -m json.tool | grep -A2 "OTEL_EXPORTER"
# Expected:
# "name": "OTEL_EXPORTER_OTLP_ENDPOINT",
# "value": "http://10.x.x.x:4317"

# 4 ΓÇö Watch agent log for Traefik sensor re-activation (60 s window)
sudo grep -i "traefik" /opt/instana/agent/log/agent.log | tail -5
# Look for: "Activated Traefik Sensor" (not "Instana tracing is not enabled")
```

> The `FrameworkEvent ERROR: Service factory returned null` is **transient** ΓÇö it
> resolves by itself once Traefik is restarted with OTLP configured. It does **not**
> require an agent restart.

---

## Fix 4 ΓÇö Send traffic to generate traces ΓåÆ populate Application Services

Even with everything wired correctly, **Applications ΓåÆ Services** are empty until at
least one request creates a distributed trace. The Kubernetes infrastructure view
(pods, nodes) is populated from the k8s API ΓÇö no traffic required. Application
services require trace data.

```bash
EC2_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)

# Generate 10 requests across all services
for i in $(seq 1 10); do
  curl -sf "http://${EC2_IP}/api/auth/health"    > /dev/null
  curl -sf "http://${EC2_IP}/api/account/health" > /dev/null
done

# Watch agent log for OTLP span ingestion
sudo grep -i "span\|otlp\|auth-service\|account-service" \
  /opt/instana/agent/log/agent.log | tail -20
```

Allow 30ΓÇô60 s for Instana to populate **Applications ΓåÆ Services**.

---

## Full Recovery Sequence (run in order)

```bash
# ΓöÇΓöÇΓöÇ Step 0: Verify configuration ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
sudo grep -A3 "plugin.kubernetes" /opt/instana/agent/etc/instana/configuration.yaml
# Must show: enabled: true

# ΓöÇΓöÇΓöÇ Step 1: Fix kubeconfig permissions ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
sudo chmod 644 /etc/rancher/k3s/k3s.yaml

# ΓöÇΓöÇΓöÇ Step 2: Restart agent ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
sudo systemctl restart instana-agent
sleep 30

# ΓöÇΓöÇΓöÇ Step 3: Confirm k8s sensor activates ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
sudo grep -i "kubernetes\|k3s\|Activated" /opt/instana/agent/log/agent.log | tail -10

# ΓöÇΓöÇΓöÇ Step 4: Verify pods and namespace visible ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
kubectl -n banking get pods    # should be: all Running

# ΓöÇΓöÇΓöÇ Step 5: Apply Traefik config + restart ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
kubectl apply -f phase1-docker-to-k8s/traefik-instana.yaml
kubectl -n kube-system rollout restart deployment/traefik
kubectl -n kube-system rollout status deployment/traefik

# ΓöÇΓöÇΓöÇ Step 6: Send traffic ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
EC2_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
for i in $(seq 1 15); do
  curl -sf "http://${EC2_IP}/api/auth/health"    > /dev/null
  curl -sf "http://${EC2_IP}/api/account/health" > /dev/null
  sleep 1
done

# ΓöÇΓöÇΓöÇ Step 7: Verify OTLP traces arriving ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
sudo grep -i "otlp\|span" /opt/instana/agent/log/agent.log | tail -10

# ΓöÇΓöÇΓöÇ Step 8: Check Instana UI (wait 30ΓÇô60 s) ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
# Infrastructure ΓåÆ Kubernetes ΓåÆ banking namespace ΓåÆ pods Γ£ô
# Applications ΓåÆ Services ΓåÆ auth-service, account-service, ... Γ£ô
```

---

## Diagnostic Commands Reference

```bash
# Agent process running?
sudo systemctl status instana-agent

# Kubernetes sensor activated?
sudo grep -i "kubernetes" /opt/instana/agent/log/agent.log | tail -20

# k8s API reachable from host?
sudo kubectl get nodes
sudo kubectl get pods -n banking

# Kubeconfig permissions
ls -la /etc/rancher/k3s/k3s.yaml    # must be 644

# OTLP port listening
sudo ss -tlnp | grep 4317           # must show LISTEN 0.0.0.0:4317

# Traefik has OTLP env?
kubectl -n kube-system get pod -l app.kubernetes.io/name=traefik \
  -o jsonpath='{.items[0].spec.containers[0].env}' | python3 -m json.tool

# Pod OTEL endpoint resolves?
kubectl -n banking exec deploy/auth-service -- env | grep -E "NODE_IP|OTEL"
```

---

## Expected State After All Fixes

| Instana UI view | Expected state |
|---|---|
| Infrastructure ΓåÆ Hosts | EC2 node visible |
| Infrastructure ΓåÆ Kubernetes | `banking` namespace with all pods, deployments, services |
| Infrastructure ΓåÆ Processes | kong, postgres, redis, traefik, auth/account/transfer/notification PIDs |
| Applications ΓåÆ Services | auth-service, account-service, transfer-service, notification-service |
| Applications ΓåÆ Traces | Trace waterfall: Traefik ΓåÆ Kong ΓåÆ FastAPI ΓåÆ PostgreSQL/Redis |
| Technology ΓåÆ Kong | Kong API metrics (throughput, latency, status codes) |
| Technology ΓåÆ Redis | Redis memory, ops/sec, keyspace |
| Technology ΓåÆ PostgreSQL | DB connections, query latency, transaction rate |

> **Note**: `frontend` (Nginx) and `kong` do **not** appear in Applications ΓåÆ Services ΓÇö they
> have no OTLP instrumentation. They appear in Infrastructure only. This is expected.

---

## Why Discovery Timeout Warnings Are Benign

The agent log shows:

```
WARN  | Discovery for com.instana.plugin.ebpf took too long (11854 ms)
WARN  | Discovery for com.instana.plugin.gcp took too long (5899 ms)
WARN  | Discovery for com.instana.plugin.action took too long (5396 ms)
WARN  | Discovery for com.instana.plugin.postgresql took too long (5457 ms)
WARN  | Discovery time (64254 ms)
```

These are **normal on first boot** ΓÇö the dynamic agent downloads and starts many
sensor plugins simultaneously. The total `64254 ms` discovery time is a one-time
cost. After the agent warms up, discovery cycles are fast. The warnings do **not**
indicate that sensors failed ΓÇö all sensors (`instana-postgresql-sensor`,
`instana-redis-sensor`, `instana-nginx-sensor`, etc.) show `Installed ...` and
`Activated Sensor` messages confirming successful start.

---

## Related Docs

| File | What it covers |
|---|---|
| [`01-agent-install.md`](./01-agent-install.md) | Agent install on EC2, kubeconfig setup |
| [`02-kubernetes-monitoring.md`](./02-kubernetes-monitoring.md) | k8s sensor overview, OTLP pod-to-agent flow |
| [`09-pod-service-detection.md`](./09-pod-service-detection.md) | Infrastructure vs Application detection, OTLP checklist |
| [`05-traefik-sensor.md`](./05-traefik-sensor.md) | Traefik HelmChartConfig, OTLP tracing setup |