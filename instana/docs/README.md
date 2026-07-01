# Instana Docs ΓÇö banking-demo Phase 1 (k3s on EC2)

Reference documentation for running Instana observability on the banking-demo stack deployed with [`phase1-docker-to-k8s/`](../../phase1-docker-to-k8s/).

All docs are condensed from the official IBM Instana docs at <https://www.ibm.com/docs/en/instana-observability> ΓÇö shortened to what is relevant for our specific stack.

---

## Stack Overview

| Component | Kind | Monitored by |
|-----------|------|-------------|
| EC2 Ubuntu instance | Host | Instana host agent (systemd) |
| k3s (Kubernetes) | Cluster | Next-gen k8s sensor (auto) |
| Traefik | Ingress | Traefik sensor (auto) |
| Kong 3.9 | API Gateway | Kong sensor (remote, configured) |
| auth / account / transfer / notification services | FastAPI (Python) | OTel OTLP ΓåÆ agent :4317 |
| frontend | Nginx | Process sensor (auto) |
| PostgreSQL 15/16 | StatefulSet | PostgreSQL sensor (configured) |
| Redis 7.x | StatefulSet | Redis sensor (configured) |
| Synthetic tests | PoP (cloud) | Synthetic monitoring |

---

## Docs Index

| File | What it covers |
|------|---------------|
| [`01-agent-install.md`](./01-agent-install.md) | Installing the Instana host agent on Ubuntu EC2 via one-liner. Directory layout, kubeconfig access, verification |
| [`02-kubernetes-monitoring.md`](./02-kubernetes-monitoring.md) | How the host agent monitors k3s. Pod discovery, RBAC, OTLP flow from pods to agent, Traefik HelmChartConfig |
| [`03-opentelemetry.md`](./03-opentelemetry.md) | OTel OTLP ingestion by the agent. FastAPI instrumentation, pod env vars, trace header propagation, troubleshooting |
| [`04-kong-sensor.md`](./04-kong-sensor.md) | Remote Kong monitoring. Prerequisites (Prometheus plugin), `configuration.yaml` block, metrics, troubleshooting |
| [`05-traefik-sensor.md`](./05-traefik-sensor.md) | Traefik metrics + tracing. k3s HelmChartConfig, agent config, what is collected, troubleshooting |
| [`06-redis-sensor.md`](./06-redis-sensor.md) | Redis sensor. NodePort config, ACL requirements, metrics, client-side OTel tracing, troubleshooting |
| [`07-postgresql-sensor.md`](./07-postgresql-sensor.md) | PostgreSQL sensor. Stats tracking setup, agent config, auto-discovery, metrics, client-side OTel tracing, troubleshooting |
| [`08-synthetic-monitoring.md`](./08-synthetic-monitoring.md) | API Script synthetic tests. Creating tests in UI, variables, Smart Alerts, PoP selection |
| [`09-pod-service-detection.md`](./09-pod-service-detection.md) | **ΓÜá∩╕Å Services show 0 calls / pods not detected as Services.** How infrastructure vs application detection works, OTLP flow checklist, Application Perspective setup, full verification sequence |
| [`10-host-agent-k8s-detection-fix.md`](./10-host-agent-k8s-detection-fix.md) | **ΓÜá∩╕Å Root cause fix for agent not detecting k8s pods/services.** Log-based diagnosis, `enabled: true` fix, kubeconfig permissions, Traefik restart, full recovery sequence |

---

## Quick Start: First-Time Setup

