# PostgreSQL Sensor

> **Source:** https://www.ibm.com/docs/en/instana-observability/current?topic=technologies-monitoring-postgresql  
> Condensed for: PostgreSQL 15/16 StatefulSet in `banking` namespace

---

## How It Works

The Instana PostgreSQL sensor is **automatically deployed** after the host agent runs. It connects to PostgreSQL using the credentials in `configuration.yaml` and queries `pg_stat_*` views.

```
Instana agent (EC2 host)
  ΓööΓöÇ JDBC connect ΓåÆ postgres.banking.svc.cluster.local:5432
       ΓööΓöÇ SELECT from pg_stat_activity, pg_stat_user_tables,
                      pg_stat_bgwriter, pg_locks, pg_database
```

---

## Supported Versions

| Technology | Support policy | Latest supported |
|------------|---------------|-----------------|
| PostgreSQL | 45 days | 18.4 |

banking-demo uses PostgreSQL 15/16.

---

## Required: Enable Statistics Collection

The sensor needs PostgreSQL statistics tracking enabled. This is done in banking-demo via the init ConfigMap [`postgres-init-configmap.yaml`](../../phase1-docker-to-k8s/postgres-init-configmap.yaml).

### What's required in `postgresql.conf`

```sql
track_activities = on    -- monitors current command per connection
track_counts = on        -- cumulative stats for table/index access
track_io_timing = on     -- block read/write times
```

### Persistent config (survives restarts)

```sql
ALTER SYSTEM SET track_activities = 'on';
ALTER SYSTEM SET track_counts = 'on';
ALTER SYSTEM SET track_io_timing = 'on';
SELECT pg_reload_conf();

-- Verify
SHOW track_activities;
SHOW track_counts;
SHOW track_io_timing;
```

---

## Agent Configuration

From [`instana/configuration.yaml`](../configuration.yaml):

```yaml
com.instana.plugin.postgresql:
  user: banking
  password: bankingpass
  database: banking
  # host and port not required ΓÇö agent auto-discovers the postgres
  # process via PID scanning (sees the containerd process on the host).
  # The agent connects to the pod IP it discovers (e.g. 10.42.0.12:5432).
```

> **How auto-discovery works:** The host agent scans running processes on the EC2 node, finds the `postgres` binary via containerd (PID visible at the host level), and connects to the IP/port it reads from the process's listening socket. In the agent log: `Connected to PostgreSQL 'banking'@'10.42.0.12:5432'`.
>
> If auto-discovery doesn't work (e.g., after a pod restart with a new IP), you can explicitly expose PostgreSQL via a NodePort and point the agent there. PostgreSQL does **not** have a NodePort in `postgres.yaml` by default ΓÇö add one if needed.

---

## Metrics Collected

| Category | Metrics |
|----------|---------|
| Connections | `numbackends`, `max_conn`, active/idle/waiting |
| Transactions | `xact_commit`, `xact_rollback`, TPS |
| I/O | `blks_read`, `blks_hit`, cache hit ratio |
| Locks | Lock types, wait count |
| Tables | Rows inserted/updated/deleted, seq/idx scans |
| Background writer | `buffers_clean`, `checkpoints_timed` |
| Replication | LSN lag (if replicas present) |
| Query performance | Top slow queries (if `pg_stat_statements` enabled) |

---

## Client-Side Tracing

banking-demo services use `opentelemetry-instrumentation-sqlalchemy`. Every SQL query produces an OTel span with:
- `db.statement` ΓÇö SQL query text
- `db.table` ΓÇö table name
- `db.operation` ΓÇö SELECT / INSERT / UPDATE

```python
# In common/observability.py ΓÇö already wired
SQLAlchemyInstrumentor().instrument(engine=_engine)
```

---

## Verifying in Instana UI

1. **Infrastructure ΓåÆ EC2 node ΓåÆ PostgreSQL** ΓÇö connections, TPS, cache hit ratio
2. **Analytics ΓåÆ Calls** ΓÇö filter `db.type=postgresql` to see all SQL spans
3. End-to-end trace: HTTP request ΓåÆ SQL SELECT visible in one trace

### Troubleshooting

```bash
# Test DB connectivity
psql -h postgres.banking.svc.cluster.local -U banking -d banking -c "SELECT 1"

# Verify stats tracking is enabled
psql -h postgres.banking.svc.cluster.local -U banking -d banking \
  -c "SHOW track_activities; SHOW track_counts; SHOW track_io_timing;"

# Check agent log
sudo grep -i "postgresql\|postgres" /opt/instana/agent/log/agent.log | tail -20
```

Common issues:
- `postgresql_connection_failed` ΓÇö check credentials in `configuration.yaml`, verify Service DNS
- Stats views returning 0 ΓÇö `track_counts`/`track_io_timing` not enabled, run `ALTER SYSTEM SET ...` above