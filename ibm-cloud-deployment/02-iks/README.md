# IBM Cloud Kubernetes Service (IKS) - Deployment Guide

## ☸️ Tổng Quan

IBM Cloud Kubernetes Service (IKS) là managed Kubernetes service trên IBM Cloud, cung cấp Kubernetes thuần với đầy đủ tính năng enterprise.

**Ưu điểm:**
- ✅ Kubernetes thuần, dễ migrate từ config hiện có
- ✅ Free tier: 1 worker node miễn phí 30 ngày
- ✅ Managed control plane (không tốn phí)
- ✅ Tích hợp sẵn với IBM Cloud services
- ✅ Auto-scaling, auto-healing
- ✅ Built-in monitoring và logging

**Chi phí:**
- Free tier: 1 worker node (2 vCPU, 4GB RAM) - 30 ngày
- Sau đó: ~$100-200/tháng cho 2-3 worker nodes

## 📋 Prerequisites

Trước khi bắt đầu:
- [ ] Đọc [PREREQUISITES.md](../PREREQUISITES.md)
- [ ] Có IBM Cloud account
- [ ] Đã cài đặt IBM Cloud CLI
- [ ] Đã cài đặt kubectl và helm
- [ ] Có payment method (credit card) - cần cho free tier

## 🚀 Quick Start

### Bước 1: Setup IBM Cloud CLI

```bash
# Install IBM Cloud CLI
curl -fsSL https://clis.cloud.ibm.com/install/linux | sh

# Login
ibmcloud login

# Hoặc login với SSO
ibmcloud login --sso

# Install Kubernetes plugin
ibmcloud plugin install container-service -r 'IBM Cloud'

# Verify
ibmcloud ks clusters
```

### Bước 2: Tạo IKS Cluster

#### Option A: Sử dụng Free Tier (Recommended cho testing)

```bash
# Set region
ibmcloud target -r us-south

# Tạo free cluster
ibmcloud ks cluster create classic \
  --name banking-demo-free \
  --flavor free \
  --workers 1

# Đợi cluster ready (15-30 phút)
ibmcloud ks cluster get --cluster banking-demo-free

# Get cluster config
ibmcloud ks cluster config --cluster banking-demo-free

# Verify
kubectl get nodes
```

#### Option B: Sử dụng Terraform (Production)

```bash
cd terraform

# Initialize Terraform
terraform init

# Review plan
terraform plan

# Apply
terraform apply

# Get cluster config
ibmcloud ks cluster config --cluster $(terraform output -raw cluster_name)
```

### Bước 3: Setup Storage Class

```bash
# IKS đã có default storage class
kubectl get storageclass

# Nếu cần, apply custom storage class
kubectl apply -f manifests/storage-class.yaml
```

### Bước 4: Deploy Banking Demo

```bash
# Run deployment script
cd scripts
./deploy-app.sh

# Hoặc deploy manually
kubectl apply -f ../../k8s/namespace.yaml
kubectl apply -f ../../k8s/secret.yaml
kubectl apply -f ../../k8s/postgres.yaml
kubectl apply -f ../../k8s/redis.yaml
kubectl apply -f ../../k8s/kong.yaml
kubectl apply -f ../../k8s/auth-service.yaml
kubectl apply -f ../../k8s/account-service.yaml
kubectl apply -f ../../k8s/transfer-service.yaml
kubectl apply -f ../../k8s/notification-service.yaml
kubectl apply -f ../../k8s/frontend.yaml
kubectl apply -f manifests/ingress-iks.yaml
```

### Bước 5: Access Application

```bash
# Get Ingress IP
kubectl get ingress -n banking

# Hoặc sử dụng NodePort (cho free cluster)
kubectl get svc -n banking

# Access application
# Free cluster: http://<worker-ip>:<nodeport>
# Paid cluster: http://<ingress-subdomain>
```

## 📁 Cấu Trúc Thư Mục

```
02-iks/
├── README.md              # File này
├── terraform/             # Infrastructure as Code
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── terraform.tfvars.example
├── manifests/             # IKS-specific manifests
│   ├── ingress-iks.yaml
│   ├── storage-class.yaml
│   └── load-balancer.yaml
└── scripts/               # Automation scripts
    ├── setup-cluster.sh
    ├── deploy-app.sh
    └── cleanup.sh
```

## 🔧 IKS-Specific Configurations

### 1. Ingress Controller

IKS có built-in Ingress Controller (ALB - Application Load Balancer):

```bash
# Enable ALB
ibmcloud ks alb ls --cluster banking-demo

# Get ALB subdomain
ibmcloud ks cluster get --cluster banking-demo | grep "Ingress Subdomain"

# Apply Ingress
kubectl apply -f manifests/ingress-iks.yaml
```

### 2. Storage

IKS hỗ trợ nhiều storage options:

```yaml
# IBM Cloud Block Storage (default)
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ibmc-block-bronze
provisioner: ibm.io/ibmc-block
parameters:
  type: "Endurance"
  iopsPerGB: "2"
```

### 3. Load Balancer

```bash
# IKS tự động provision IBM Cloud Load Balancer
# Khi tạo Service type LoadBalancer

kubectl expose deployment frontend \
  --type=LoadBalancer \
  --port=80 \
  --target-port=80 \
  -n banking
```

