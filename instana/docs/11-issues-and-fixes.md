# Instana Integration — Issues & Fixes

A log of every real problem hit during the banking-demo Phase 1 Instana integration,
the root cause, and the exact fix applied. Useful for debugging the same problems on
a fresh setup.

---

## Issue 1 — `python_sensor_not_installed` / services not appearing in Applications

**Symptom**
- Agent log: `python_sensor_not_installed`
- Instana UI → Applications → Services: shows nothing for the Python microservices
- Infrastructure shows the pods but they have no service-level data

**Root cause**
The Instana Python sensor (`instana` package) was removed from `requirements.txt`
when migrating to OTel. The host agent detects Python processes via containerd but
cannot fingerprint them as named services without the sensor package present and
activated inside the process.

OTel OTLP traces and the Instana process-level sensor are **two separate things**:
- OTel pipeline → delivers distributed traces via OTLP/gRPC to agent port 4317
- Instana sensor → delivers CPU/mem/GC metrics + enables service fingerprinting

Both must be present.

**Fix**
1. Re-add `instana==3.16.0` to `common/requirements.txt` (alongside OTel packages)
2. Add `AUTOWRAPT_BOOTSTRAP=instana` env var to every service Deployment and in
   `docker-compose.yml` — activates the sensor via autowrapt at uvicorn startup,
   no code changes needed
3. `setuptools>=80.0.0` must also be in `requirements.txt` — required by autowrapt
   on Python 3.12+

```yaml
# k8s Deployment env section
- name: AUTOWRAPT_BOOTSTRAP
  value: instana
```

**Files changed**
- `common/requirements.txt`
- `phase1-docker-to-k8s/auth-service.yaml` (and account/transfer/notification)
- `docker-compose.yml`

---

## Issue 2 — Services appear as `uvicorn` / `banking` instead of individual names

**Symptom**
- Instana UI → Services: shows one entry called `uvicorn` or `banking` instead of
  `auth-service`, `account-service`, `transfer-service`, `notification-service`
- All four uvicorn processes grouped under a single generic name

**Root cause**
`OTEL_SERVICE_NAME` controls the `service.name` attribute on OTel **trace spans**.
The Instana Python sensor uses a **separate** env var `INSTANA_SERVICE_NAME` for
the process-level service name shown in Infrastructure and Services views.
Without `INSTANA_SERVICE_NAME`, the sensor falls back to the process binary name
(`uvicorn`) or the first meaningful string it can derive.

**Fix**
Add `INSTANA_SERVICE_NAME` to every service Deployment and `docker-compose.yml`:

```yaml
- name: INSTANA_SERVICE_NAME
  value: auth-service   # or account-service, transfer-service, notification-service
```

| Env var | Used by | Controls |
|---------|---------|---------|
| `OTEL_SERVICE_NAME` | OTel SDK | `service.name` on trace spans |
| `INSTANA_SERVICE_NAME` | Instana Python sensor | Service name in Infrastructure / Services UI |

**Files changed**
- `phase1-docker-to-k8s/auth-service.yaml` (and account/transfer/notification)
- `docker-compose.yml`

---

## Issue 3 — Frontend appears as `unspecified` in Services

**Symptom**
- Instana UI → Services: frontend shows as `unspecified` instead of `frontend`
- Infrastructure shows the Nginx process but with no useful service name

**Root cause**
Nginx does not support `INSTANA_SERVICE_NAME` (it is not a Python process).
The Instana Nginx sensor names the service by the process binary name unless
explicitly configured in `configuration.yaml` or via a pod annotation.

**Fix**
Two complementary changes:

1. Add `instana/service-name` pod annotation to `frontend.yaml`:
```yaml
# pod template metadata
annotations:
  instana/service-name: frontend
```

2. Add Nginx service name in `instana/configuration.yaml`:
```yaml
com.instana.plugin.nginx:
  service_name: frontend
```

After `sudo cp instana/configuration.yaml /opt/instana/agent/etc/instana/configuration.yaml`
the agent hot-reloads within ~10 s. The pod annotation takes effect on the next rollout.

**Files changed**
- `phase1-docker-to-k8s/frontend.yaml`
- `instana/configuration.yaml`

---

## Issue 4 — Kong sensor `Error while getting data from host localhost`

**Symptom**
- Agent log repeats every 30 s:
  ```
  ERROR | Kong | Error while getting data from host localhost
  ```
- Kong appears in Infrastructure but sensor shows no metrics

