# Build & Push ΓÇö banking-demo services

## 0. Install Docker on Ubuntu (if not already installed)

```bash
# Add Docker's official GPG key and repo, then install
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu \
$(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin

# Allow current user to run docker without sudo (re-login required)
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
```

---

## 1. Login to ghcr.io

```bash
# Create a GitHub PAT: Settings ΓåÆ Developer settings ΓåÆ Personal access tokens (classic)
# Scopes required: write:packages, read:packages, delete:packages
echo <YOUR_GHCR_PAT> | docker login ghcr.io -u dungxnd --password-stdin
```

---

## 2. Build & Push

```bash
REGISTRY=ghcr.io/dungxnd/banking-demo TAG=v2

docker build -f services/auth-service/Dockerfile         -t $REGISTRY/auth-service:$TAG         . && \
docker build -f services/account-service/Dockerfile      -t $REGISTRY/account-service:$TAG      . && \
docker build -f services/transfer-service/Dockerfile     -t $REGISTRY/transfer-service:$TAG     . && \
docker build -f services/notification-service/Dockerfile -t $REGISTRY/notification-service:$TAG . && \
docker build -t $REGISTRY/frontend:$TAG frontend         && \
docker push $REGISTRY/auth-service:$TAG                  && \
docker push $REGISTRY/account-service:$TAG               && \
docker push $REGISTRY/transfer-service:$TAG              && \
docker push $REGISTRY/notification-service:$TAG          && \
docker push $REGISTRY/frontend:$TAG
```

---

## Changes in v2

- `common/observability.py`: strips `http://` scheme from `OTEL_EXPORTER_OTLP_ENDPOINT` before passing to `OTLPSpanExporter` ΓÇö the gRPC exporter expects bare `host:port`, not `http://host:port`
- All service Deployments: added `OTEL_EXPORTER_OTLP_PROTOCOL=grpc` env var
- `instana/configuration.yaml`: OTel listener bound to `0.0.0.0:4317` so pods on the k3s CNI network can reach the host agent
