# Prerequisites - Yêu Cầu Chung

## 📋 Tổng Quan

Tài liệu này liệt kê các yêu cầu chung để triển khai Banking Demo lên các môi trường IBM Cloud.

## 🔧 Tools & CLI Cần Thiết

### 1. Kubernetes CLI (kubectl)
```bash
# Kiểm tra version
kubectl version --client

# Cài đặt (nếu chưa có)
# Windows (PowerShell)
choco install kubernetes-cli

# macOS
brew install kubectl

# Linux
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
```

**Version yêu cầu:** >= 1.24

### 2. Helm
```bash
# Kiểm tra version
helm version

# Cài đặt
# Windows
choco install kubernetes-helm

# macOS
brew install helm

# Linux
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

**Version yêu cầu:** >= 3.10

### 3. IBM Cloud CLI
```bash
# Cài đặt
# Windows
# Download từ: https://cloud.ibm.com/docs/cli?topic=cli-install-ibmcloud-cli

# macOS
curl -fsSL https://clis.cloud.ibm.com/install/osx | sh

# Linux
curl -fsSL https://clis.cloud.ibm.com/install/linux | sh

# Kiểm tra
ibmcloud --version

# Login
ibmcloud login
```

### 4. OpenShift CLI (oc) - Chỉ cho OpenShift
```bash
# Download từ OpenShift console
# Hoặc cài đặt:

# Windows
choco install openshift-cli

# macOS
brew install openshift-cli

# Linux
wget https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest/openshift-client-linux.tar.gz
tar -xvf openshift-client-linux.tar.gz
sudo mv oc /usr/local/bin/

# Kiểm tra
oc version
```

### 5. Docker (Optional - cho local testing)
```bash
# Kiểm tra
docker --version

# Cài đặt Docker Desktop
# Windows/macOS: https://www.docker.com/products/docker-desktop
```

### 6. Git
```bash
# Kiểm tra
git --version

# Clone repository
git clone <your-repo-url>
cd banking-demo
```

## 🔑 IBM Cloud Account & Access

### 1. IBM Cloud Account
- ✅ Tạo account tại: https://cloud.ibm.com/registration
- ✅ Verify email
- ✅ Setup payment method (nếu dùng paid services)

### 2. IBM Technology Zone Access (Cho nhân viên IBM)
- ✅ Truy cập: https://techzone.ibm.com
- ✅ Login bằng IBM ID (w3id)
- ✅ Complete profile setup
- ✅ Đọc Terms of Use

### 3. IBM Cloud API Key
```bash
# Tạo API key
ibmcloud iam api-key-create banking-demo-key -d "Banking Demo API Key" --file api-key.json

# Set API key
export IBMCLOUD_API_KEY=$(cat api-key.json | jq -r .apikey)

# Hoặc login bằng API key
ibmcloud login --apikey @api-key.json
```

### 4. Resource Groups & Permissions
```bash
# List resource groups
ibmcloud resource groups

# Tạo resource group mới (optional)
ibmcloud resource group-create banking-demo-rg

# Set target resource group
ibmcloud target -g banking-demo-rg
```

## 📦 Project Requirements

### 1. Clone Banking Demo Repository
```bash
git clone <your-banking-demo-repo>
cd banking-demo
```

### 2. Verify Project Structure
```bash
# Kiểm tra các thư mục quan trọng
ls -la services/
ls -la k8s/
ls -la frontend/
ls -la common/
```

### 3. Build Docker Images (Optional - cho local testing)
```bash
# Build tất cả services
docker compose build

# Hoặc build từng service
docker build -t auth-service:latest -f services/auth-service/Dockerfile .
docker build -t account-service:latest -f services/account-service/Dockerfile .
docker build -t transfer-service:latest -f services/transfer-service/Dockerfile .
docker build -t notification-service:latest -f services/notification-service/Dockerfile .
docker build -t frontend:latest -f frontend/Dockerfile ./frontend
```

## 🌐 Network & Connectivity

### 1. Internet Access
- ✅ Cần kết nối internet để pull images từ Docker Hub
- ✅ Access IBM Cloud APIs
- ✅ Download Helm charts

### 2. Firewall Rules
- ✅ Allow outbound HTTPS (443)
- ✅ Allow Kubernetes API access (6443)
- ✅ Allow container registry access

### 3. DNS (Optional)
- ✅ Setup custom domain nếu cần
- ✅ Configure DNS records cho Ingress/Routes

## 💾 Storage Requirements

### Minimum Storage
- **PostgreSQL**: 1Gi PVC
- **Redis**: Ephemeral (no PVC needed)
- **Application logs**: ~500Mi

### Recommended Storage
- **PostgreSQL**: 5Gi PVC với backup
- **Monitoring**: 10Gi cho Prometheus
- **Logs**: 5Gi cho log aggregation

## 🔒 Security Requirements

### 1. Secrets Management
```bash
# Tạo namespace
kubectl create namespace banking

