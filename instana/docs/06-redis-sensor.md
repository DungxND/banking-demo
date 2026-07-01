# Redis Sensor

> **Source:** https://www.ibm.com/docs/en/instana-observability/current?topic=technologies-monitoring-redis  
> Condensed for: Redis 7.x StatefulSet in `banking` namespace (no auth, no TLS)

---

## How It Works

The Instana Redis sensor is **automatically installed** after the host agent is running. It connects to Redis using the credentials in `configuration.yaml` and runs `INFO` and `CONFIG GET` commands to collect metrics.

```
Instana agent (EC2 host)
  ΓööΓöÇ TCP connect ΓåÆ redis pod IP :6379 (every 10s)
       ΓööΓöÇ INFO, CONFIG GET, SLOWLOG GET, LATENCY LATEST
```

---

## Supported Versions

| Technology | Support policy | Latest supported |
|------------|---------------|-----------------|
| Redis | 45 days | 8.8.0 |

banking-demo uses Redis 7.x (stock `redis` Docker image).

---

## Requirements on Redis Side

- The `CONFIG` command must **not** be disabled or renamed
- The `INFO` command must be accessible
- No password required if Redis runs without auth (banking-demo default)

---

## Agent Configuration

From [`instana/configuration.yaml`](../configuration.yaml):

```yaml
com.instana.plugin.redis:
  username: ''   # Redis 6+ ACL username ΓÇö leave empty if no ACL
  password: ''   # Leave empty if no requirepass
  poll_rate: 10  # seconds between scrapes (default: 1s)
  hosts:
    - host: 'localhost'
      port: 32002   # NodePort ΓÇö stable even if pod restarts
  # config-command: 'CONFIG'  # rename if you used rename-command CONFIG in redis.conf
```

> **Why NodePort (`localhost:32002`)?** The Instana host agent runs on the EC2 node, not inside the cluster. It cannot resolve `redis.banking.svc.cluster.local` (k8s DNS is only available inside the pod network). The `redis-nodeport` NodePort service in [`redis.yaml`](../../phase1-docker-to-k8s/redis.yaml) exposes Redis on EC2 port 32002, which the host agent reaches via `localhost:32002`. This is stable across pod restarts, unlike a pod ClusterIP.

---

## ACL Permissions (Redis 6+ ΓÇö not needed for banking-demo)

If ACL is enabled, create a monitoring user with minimum permissions:

```redis
# In redis.conf or via redis-cli
ACL SETUSER instana-monitor on >password123 ~* -@all \
  +info +config|get +slowlog|get +pubsub|channels +pubsub|numpat +latency|latest
```

---

## Metrics Collected

| Category | Metrics |
|----------|---------|
| Memory | `used_memory`, `mem_fragmentation_ratio` |
| Clients | `connected_clients`, `blocked_clients` |
| Stats | `total_commands_processed`, `instantaneous_ops_per_sec` |
| Replication | `role`, `connected_slaves`, `repl_backlog_size` |
| Keyspace | Per-db keys, expires, avg_ttl |
| Latency | Command latency histograms |
| Slow log | Commands exceeding `slowlog-log-slower-than` |

---

## Client-Side Tracing

banking-demo services use `opentelemetry-instrumentation-redis` ΓÇö every Redis command generates an OTel span:

```python
# In common/observability.py ΓÇö already wired
RedisInstrumentor().instrument()
```

This connects Redis calls to the parent HTTP request span in the Instana trace waterfall.

---

## Verifying in Instana UI

1. **Infrastructure ΓåÆ EC2 node ΓåÆ Redis** ΓÇö memory, ops/sec, client count
2. **Analytics ΓåÆ Calls** ΓÇö filter `db.type=redis` to see all Redis spans
3. End-to-end trace: HTTP request ΓåÆ Redis GET/SET visible in one trace

### Troubleshooting

```bash
# Test Redis connectivity from EC2 host
redis-cli -h redis.banking.svc.cluster.local -p 6379 info server

# Check agent log
sudo grep -i "redis" /opt/instana/agent/log/agent.log | tail -20
```

Common issues:
- `redis_connection_failed` ΓÇö wrong IP/host, check pod IP with `kubectl -n banking get pod -o wide`
- `redis_config_command_unavailable` ΓÇö `CONFIG` was renamed, set `config-command` in the agent config