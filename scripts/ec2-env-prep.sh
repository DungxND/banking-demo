#!/bin/bash
# EC2 User Data — banking-demo on k3s (Amazon Linux 2023 / Ubuntu 24.04)
#
# What this does:
#   1. Install k3s (Kubernetes + containerd, runs as a systemd service on the host)
#   2. Install helm
#   3. Clone the repo into ~/banking-demo (owned by the login user)
#   4. Build images with Docker (k3s has its own containerd but Docker is easiest
#      for building; images are imported into k3s via ctr)
#   5. Deploy via Helm
#   6. Install Instana host agent
#   7. Print access URLs
#
# k3s vs k3d: k3s runs directly on the host — the Instana host agent can read
# /etc/rancher/k3s/k3s.yaml, walk /proc for pod PIDs, and reach the k8s API at
# 127.0.0.1:6443 without any extra tunneling. k3d wraps k3s inside Docker
# containers which breaks all three of those requirements.
#
# After first boot, SSH in as the login user — no sudo needed for kubectl/helm/git.
set -euo pipefail

REPO_URL="https://github.com/dungxnd/banking-demo.git"

# Resolve latest Helm version at runtime — no hardcoded version to go stale.
# k3s ships its own kubectl so we don't need to resolve that separately.
HELM_VERSION=$(curl -fsSL https://api.github.com/repos/helm/helm/releases/latest \
  | grep -o '"tag_name": *"[^"]*"' | head -1 \
  | sed 's/.*"tag_name": *"\([^"]*\)"/\1/')

# ── Detect distro + login user ───────────────────────────────────────────────
if [ -f /etc/os-release ]; then
  . /etc/os-release
  DISTRO=$ID
else
  DISTRO=unknown
fi

case "$DISTRO" in
  amzn)   LOGIN_USER="ec2-user" ;;
  ubuntu) LOGIN_USER="ubuntu"   ;;
  *)      LOGIN_USER="ec2-user" ;;
esac

LOGIN_HOME=$(getent passwd "$LOGIN_USER" | cut -d: -f6)
REPO_DIR="$LOGIN_HOME/banking-demo"

# ── 1. Install base packages + Docker (for building images) ──────────────────
if [ "$DISTRO" = "amzn" ]; then
  dnf update -y
  dnf install -y docker git curl tar
  systemctl enable --now docker
elif [ "$DISTRO" = "ubuntu" ]; then
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg git tar
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io
  systemctl enable --now docker
fi

usermod -aG docker "$LOGIN_USER"

# ── 2. Install k3s ────────────────────────────────────────────────────────────
# --disable traefik: we use Kong as the gateway; traefik would conflict on :80/:443
# --write-kubeconfig-mode 644: Instana host agent must read this file; k3s
#   recreates it as 600 on each restart — setting mode here makes it persistent
curl -sfL https://get.k3s.io | \
  INSTALL_K3S_EXEC="--disable traefik --write-kubeconfig-mode 644" \
  sh -

# k3s installs kubectl at /usr/local/bin/kubectl automatically
# Symlink kubeconfig for normal user use (kubectl reads KUBECONFIG or ~/.kube/config)
mkdir -p "$LOGIN_HOME/.kube"
ln -sf /etc/rancher/k3s/k3s.yaml "$LOGIN_HOME/.kube/config"
chown -h "$LOGIN_USER:$LOGIN_USER" "$LOGIN_HOME/.kube" "$LOGIN_HOME/.kube/config"

# ── 3. Install Helm ───────────────────────────────────────────────────────────
curl -fsSL "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz" \
  | tar -xz -C /usr/local/bin --strip-components=1 linux-amd64/helm

# ── 4. Clone repo ─────────────────────────────────────────────────────────────
sudo -u "$LOGIN_USER" git clone --branch instana "$REPO_URL" "$REPO_DIR"

# ── 5. Build images with Docker + import into k3s containerd ─────────────────
# k3s uses its own containerd instance (/run/k3s/containerd/containerd.sock).
# The easiest bridge: build with Docker, save as tar, import via k3s ctr.
# All images are tagged as localhost/<name>:latest — k3s resolves "localhost"
# registry pulls from its own containerd store without needing a registry server.
cd "$REPO_DIR/final"

build_import() {
  local name=$1 dockerfile=$2 context=$3
  docker build -f "$dockerfile" "$context" -t "localhost/$name:latest"
  docker save "localhost/$name:latest" \
    | k3s ctr images import -
}

build_import api-producer         producer/Dockerfile                  .
build_import auth-service         services/auth-service/Dockerfile     .
build_import account-service      services/account-service/Dockerfile  .
build_import transfer-service     services/transfer-service/Dockerfile .
build_import notification-service services/notification-service/Dockerfile .
build_import frontend             frontend/Dockerfile                  frontend

# ── 6. Deploy with Helm ───────────────────────────────────────────────────────
cd "$REPO_DIR/final/helm"

