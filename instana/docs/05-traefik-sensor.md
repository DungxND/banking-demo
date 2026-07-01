# Traefik Sensor

> **Source:** https://www.ibm.com/docs/en/instana-observability/current?topic=technologies-monitoring-traefik  
> **Traefik v3 tracing ref:** https://doc.traefik.io/traefik/v3.7/reference/install-configuration/observability/tracing/  
> **Migration guide:** https://doc.traefik.io/traefik/v3.7/migrate/v2-to-v3-details/#tracing  
> Condensed for: k3s built-in Traefik v3, patched via `HelmChartConfig` (banking-demo phase1)

> **ΓÜá∩╕Å Traefik v3 breaking change:** `--tracing.instana` and `INSTANA_AGENT_ENDPOINT` were **removed in Traefik v3**. All vendor-specific tracing backends (Instana, Jaeger, Zipkin, Datadog, Elastic) were removed. Tracing is now exclusively via OTLP. The `HelmChartConfig` uses `tracing.otlp.grpc` Helm values pointed at the Instana agent's OTLP port (4317).

---

## How It Works

The Instana Traefik sensor is **automatically deployed** after the host agent is installed. It collects:
- **Metrics** via Traefik's Prometheus endpoint (scraped by the agent every 1 s)
- **Distributed traces** via OTLP/gRPC ΓåÆ Instana agent :4317 (Traefik v3)

```
User request
  ΓööΓöÇ Traefik (k3s ingress, :80/:443)
       Γö£ΓöÇ OTLP span sent to Instana agent :4317 on NODE_IP
       Γö£ΓöÇ W3C traceparent/tracestate headers propagated downstream
       Γö£ΓöÇ Prometheus /metrics exposed on :9100
       Γöé       ΓööΓöÇ Instana agent scrapes every 1s
       ΓööΓöÇ Request forwarded to kong:8000 or frontend:80
```

---

## Supported Versions

| Technology | Support policy | Latest supported |
|------------|---------------|-----------------|
| Traefik | On demand | 3.4 |

k3s v1.28+ ships Traefik v3. Run `kubectl -n kube-system exec -it deploy/traefik -- traefik version` to confirm.

---

## k3s-Specific Configuration

k3s manages Traefik via an internal Helm chart. The correct way to patch it is a `HelmChartConfig` resource applied to `kube-system`. **Do not use `additionalArguments` for tracing** ΓÇö use the `tracing:` Helm values block directly.

File: [`phase1-docker-to-k8s/traefik-instana.yaml`](../../phase1-docker-to-k8s/traefik-instana.yaml)

```yaml
apiVersion: helm.cattle.io/v1
kind: HelmChartConfig
metadata:
  name: traefik
  namespace: kube-system
spec:
  valuesContent: |-
    env:
      - name: NODE_IP
        valueFrom:
          fieldRef:
            fieldPath: status.hostIP
      # OTEL_EXPORTER_OTLP_ENDPOINT overrides tracing.otlp.grpc.endpoint at runtime.
      # Kubernetes expands $(NODE_IP) in env value: fields ΓÇö this is how we pass
      # the dynamic node IP since Helm values are static YAML strings.
      - name: OTEL_EXPORTER_OTLP_ENDPOINT
        value: "http://$(NODE_IP):4317"

    # Helm chart tracing values (Traefik v3 ΓÇö OTLP only)
    # OTEL_EXPORTER_OTLP_ENDPOINT above overrides endpoint at runtime.
    tracing:
      otlp:
        grpc:
          endpoint: "localhost:4317"   # static fallback; env var takes precedence
          insecure: true

    additionalArguments:
      - "--entrypoints.metrics.address=:9100"
      - "--metrics.prometheus.entryPoint=metrics"

    ports:
      metrics:
        port: 9100
        exposedPort: 9100
```

### Why `OTEL_EXPORTER_OTLP_ENDPOINT` instead of `tracing.otlp.grpc.endpoint`

The Helm values `tracing.otlp.grpc.endpoint` is a **static string** ΓÇö `$(NODE_IP)` does not expand inside YAML. Kubernetes **does** expand env var references in `env[].value` fields. Traefik v3 honours the standard `OTEL_EXPORTER_OTLP_ENDPOINT` env var and uses it to override the static endpoint, so `http://$(NODE_IP):4317` resolves correctly at pod creation time.

### Apply