**Root cause — step 1: service still ClusterIP**
`kubectl apply` cannot change a Service `type` from `ClusterIP` to `NodePort`
in-place — it silently ignores the type change. The Kong service remained
`ClusterIP` so NodePort 32001 was never bound on the host.

**Fix — step 1**
```bash
kubectl delete svc kong -n banking
kubectl apply -f phase1-docker-to-k8s/kong.yaml
# Verify: kubectl get svc kong -n banking
# Expected: 8000:32000/TCP,8001:32001/TCP
```

**Root cause — step 2: `localhost` resolves to IPv6 on Ubuntu 22.04**
After the NodePort was bound, `curl http://localhost:32001` showed:
```
*   Trying [::1]:32001...   → Connection refused   (IPv6)
*   Trying 127.0.0.1:32001... → 200 OK             (IPv4)
```
Ubuntu 22.04 `/etc/hosts` lists `::1 localhost` before `127.0.0.1 localhost`.
The Instana Java agent resolves `localhost` to `::1` first and **does not retry
on the next address** when the connection is refused.

**Fix — step 2**
Change `localhost` → `127.0.0.1` in `instana/configuration.yaml`:

```yaml
com.instana.plugin.kong:
  remote:
    - host: '127.0.0.1'   # not 'localhost' — IPv6 ::1 is tried first on Ubuntu 22.04
      port: '32001'
```

Apply without agent restart (hot-reload):
```bash
sudo cp instana/configuration.yaml /opt/instana/agent/etc/instana/configuration.yaml
```

Same fix applied to the Redis sensor host for the same reason.

**Files changed**
- `phase1-docker-to-k8s/kong.yaml` (type: NodePort, nodePort: 32001)
- `instana/configuration.yaml` (localhost → 127.0.0.1 for Kong and Redis)
- `instana/configuration-docker-compose.yaml` (same IPv6 fix for parity)

---

## Issue 5 — `ImagePullBackOff` on new pods after rollout restart

**Symptom**
```
account-service-5b5b9c45b7-gr8k7   0/1   ImagePullBackOff   0   83s
```
Old pods stayed Running, new pods couldn't pull the image.

**Root cause**
CI auto-push tags images with the short SHA (e.g. `b35d634`).
Manifests pinned to `:v2` — a tag that existed when first built manually but was
never re-pushed by CI. The old pods were still running because k8s doesn't pull
on restart if the image is already cached locally.

**Fix**
Change all manifest image references to `:latest`:
```yaml
image: ghcr.io/dungxnd/banking-demo/auth-service:latest
```
CI always pushes `:latest` alongside the SHA tag, so manifests stay in sync
regardless of which SHA tag CI chose.

Also update workflow dispatch default from `v2` → `latest`.

**Files changed**
- All five `phase1-docker-to-k8s/*.yaml` service manifests
- `.github/workflows/docker-build.yml`

---

## Issue 6 — CI not triggering on manifest / config changes

**Symptom**
Pushing changes to `phase1-docker-to-k8s/**` or `instana/configuration.yaml`
did not trigger any CI job — pods on EC2 had to be updated manually.

**Root cause**
`docker-build.yml` only watches `services/**`, `common/**`, `frontend/**` —
paths that require a new image build. Manifest and agent config changes don't
need a new image; they need `kubectl apply + rollout restart` on EC2.

**Fix**
Add a separate `k8s-deploy.yml` workflow:
- Triggers on push to `instana` when `phase1-docker-to-k8s/**` or
  `instana/configuration.yaml` changes
- SSH into EC2, `git pull`, `kubectl apply -f phase1-docker-to-k8s/`,
  `kubectl rollout restart deployment -n banking`

Requires two repo secrets: `EC2_HOST` and `EC2_SSH_KEY`.

**Files changed**
- `.github/workflows/k8s-deploy.yml` (new)

---

## Quick reference: agent config hot-reload

Most `configuration.yaml` changes take effect without an agent restart:

```bash
# Pull latest config and copy to agent directory
cd /opt/banking-demo && git pull
sudo cp instana/configuration.yaml /opt/instana/agent/etc/instana/configuration.yaml

# Watch agent pick it up (within ~10 s)
sudo tail -f /opt/instana/agent/log/agent.log | grep -i "kong\|redis\|python\|reload"
```

Full restart (only needed for major changes like adding new sensor plugins):
```bash
sudo systemctl restart instana-agent
sudo systemctl status instana-agent
```