# Override image repos to use the k3s local store; pullPolicy=Never so k3s
# never tries to pull from Docker Hub (the images are already imported above).
SETS=""
for svc in api-producer auth-service account-service transfer-service notification-service frontend; do
  SETS="$SETS --set ${svc}.image.repository=localhost/${svc}"
  SETS="$SETS --set ${svc}.image.tag=latest"
  SETS="$SETS --set ${svc}.image.pullPolicy=Never"
done

# Use KUBECONFIG explicitly since this runs as root but the file is at the k3s path
KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
helm upgrade --install banking-demo . \
  --namespace banking --create-namespace \
  -f charts/common/values.yaml \
  -f charts/postgres/values.yaml \
  -f charts/redis/values.yaml \
  -f charts/rabbitmq/values.yaml \
  -f charts/kong/values.yaml \
  -f charts/auth-service/values.yaml \
  -f charts/account-service/values.yaml \
  -f charts/transfer-service/values.yaml \
  -f charts/notification-service/values.yaml \
  -f charts/api-producer/values.yaml \
  -f charts/frontend/values.yaml \
  $SETS

KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
kubectl wait --for=condition=ready pod --all -n banking --timeout=300s

# ── 7. Instana host agent ─────────────────────────────────────────────────────
# Replace <AGENT_KEY> and <BACKEND_HOST> before using, or pass as instance tags.
# The one-liner is generated from: Instana UI → Agents → Install → Linux.
#
# INSTANA_AGENT_KEY="<your-agent-key>"
# INSTANA_BACKEND="ingress-<region>-saas.instana.io"
# curl -o setup_agent.sh https://setup.instana.io/agent \
#   && chmod 700 ./setup_agent.sh \
#   && sudo -E ./setup_agent.sh -a "$INSTANA_AGENT_KEY" -e "$INSTANA_BACKEND" -t dynamic -s
#
# After installing the agent, copy the pre-configured configuration.yaml:
#   sudo cp "$REPO_DIR/instana/configuration.yaml" \
#        /opt/instana/agent/etc/instana/configuration.yaml
#   sudo systemctl restart instana-agent
#
# The config already sets:
#   com.instana.plugin.kubernetes.enabled: true
#   com.instana.plugin.kubernetes.kubeconfig: /etc/rancher/k3s/k3s.yaml
#   com.instana.plugin.opentelemetry.grpc.listenAddress: 0.0.0.0:4317

# ── Done ──────────────────────────────────────────────────────────────────────
# IMDSv2-aware public IP lookup.
# --connect-timeout 3: don't hang if IMDS is slow on first boot.
# Modern EC2 instances enforce IMDSv2 (token required); the IMDSv1 fallback is
# kept only for older launch configs that still have it enabled.
IMDS="http://169.254.169.254"
TOKEN=$(curl -sf --connect-timeout 3 --max-time 5 \
  -X PUT "${IMDS}/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null || true)

if [ -n "$TOKEN" ]; then
  PUBLIC_IP=$(curl -sf --connect-timeout 3 --max-time 5 \
    -H "X-aws-ec2-metadata-token: $TOKEN" \
    "${IMDS}/latest/meta-data/public-ipv4" 2>/dev/null || true)
else
  # IMDSv1 fallback (only works when hop-limit allows it)
  PUBLIC_IP=$(curl -sf --connect-timeout 3 --max-time 5 \
    "${IMDS}/latest/meta-data/public-ipv4" 2>/dev/null || true)
fi

# If the instance has no public IP (private-only VPC), use the private IP instead
if [ -z "$PUBLIC_IP" ]; then
  if [ -n "$TOKEN" ]; then
    PUBLIC_IP=$(curl -sf --connect-timeout 3 --max-time 5 \
      -H "X-aws-ec2-metadata-token: $TOKEN" \
      "${IMDS}/latest/meta-data/local-ipv4" 2>/dev/null || echo "<instance-ip>")
  else
    PUBLIC_IP=$(curl -sf --connect-timeout 3 --max-time 5 \
      "${IMDS}/latest/meta-data/local-ipv4" 2>/dev/null || echo "<instance-ip>")
  fi
fi

echo ""
echo "=== Banking Demo deployed on k3s ==="
echo "  Frontend  : http://${PUBLIC_IP}:80  (via k3s ingress)"
echo "  Kong API  : http://${PUBLIC_IP}:8000"
echo ""
echo "SSH in then:"
echo "  kubectl get pods -n banking"
echo "  kubectl logs -n banking -l app=api-producer -f"
echo ""
echo "Rebuild a single service after code change:"
echo "  cd ~/banking-demo/final"
echo "  git pull"
echo "  docker build -f producer/Dockerfile . -t localhost/api-producer:latest"
echo "  docker save localhost/api-producer:latest | sudo k3s ctr images import -"
echo "  kubectl rollout restart deployment/api-producer -n banking"
echo ""
echo "Instana agent (install manually with your key):"
echo "  See: ~/banking-demo/instana/docs/01-agent-install.md"
echo "  Config: sudo cp ~/banking-demo/instana/configuration.yaml \\"
echo "               /opt/instana/agent/etc/instana/configuration.yaml"
