# Phase 1: Docker Compose ΓåÆ Kubernetes

Migrates the banking-demo stack from Docker Compose to Kubernetes using plain manifests.
See [ARCHITECTURE.md](./ARCHITECTURE.md) for the traffic flow diagram.

---

## Prerequisites ΓÇö get a cluster first

You need a running Kubernetes cluster with `kubectl` connected to it before any manifest can be applied.

### Option A ΓÇö k3s on your EC2 instance (recommended for this project)

SSH into EC2 and run:

```bash
curl -sfL https://get.k3s.io | sh -
```

Verify:

```bash
sudo kubectl get nodes
# Expected: your node in Ready state
```

k3s writes the kubeconfig to `/etc/rancher/k3s/k3s.yaml`. Prefix all `kubectl` commands with `sudo`, or run once to avoid it:

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
```

### Option B ΓÇö use `kubectl` from your local machine

Copy the kubeconfig from EC2 to your local machine:

```bash
# Run on your local machine
scp ubuntu@<ec2-ip>:/etc/rancher/k3s/k3s.yaml ~/.kube/config

# Fix the server address ΓÇö k3s defaults to 127.0.0.1, change to EC2 public IP
sed -i 's/127.0.0.1/<ec2-ip>/g' ~/.kube/config

kubectl get nodes   # verify connection
```

> Port `6443` must be open in your EC2 security group for your local IP.

---

## Deploy

All commands below run **on EC2** (or from your local machine if you did Option B above).

### Step 1 ΓÇö Clone the repo

```bash
git clone https://github.com/dungxnd/banking-demo.git
cd banking-demo/phase1-docker-to-k8s
```

### Step 2 ΓÇö Create the namespace

Everything else lives inside this namespace, so it must exist first:

```bash
kubectl apply -f namespace.yaml
```

### Step 3 ΓÇö Pull secret (first time only)

The cluster needs credentials to pull the app images from GitLab registry.

Create a deploy token in GitLab:
1. Your project ΓåÆ **Settings** ΓåÆ **Repository** ΓåÆ **Deploy tokens**
2. **Create deploy token** ΓåÆ tick scope `read_registry` ΓåÆ copy the username + token

```bash
kubectl -n banking create secret docker-registry gitlab-registry \
  --docker-server=registry.gitlab.com \
  --docker-username=<deploy-token-username> \
  --docker-password=<token>
```

<details>
<summary>Switching to GitHub Container Registry (ghcr.io)?</summary>

Create a PAT: GitHub ΓåÆ **Settings** ΓåÆ **Developer settings** ΓåÆ **Personal access tokens** ΓåÆ **Tokens (classic)** ΓåÆ scope `read:packages`.

```bash
kubectl -n banking create secret docker-registry github-registry \
  --docker-server=ghcr.io \
  --docker-username=<your-github-username> \
  --docker-password=<your-PAT>
```

Then update `imagePullSecrets` in each manifest from `gitlab-registry` to `github-registry`
and change the `image:` paths to `ghcr.io/...`.

</details>

<details>
<summary>Docker Hub rate limit (429 on postgres / redis / kong)?</summary>

```bash
kubectl -n banking create secret docker-registry dockerhub-registry \
  --docker-server=https://index.docker.io/v1/ \
  --docker-username=<your-dockerhub-username> \
  --docker-password=<your-token>
```

</details>

### Step 4 ΓÇö Deploy everything

```bash
kubectl apply -f .
```

Idempotent ΓÇö safe to re-run on updates.

### Step 5 ΓÇö Verify

```bash
kubectl get pods -n banking
# All pods should reach Running state within ~60s

kubectl get ingress -n banking
# Shows the IP to access the app
```

---

## Changing the image registry or tag

Edit the `image:` line in the relevant manifest:

```yaml
# example: auth-service.yaml
image: ghcr.io/<your-org>/banking-demo/auth-service:v2
```

Then re-run `kubectl apply -f .`.

> Images must be pushed to the registry before deploying. From your local machine:
> ```bash
> echo <PAT> | docker login ghcr.io -u <username> --password-stdin
> docker tag auth-service:v1 ghcr.io/<org>/banking-demo/auth-service:v1
> docker push ghcr.io/<org>/banking-demo/auth-service:v1
> ```

---

## Tear down

```bash
kubectl delete -f .
```

PVCs are not deleted automatically (data is preserved). Wipe them manually if needed:

```bash
kubectl delete pvc -n banking --all
```

---

## What's in this folder

| File | Kind | Notes |
|------|------|-------|
| `namespace.yaml` | Namespace | `banking` |
| `secret.yaml` | Secret | DB credentials, DATABASE_URL, REDIS_URL |
| `postgres-init-configmap.yaml` | ConfigMap | Mounts `01-stats-tracking.sql` into `/docker-entrypoint-initdb.d`; enables `track_counts`, `track_io_timing`, `track_activities` for the Instana PostgreSQL sensor |
| `postgres.yaml` | StatefulSet + Service | Headless, PVC on `local-path`, mounts postgres-init ConfigMap |
| `redis.yaml` | StatefulSet + Service | Headless, PVC 256Mi on `nfs-client` |
| `kong-configmap.yaml` | ConfigMap | Declarative Kong routes |
| `kong.yaml` | Deployment + Service | Proxy :8000, admin bound to loopback only |
| `auth-service.yaml` | Deployment + Service | Port 8001 |
| `account-service.yaml` | Deployment + Service | Port 8002 |
| `transfer-service.yaml` | Deployment + Service | Port 8003 |
| `notification-service.yaml` | Deployment + Service | Port 8004 |
| `frontend.yaml` | Deployment + Service | Nginx, port 80 |
| `ingress.yaml` | Ingress | Traefik, `/api` + `/ws` ΓåÆ Kong, `/` ΓåÆ frontend |
| `traefik-instana.yaml` | HelmChartConfig | Patches k3s Traefik: injects `INSTANA_AGENT_ENDPOINT` (host IP via Downward API) + `INSTANA_AGENT_ENDPOINT_PORT`, enables `--tracing.instana` |