```bash
kubectl apply -f phase1-docker-to-k8s/traefik-instana.yaml
kubectl -n kube-system rollout restart deployment/traefik
kubectl -n kube-system rollout status deployment/traefik
```

---

## Agent Configuration

From [`instana/configuration.yaml`](../configuration.yaml):

```yaml
com.instana.plugin.traefik:
  enabled: true
  poll_rate: 1    # seconds between Prometheus metrics scrapes
```

`poll_rate: 1` gives 1-second resolution on HTTP requests and config reload metrics.

---

## What is Collected

### Configuration Data
- PID, version, start time

### Performance Metrics

| Metric | Description | Granularity |
|--------|-------------|-------------|
| HTTP requests/sec | Per second across all entrypoints | 1 s |
| Config last reload success | Timestamp of last successful config reload | 1 s |
| Config reload count | Reloads per second | 1 s |
| Entrypoints | HTTP requests/sec per entrypoint (max 100) | 1 s |

### Tracing (Traefik v3 ΓÇö OTLP)
- Every request through Traefik generates an OTLP span
- Span sent to Instana agent `:4317` via gRPC (insecure)
- W3C `traceparent` / `tracestate` headers propagated to all downstream services
- Connects the frontend ΓåÆ Kong ΓåÆ microservice call chain in Instana UI

---

## Traffic Flow Traced in banking-demo

```
Internet
  ΓööΓöÇ Traefik (OTLP span ΓåÆ Instana agent :4317)
       Γö£ΓöÇ path /          ΓåÆ frontend:80
       Γö£ΓöÇ path /api/*     ΓåÆ kong:8000 (OTel context continues via traceparent)
       Γöé                         ΓööΓöÇ auth/account/transfer/notification-service
       ΓööΓöÇ path /ws        ΓåÆ kong:8000 ΓåÆ notification-service (WebSocket)
```

---

## Verifying Tracing is Active

```bash
# 1. Check Traefik pod log ΓÇö should be EMPTY (no tracing errors)
kubectl -n kube-system logs -l app.kubernetes.io/name=traefik --tail=50 \
  | grep -i "instana\|tracing\|otlp\|error"

# 2. Confirm OTEL_EXPORTER_OTLP_ENDPOINT was set with actual node IP
kubectl -n kube-system get pod -l app.kubernetes.io/name=traefik \
  -o jsonpath='{.items[0].spec.containers[0].env}' | python3 -m json.tool \
  | grep -A2 OTEL_EXPORTER

# 3. Verify Prometheus metrics endpoint is accessible
kubectl -n kube-system port-forward svc/traefik 9100:9100 &
curl -s http://localhost:9100/metrics | grep traefik_

# 4. Check Instana agent sees Traefik
sudo grep -i "traefik" /opt/instana/agent/log/agent.log | tail -20
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `"Instana Tracing backend has been removed in v3"` in Traefik pod log | Old `--tracing.instana=true` still in `additionalArguments` | Remove it ΓÇö use `tracing.otlp.grpc` Helm values instead |
| `"Instana tracing is not enabled"` in Instana agent log | Traefik pod not yet restarted after applying `HelmChartConfig`, or `tracing:` block missing from `valuesContent` | `kubectl rollout restart deployment/traefik -n kube-system` |
| `FrameworkEvent ERROR: Service factory returned null (com.instana.agent.traefik.sensor.Traefik)` in agent log | Instana Traefik sensor tried to initialize while Traefik reported tracing disabled ΓÇö OSGi component returns null on first bind | **Transient** ΓÇö resolves automatically once Traefik pod restarts with OTLP tracing configured |
| `"Error while getting data from host localhost"` in Kong sensor | Kong pod restarted during Traefik rollout ΓÇö NodePort 32001 briefly unreachable | **Transient** ΓÇö Kong sensor retries every 30 s; errors stop once Kong pod is Ready again |
| `traefik_metrics_api_not_accessible` | Prometheus `/metrics` endpoint not exposed on `:9100` | Add `ports.metrics` block and `--entrypoints.metrics.address=:9100` to `additionalArguments` |
| Spans missing in Instana UI after tracing configured | `OTEL_EXPORTER_OTLP_ENDPOINT` not reaching agent ΓÇö check agent is listening | `sudo ss -tlnp \| grep 4317` on EC2; verify no firewall blocks pod-to-host traffic |