# Kong API Gateway Sensor

> **Source:** https://www.ibm.com/docs/en/instana-observability/current?topic=technologies-monitoring-kong-api-gateway  
> Condensed for: Kong 3.9 DB-less, remote monitoring from Instana host agent on EC2

---

## How It Works

The Instana Kong sensor is **automatically installed** after the host agent is running. For remote monitoring (agent on EC2 host, Kong inside k3s cluster), configure the sensor with the Kong Admin API address.

```
Instana agent (EC2 host)
  ΓööΓöÇ HTTP poll every 30s ΓåÆ kong.banking.svc.cluster.local:8001 (Admin API)
  ΓööΓöÇ Prometheus scrape ΓåÆ kong-proxy :8000/metrics (via Prometheus plugin)
```

---

## Prerequisites

### 1. Kong Admin API accessibility

In banking-demo, Kong's admin API is bound to `127.0.0.1:8001` inside the pod (loopback only). The agent accesses it via the **Kubernetes Service** `kong.banking.svc.cluster.local:8001`.

> **Security note:** The Kong Service exposes port 8001 within the cluster only ΓÇö not externally. This is sufficient for the host agent since it runs on the EC2 node that has access to the cluster network.

### 2. Prometheus plugin enabled

The sensor depends on the Kong Prometheus plugin for latency, bandwidth, and request metrics. Enabled globally in [`kong-configmap.yaml`](../../phase1-docker-to-k8s/kong-configmap.yaml):

```yaml
plugins:
  - name: prometheus
    config:
      status_code_metrics: true
      latency_metrics: true
      bandwidth_metrics: true
      upstream_health_metrics: true
```

---

## Supported Versions

| Technology | Support policy | Latest supported |
|------------|---------------|-----------------|
| Kong Gateway (OSS/Enterprise) | On demand | 3.10.0.0 |

Banking-demo uses Kong 3.9.

---

## Agent Configuration

From [`instana/configuration.yaml`](../configuration.yaml):

```yaml
com.instana.plugin.kong:
  enabled: true
  dataset_size: 10                         # max rows for service/route metrics
  status_code_group: '2xx,3xx,4xx,5xx'    # status code buckets to collect
  remote:
    - host: 'kong.banking.svc.cluster.local'
      port: '8001'
      availabilityZone: 'banking-ec2-prod'
      poll_rate: 30                        # seconds (minimum: 30 per Instana docs)
      protocol: 'http'
      # username: ''   # only if RBAC basic auth enabled
      # password: ''
      # admin_token: ''  # only if Kong-Admin-Token RBAC enabled
```

### Key Notes

- `poll_rate` minimum is **30 seconds** ΓÇö do not set lower
- `disabled_metrics` is omitted ΓåÆ all metrics are collected
- No auth configured ΓÇö banking-demo Kong runs DB-less without RBAC
- Multiple `remote` entries can be listed for multiple Kong instances

---

## Metrics Collected

| Metric | Description |
|--------|-------------|
| Total HTTP requests | By service, route, status code |
| Kong latency | Time Kong spends processing requests |
| Upstream latency | Time upstream service takes to respond |
| Bandwidth | Ingress/egress bytes per service |
| Upstream health | Status of upstream targets |

---

## Kong Routes Monitored (banking-demo)

| Route | Upstream service | Port |
|-------|-----------------|------|
| `/api/auth` | auth-service | 8001 |
| `/api/account` | account-service | 8002 |
| `/api/transfer` | transfer-service | 8003 |
| `/api/notifications` | notification-service | 8004 |
| `/ws` | notification-service | 8004 |

---

## Verifying in Instana UI

1. **Infrastructure ΓåÆ EC2 node ΓåÆ Kong** ΓÇö Kong dashboard with request rates, latency
2. **Services ΓåÆ kong** ΓÇö service health and call graph
3. Check agent log:

```bash
sudo grep -i "kong" /opt/instana/agent/log/agent.log | tail -20
```

### Common Issue: `kong_admin_api_not_accessible`

Cause: The agent cannot reach the Admin API.

Fix: Verify the Kubernetes Service is reachable from the EC2 host:

```bash
# From EC2 host ΓÇö test Kong admin API via cluster DNS
curl http://kong.banking.svc.cluster.local:8001/status

# Or use the ClusterIP directly
kubectl -n banking get svc kong -o jsonpath='{.spec.clusterIP}'
curl http://<CLUSTER_IP>:8001/status
```