```bash
# 1. Install Instana agent on EC2 (from Instana UI: Agents ΓåÆ Install ΓåÆ Linux one-liner)
curl -o setup_agent.sh https://setup.instana.io/agent \
  && chmod 700 ./setup_agent.sh \
  && sudo -E ./setup_agent.sh -a <AGENT_KEY> -e <BACKEND_HOST> -t dynamic -s

# 2. Copy our configuration (includes com.instana.plugin.kubernetes: enabled: true)
sudo cp instana/configuration.yaml \
     /opt/instana/agent/etc/instana/configuration.yaml

# 3. Make k3s kubeconfig readable (REQUIRED ΓÇö agent reads k8s API via this file)
sudo chmod 644 /etc/rancher/k3s/k3s.yaml

# 4. Restart agent to pick up config + kubeconfig permissions
sudo systemctl restart instana-agent

# 5. Apply Traefik Instana patch (enables OTLP tracing + Prometheus metrics)
kubectl apply -f phase1-docker-to-k8s/traefik-instana.yaml
kubectl -n kube-system rollout restart deployment/traefik
kubectl -n kube-system rollout status deployment/traefik

# 6. Verify agent is up and k8s sensor activated
sudo systemctl status instana-agent
sudo grep -i "kubernetes\|Activated\|ERROR" /opt/instana/agent/log/agent.log | tail -20
```

After ~30ΓÇô60 s the host and all k8s pods appear in **Instana UI ΓåÆ Infrastructure ΓåÆ Kubernetes**.
Services populate in **Applications ΓåÆ Services** after the first HTTP requests generate traces.

> **If pods are still not detected**: see [`10-host-agent-k8s-detection-fix.md`](./10-host-agent-k8s-detection-fix.md)
> for a step-by-step diagnosis based on the agent log.

---

## Related Files

| File | Description |
|------|-------------|
| [`instana/configuration.yaml`](../configuration.yaml) | Main agent config (zone, tags, Kong, Redis, PostgreSQL, OTel, tracing headers, secrets) |
| [`instana/configuration-docker-compose.yaml`](../configuration-docker-compose.yaml) | Agent config for local Docker Compose mode |
| [`instana/synthetic/`](../synthetic/) | API Script synthetic tests (`health-checks.js`, `user-login-flow.js`, `transfer-flow.js`, `auth-edge-cases.js`) |
| [`phase1-docker-to-k8s/traefik-instana.yaml`](../../phase1-docker-to-k8s/traefik-instana.yaml) | HelmChartConfig that enables Traefik tracing + Prometheus metrics |
| [`phase1-docker-to-k8s/kong-configmap.yaml`](../../phase1-docker-to-k8s/kong-configmap.yaml) | Kong declarative config with Prometheus plugin enabled |
| [`phase1-docker-to-k8s/postgres-init-configmap.yaml`](../../phase1-docker-to-k8s/postgres-init-configmap.yaml) | PostgreSQL init SQL enabling track_counts, track_io_timing, track_activities |
| [`common/observability.py`](../../common/observability.py) | FastAPI OTel + Prometheus instrumentation (used by all microservices) |

---

## Official Instana Docs (full)

- Agent install: <https://www.ibm.com/docs/en/instana-observability/current?topic=linux-installing-agent>
- EC2: <https://www.ibm.com/docs/en/instana-observability/current?topic=aws-ec2>
- Kubernetes sensor: <https://www.ibm.com/docs/en/instana-observability/current?topic=kubernetes-installing-agent>
- OpenTelemetry: <https://www.ibm.com/docs/en/instana-observability/current?topic=opentelemetry>
- Kong: <https://www.ibm.com/docs/en/instana-observability/current?topic=technologies-monitoring-kong-api-gateway>
- Traefik: <https://www.ibm.com/docs/en/instana-observability/current?topic=technologies-monitoring-traefik>
- Redis: <https://www.ibm.com/docs/en/instana-observability/current?topic=technologies-monitoring-redis>
- PostgreSQL: <https://www.ibm.com/docs/en/instana-observability/current?topic=technologies-monitoring-postgresql>
- Synthetic monitoring: <https://www.ibm.com/docs/en/instana-observability/current?topic=instana-synthetic-monitoring>
- Agent configuration file: <https://www.ibm.com/docs/en/instana-observability/current?topic=cha-configuring-host-agents-by-using-agent-configuration-file>
- Service detection (Application Perspectives): <https://www.ibm.com/docs/en/instana-observability/current?topic=instana-application-perspectives>