### 4. Monitoring

```bash
# Enable IBM Cloud Monitoring
ibmcloud ks cluster addon enable monitoring \
  --cluster banking-demo

# Access monitoring dashboard
ibmcloud ks cluster addon ls --cluster banking-demo
```

## 💰 Cost Optimization

### Free Tier Limitations
- ✅ 1 worker node only
- ✅ 2 vCPU, 4GB RAM
- ✅ 30 days free
- ❌ No load balancer
- ❌ No persistent storage
- ❌ No auto-scaling

### Tips để Tiết Kiệm Chi Phí

1. **Sử dụng Spot Instances** (cho non-production)
```bash
ibmcloud ks worker-pool create classic \
  --name spot-pool \
  --cluster banking-demo \
  --flavor b3c.4x16 \
  --size-per-zone 2 \
  --label pool=spot
```

2. **Auto-scaling**
```bash
# Enable cluster autoscaler
ibmcloud ks cluster addon enable cluster-autoscaler \
  --cluster banking-demo
```

3. **Schedule Scaling**
```bash
# Scale down ngoài giờ làm việc
# Sử dụng CronJob hoặc external scheduler
```

4. **Resource Limits**
```yaml
# Set resource limits cho tất cả pods
resources:
  requests:
    memory: "128Mi"
    cpu: "100m"
  limits:
    memory: "256Mi"
    cpu: "500m"
```

## 🔒 Security Best Practices

### 1. Network Policies
```bash
kubectl apply -f ../common/security/network-policies.yaml
```

### 2. Pod Security Policies
```bash
kubectl apply -f ../common/security/pod-security-policy.yaml
```

### 3. Secrets Management
```bash
# Sử dụng IBM Cloud Secrets Manager
ibmcloud plugin install secrets-manager

# Hoặc sử dụng Kubernetes secrets với encryption at rest
```

### 4. RBAC
```bash
# Tạo service account với limited permissions
kubectl create serviceaccount banking-app -n banking
kubectl create rolebinding banking-app-binding \
  --clusterrole=edit \
  --serviceaccount=banking:banking-app \
  -n banking
```

## 📊 Monitoring & Logging

### Setup Prometheus & Grafana
```bash
# Install kube-prometheus-stack
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace

# Access Grafana
kubectl port-forward svc/prometheus-grafana 3000:80 -n monitoring
```

### IBM Cloud Monitoring Integration
```bash
# Enable IBM Cloud Monitoring
ibmcloud ks cluster addon enable monitoring \
  --cluster banking-demo

# View logs
ibmcloud ks cluster addon ls --cluster banking-demo
```

## 🆘 Troubleshooting

### Cluster không ready
```bash
# Check cluster status
ibmcloud ks cluster get --cluster banking-demo

# Check worker nodes
ibmcloud ks workers --cluster banking-demo

# Reload worker nếu cần
ibmcloud ks worker reload --cluster banking-demo --worker <worker-id>
```

### Pods không start
```bash
# Check pod status
kubectl get pods -n banking

# Describe pod
kubectl describe pod <pod-name> -n banking

# Check logs
kubectl logs <pod-name> -n banking

# Check events
kubectl get events -n banking --sort-by='.lastTimestamp'
```

### Ingress không hoạt động
```bash
# Check ALB status
ibmcloud ks alb ls --cluster banking-demo

# Enable ALB nếu disabled
ibmcloud ks alb enable --alb <alb-id> --cluster banking-demo

# Check Ingress
kubectl get ingress -n banking
kubectl describe ingress banking-ingress -n banking
```

### Storage issues
```bash
# Check PVC
kubectl get pvc -n banking

# Check storage class
kubectl get storageclass

# Describe PVC
kubectl describe pvc postgres-pvc -n banking
```

## 🔄 Upgrade & Maintenance

### Upgrade Kubernetes Version
```bash
# Check available versions
ibmcloud ks versions

# Upgrade master
ibmcloud ks cluster master update --cluster banking-demo --version 1.28

# Upgrade workers
ibmcloud ks worker update --cluster banking-demo --worker <worker-id>
```

### Backup & Restore
```bash
# Backup using Velero
helm install velero vmware-tanzu/velero \
  --namespace velero --create-namespace

# Create backup
velero backup create banking-backup --include-namespaces banking
```

## 📚 Tài Liệu Tham Khảo

- [IKS Documentation](https://cloud.ibm.com/docs/containers)
- [IKS CLI Reference](https://cloud.ibm.com/docs/containers?topic=containers-cli-plugin-kubernetes-service-cli)
- [IKS Pricing](https://cloud.ibm.com/kubernetes/catalog/about)
- [IKS Best Practices](https://cloud.ibm.com/docs/containers?topic=containers-plan_deploy)

## 🔄 Next Steps

1. ✅ Tạo IKS cluster
2. ✅ Deploy Banking Demo
3. ✅ Setup monitoring
4. ✅ Configure CI/CD
5. ✅ Setup backup strategy
6. ✅ Document runbook

---

**Production Ready! ☸️**

*IKS là lựa chọn tốt cho production workloads với chi phí hợp lý.*