# Tạo secrets
kubectl create secret generic postgres-secret \
  --from-literal=username=banking \
  --from-literal=password=<your-secure-password> \
  --from-literal=database=banking \
  -n banking

kubectl create secret generic redis-secret \
  --from-literal=password=<your-redis-password> \
  -n banking
```

### 2. TLS Certificates (Optional)
```bash
# Tạo self-signed cert cho testing
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout tls.key -out tls.crt \
  -subj "/CN=banking.local/O=banking-demo"

# Tạo TLS secret
kubectl create secret tls banking-tls \
  --cert=tls.crt --key=tls.key \
  -n banking
```

### 3. Image Pull Secrets (Nếu dùng private registry)
```bash
kubectl create secret docker-registry regcred \
  --docker-server=<your-registry> \
  --docker-username=<username> \
  --docker-password=<password> \
  --docker-email=<email> \
  -n banking
```

## 📊 Resource Requirements

### Minimum Cluster Resources
- **Nodes**: 2 worker nodes
- **CPU**: 4 vCPU total
- **Memory**: 8GB RAM total
- **Storage**: 20GB

### Recommended Cluster Resources
- **Nodes**: 3 worker nodes
- **CPU**: 8 vCPU total
- **Memory**: 16GB RAM total
- **Storage**: 50GB

### Per-Service Resources

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---------|-------------|-----------|----------------|--------------|
| Auth Service | 100m | 500m | 128Mi | 256Mi |
| Account Service | 100m | 500m | 128Mi | 256Mi |
| Transfer Service | 100m | 500m | 128Mi | 256Mi |
| Notification Service | 100m | 500m | 128Mi | 256Mi |
| Frontend | 50m | 200m | 64Mi | 128Mi |
| Kong Gateway | 100m | 500m | 256Mi | 512Mi |
| PostgreSQL | 100m | 500m | 256Mi | 512Mi |
| Redis | 50m | 200m | 64Mi | 128Mi |

## ✅ Pre-Deployment Checklist

### General
- [ ] Đã cài đặt kubectl, helm, ibmcloud CLI
- [ ] Đã có IBM Cloud account hoặc TechZone access
- [ ] Đã clone banking-demo repository
- [ ] Đã đọc README của platform muốn deploy

### IBM Technology Zone
- [ ] Đã login vào TechZone portal
- [ ] Đã reserve environment (OpenShift hoặc IKS)
- [ ] Đã có cluster credentials
- [ ] Đã test kubectl/oc connectivity

### IBM Cloud IKS
- [ ] Đã tạo IKS cluster hoặc có access
- [ ] Đã config kubectl context
- [ ] Đã setup IBM Cloud Block Storage
- [ ] Đã install Ingress Controller

### Red Hat OpenShift
- [ ] Đã tạo OpenShift cluster hoặc có access
- [ ] Đã login bằng oc CLI
- [ ] Đã tạo project/namespace
- [ ] Đã có quyền deploy applications

### Security
- [ ] Đã tạo secrets cho PostgreSQL
- [ ] Đã tạo secrets cho Redis (nếu cần)
- [ ] Đã setup TLS certificates (nếu cần)
- [ ] Đã review security policies

### Monitoring (Optional)
- [ ] Đã cài đặt Prometheus
- [ ] Đã cài đặt Grafana
- [ ] Đã setup Jaeger (nếu cần tracing)
- [ ] Đã config alerts

## 🆘 Troubleshooting

### Không connect được cluster
```bash
# Kiểm tra kubectl config
kubectl config view
kubectl config get-contexts

# Test connectivity
kubectl cluster-info
kubectl get nodes
```

### IBM Cloud CLI issues
```bash
# Re-login
ibmcloud login --sso

# Update CLI
ibmcloud update

# Install plugins
ibmcloud plugin install container-service
ibmcloud plugin install container-registry
```

### Permission denied
```bash
# Kiểm tra RBAC
kubectl auth can-i create deployments -n banking
kubectl auth can-i create services -n banking

# Get current user
kubectl config view --minify
```

## 📚 Tài Liệu Tham Khảo

- [IBM Cloud Documentation](https://cloud.ibm.com/docs)
- [IBM Technology Zone](https://techzone.ibm.com)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [OpenShift Documentation](https://docs.openshift.com/)
- [Helm Documentation](https://helm.sh/docs/)

## 🔄 Next Steps

Sau khi hoàn thành prerequisites:

1. **Cho TechZone**: Đọc [01-techzone/README.md](./01-techzone/README.md)
2. **Cho IKS**: Đọc [02-iks/README.md](./02-iks/README.md)
3. **Cho OpenShift**: Đọc [03-openshift/README.md](./03-openshift/README.md)

---

**Lưu ý:** Đây là yêu cầu chung. Mỗi platform có thể có thêm yêu cầu riêng, xem README trong thư mục tương ứng.