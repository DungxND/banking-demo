# OpenTelemetry ΓÇö Instana Agent OTLP Ingestion

> **Source:** https://www.ibm.com/docs/en/instana-observability/current?topic=opentelemetry  
> https://www.ibm.com/docs/en/instana-observability/current?topic=instana-agent (Sending OTel to agent)  
> https://www.ibm.com/docs/en/instana-observability/current?topic=collectors-opentelemetry-collector  
> Condensed for: banking-demo FastAPI microservices sending OTLP ΓåÆ Instana agent on EC2

---

## How OTel Fits into banking-demo

```
FastAPI service (Python)
  ΓööΓöÇ OTel SDK (opentelemetry-sdk)
       ΓööΓöÇ OTLP gRPC exporter ΓåÆ http://<NODE_IP>:4317
                                        Γöé
                              Instana host agent (EC2)
                                        Γöé
                              Instana backend (SaaS)
```

Each service uses [`common/observability.py`](../../common/observability.py):
- `FastAPIInstrumentor` ΓÇö auto-spans for every HTTP request
- `SQLAlchemyInstrumentor` ΓÇö spans for every SQL query
- `RedisInstrumentor` ΓÇö spans for every Redis command
- `OTLPSpanExporter` ΓÇö sends spans to `OTEL_EXPORTER_OTLP_ENDPOINT`

---

## Instana Agent OTLP Config

The agent accepts OTLP by default (agent ΓëÑ 1.1.726). Explicit config in [`instana/configuration.yaml`](../configuration.yaml):

```yaml
com.instana.plugin.opentelemetry:
  enabled: true
  # grpc:
  #   enabled: true
  #   port: 4317      # default
  # http:
  #   enabled: true
  #   port: 4318      # default
```

### Ports

| Protocol | Port | Default |
|----------|------|---------|
| OTLP/gRPC | 4317 | enabled |
| OTLP/HTTP | 4318 | enabled |

> **Important:** The agent listens on `0.0.0.0` by default. Pods reach it via the node IP (`status.hostIP`), not `localhost`.

---

## Pod Environment Variables

Set in each Deployment manifest (e.g. [`auth-service.yaml`](../../phase1-docker-to-k8s/auth-service.yaml)):

```yaml
env:
  - name: OTEL_SERVICE_NAME
    value: auth-service
  - name: OTEL_RESOURCE_ATTRIBUTES
    value: service.namespace=banking-demo,deployment.environment=production
  - name: NODE_IP
    valueFrom:
      fieldRef:
        fieldPath: status.hostIP
  - name: OTEL_EXPORTER_OTLP_ENDPOINT
    value: "http://$(NODE_IP):4317"
```

The OTel SDK merges `OTEL_SERVICE_NAME` and `OTEL_RESOURCE_ATTRIBUTES` automatically with the `Resource` object ΓÇö no code changes needed.

---

## Trace Headers Propagated

Config in [`instana/configuration.yaml`](../configuration.yaml):

```yaml
com.instana.tracing:
  extra-http-headers:
    - traceparent     # W3C Trace Context
    - tracestate
    - x-instana-t    # Instana native
    - x-instana-s
    - x-instana-l
```

Traefik injects `traceparent`/`tracestate` on inbound requests (via OTLP tracing configured in `HelmChartConfig` ΓÇö `--tracing.instana` was removed in Traefik v3) and banking services propagate them downstream via the OTel SDK automatically.

---

## OTel Signals Supported

| Signal | Status |
|--------|--------|
| Traces (OTLP/gRPC, OTLP/HTTP) | GA |
| Metrics (OTLP) | GA |
| Logs (OTLP) | GA |

Instana correlates OTel spans with its own AutoTrace spans. Mixed tracing (some hops instrumented with OTel, others with Instana tracer) is supported.

---

## OTel Collector (Optional ΓÇö not used in phase1)

If you want to pre-process or fan-out telemetry, deploy an OTel Collector between services and the Instana agent:

```yaml
# otelcol config.yaml excerpt
exporters:
  otlp:
    endpoint: <NODE_IP>:4317
    tls:
      insecure: true
processors:
  batch:
    send_batch_size: 5000
    timeout: 180s
service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp]
```

For phase1 the services export directly to the agent ΓÇö no collector needed.

---

## Verifying Traces in Instana UI

1. **Instana UI ΓåÆ Services** ΓÇö each banking service appears after first traces
2. **Instana UI ΓåÆ Analytics ΓåÆ Calls** ΓÇö filter by `service.name = auth-service` to see spans
3. **Instana UI ΓåÆ Infrastructure ΓåÆ EC2 node** ΓÇö shows OTel metrics from services

### Troubleshooting

```bash
# Check agent is listening on OTLP ports
sudo ss -tlnp | grep -E '4317|4318'

# Check agent accepted spans
sudo grep -i "opentelemetry\|otlp" /opt/instana/agent/log/agent.log | tail -20
```