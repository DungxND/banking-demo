#!/bin/bash
# ============================================================
# AWS EC2 User Data ΓÇö Phase 1: k3s + banking-demo on Ubuntu
# Paste this verbatim into the "User data" box when launching
# an EC2 instance (Amazon Linux 2023 / Ubuntu 22.04+).
#
# What this script does:
#   1. System update + essential packages
#   2. Install k3s (single-node, Traefik enabled)
#   3. Set KUBECONFIG for ubuntu user
#   4. Install NFS subdir provisioner (StorageClass: nfs-client)
#      ΓÇö uses hostPath via local-path as a fallback if no NFS
#   5. Clone the repo and deploy all manifests
#   6. Print access info to /var/log/banking-demo-setup.log
#
# BEFORE launching:
#   - Open ports 80 (HTTP), 443 (HTTPS), 6443 (k8s API),
#     8000 (Kong proxy) in the Security Group inbound rules.
#   - Recommended instance: t3.medium (2 vCPU / 4 GB RAM) or larger.
# ============================================================

# Re-exec as root when run manually as ubuntu (AWS User Data already runs as root)
if [[ $EUID -ne 0 ]]; then
  exec sudo bash "$0" "$@"
fi

set -euo pipefail
LOG=/var/log/banking-demo-setup.log
exec > >(tee -a "$LOG") 2>&1

echo "=== [$(date)] START banking-demo setup ==="

# -----------------------------------------------------------
# 1. System packages
# -----------------------------------------------------------
apt-get update -y
apt-get install -y \
  curl \
  git \
  jq

# -----------------------------------------------------------
# 2. Install k3s (single-node; Traefik stays enabled)
# -----------------------------------------------------------
echo "--- Installing k3s ---"
curl -sfL https://get.k3s.io | sh -

# Wait until the node is Ready
echo "--- Waiting for k3s node to be Ready ---"
until kubectl get nodes 2>/dev/null | grep -q " Ready"; do
  sleep 5
done
echo "--- k3s node is Ready ---"

# -----------------------------------------------------------
# 3. Make kubectl usable as ubuntu (no sudo needed)
# -----------------------------------------------------------
mkdir -p /home/ubuntu/.kube
cp /etc/rancher/k3s/k3s.yaml /home/ubuntu/.kube/config
chown ubuntu:ubuntu /home/ubuntu/.kube/config
chmod 600 /home/ubuntu/.kube/config

# Also persist KUBECONFIG in the ubuntu user's shell
echo 'export KUBECONFIG=/home/ubuntu/.kube/config' >> /home/ubuntu/.bashrc
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml   # for the rest of this script

# -----------------------------------------------------------
# 4. StorageClass "nfs-client" ΓÇö backed by local-path on this
#    single node. No external NFS server needed.
#    The manifests reference "nfs-client"; this satisfies that
#    name without any NFS daemon or provisioner pod.
# -----------------------------------------------------------
echo "--- Creating nfs-client StorageClass (local-path backed) ---"
if kubectl get storageclass nfs-client &>/dev/null; then
  echo "    StorageClass nfs-client already exists ΓÇö skipping"
else
  kubectl apply -f - <<'EOF'
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: nfs-client
  annotations:
    storageclass.kubernetes.io/is-default-class: "false"
provisioner: rancher.io/local-path
reclaimPolicy: Retain
volumeBindingMode: WaitForFirstConsumer
EOF
fi

# -----------------------------------------------------------
# 5. Clone repo and deploy
# -----------------------------------------------------------
REPO_DIR="/opt/banking-demo"
if [[ -d "$REPO_DIR/.git" ]]; then
  echo "--- Repo already cloned ΓÇö pulling latest ---"
  git -C "$REPO_DIR" pull --ff-only
else
  rm -rf "$REPO_DIR"
  git clone -b instana https://github.com/dungxnd/banking-demo.git "$REPO_DIR"
fi
cd "$REPO_DIR/phase1-docker-to-k8s"

# Apply manifests in dependency order
kubectl apply -f namespace.yaml
kubectl apply -f secret.yaml
kubectl apply -f postgres-init-configmap.yaml || true   # may not exist on all branches
kubectl apply -f kong-configmap.yaml
kubectl apply -f postgres.yaml
kubectl apply -f redis.yaml

# Wait for stateful sets before deploying services that depend on them
kubectl rollout status statefulset/postgres -n banking --timeout=120s || true
kubectl rollout status statefulset/redis    -n banking --timeout=120s || true

kubectl apply -f kong.yaml
kubectl apply -f auth-service.yaml
kubectl apply -f account-service.yaml
kubectl apply -f transfer-service.yaml
kubectl apply -f notification-service.yaml
kubectl apply -f frontend.yaml
kubectl apply -f ingress.yaml
kubectl apply -f traefik-instana.yaml

# -----------------------------------------------------------
# 6. Summary
# -----------------------------------------------------------
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo "unknown")

echo ""
echo "============================================================"
echo " banking-demo Phase 1 ΓÇö setup complete"
echo " Public IP : ${PUBLIC_IP}"
echo " Frontend  : http://${PUBLIC_IP}/"
echo " Kong proxy: http://${PUBLIC_IP}:8000/"
echo " k8s API   : https://${PUBLIC_IP}:6443"
echo ""
echo " Check pods:"
echo "   sudo kubectl get pods -n banking"
echo ""
echo " Full log: ${LOG}"
echo "============================================================"
echo "=== [$(date)] END banking-demo setup ==="
