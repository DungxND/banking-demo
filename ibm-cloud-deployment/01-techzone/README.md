# IBM Technology Zone - Deployment Guide

## 🎓 Tổng Quan

IBM Technology Zone (TechZone) là môi trường lab/sandbox **MIỄN PHÍ** dành cho nhân viên IBM để học tập, demo và POC.

**Ưu điểm:**
- ✅ Hoàn toàn miễn phí cho nhân viên IBM
- ✅ Hỗ trợ cả OpenShift và IKS
- ✅ Dễ dàng reserve và setup
- ✅ Thời gian sử dụng: 2-4 tuần per reservation
- ✅ Lý tưởng cho learning và demo

## 📋 Prerequisites

Trước khi bắt đầu, đảm bảo bạn đã:
- [ ] Đọc [PREREQUISITES.md](../PREREQUISITES.md)
- [ ] Có IBM ID (w3id) - dành cho nhân viên IBM
- [ ] Đã cài đặt kubectl hoặc oc CLI
- [ ] Đã cài đặt helm

## 🚀 Quick Start

### Bước 1: Truy Cập TechZone
1. Mở browser và truy cập: https://techzone.ibm.com
2. Login bằng IBM ID (w3id)
3. Complete profile nếu lần đầu sử dụng

### Bước 2: Reserve Environment

#### Option A: OpenShift Cluster
```
1. Search "OpenShift" trong TechZone
2. Chọn "Red Hat OpenShift on IBM Cloud"
3. Click "Reserve"
4. Chọn:
   - Purpose: Education/Demo
   - Duration: 2 weeks (có thể extend)
   - Region: Gần nhất với bạn
5. Submit reservation
6. Đợi email confirmation (5-30 phút)
```

#### Option B: IKS Cluster
```
1. Search "Kubernetes" trong TechZone
2. Chọn "IBM Cloud Kubernetes Service"
3. Click "Reserve"
4. Chọn configuration tương tự OpenShift
5. Submit và đợi confirmation
```

### Bước 3: Access Cluster

#### Cho OpenShift:
```bash
# Lấy login command từ OpenShift console
# Copy command và chạy trong terminal
oc login --token=<your-token> --server=https://<cluster-url>:6443

# Verify
oc whoami
oc get nodes
```

#### Cho IKS:
```bash
# Login IBM Cloud
ibmcloud login --sso

# Get cluster config
ibmcloud ks cluster config --cluster <cluster-name>

# Verify
kubectl get nodes
```

### Bước 4: Deploy Banking Demo

#### Cho OpenShift:
```bash
cd openshift
./deploy.sh
```

#### Cho IKS:
```bash
cd iks
./deploy.sh
```

## 📁 Cấu Trúc Thư Mục

```
01-techzone/
├── README.md           # File này
├── openshift/          # OpenShift-specific configs
│   ├── deploy.sh
│   ├── routes.yaml
│   └── scc.yaml
└── iks/                # IKS-specific configs
    ├── deploy.sh
    └── ingress.yaml
```

## 🔧 Chi Tiết Deployment

### OpenShift Deployment
Xem chi tiết trong [openshift/README.md](./openshift/README.md)

### IKS Deployment
Xem chi tiết trong [iks/README.md](./iks/README.md)

## 📊 Resource Allocation

TechZone thường cung cấp:
- **Nodes**: 3 worker nodes
- **CPU**: 8 vCPU per node
- **Memory**: 32GB per node
- **Storage**: 100GB per node

Đủ để chạy Banking Demo với monitoring stack.

## ⏱️ Thời Gian Sử Dụng

- **Initial reservation**: 2 weeks
- **Extension**: Có thể extend thêm 1-2 weeks
- **Maximum**: Thường 4 weeks total
- **Cleanup**: Tự động xóa sau khi hết hạn

**Lưu ý:** Backup data quan trọng trước khi hết hạn!

## 💡 Best Practices

### 1. Reserve Trước
- Reserve ít nhất 1-2 ngày trước khi cần
- Peak times (Mon-Wed) có thể đợi lâu hơn

### 2. Sử Dụng Hiệu Quả
- Tắt services không dùng để tiết kiệm resources
- Scale down khi không demo
- Cleanup resources không cần thiết

### 3. Documentation
- Document setup steps của bạn
- Save kubeconfig và credentials
- Screenshot important configurations

### 4. Collaboration
- Share cluster với team members nếu cần
- Setup RBAC cho multiple users
- Use namespaces để tách workloads

## 🆘 Troubleshooting

### Không nhận được email confirmation
- Kiểm tra spam folder
- Đợi thêm 30 phút
- Contact TechZone support qua Slack

### Không connect được cluster
```bash
# OpenShift: Get new login token
# Vào OpenShift console > Copy login command

# IKS: Re-authenticate
ibmcloud login --sso
ibmcloud ks cluster config --cluster <cluster-name>
```

### Cluster hết resources
```bash
# Check resource usage
kubectl top nodes
kubectl top pods -A

# Scale down non-essential services
kubectl scale deployment <name> --replicas=0 -n <namespace>
```

### Reservation bị reject
- Thử reserve region khác
- Giảm duration xuống 1 week
- Thử vào off-peak hours (Thu-Fri)

## 📚 Tài Liệu Tham Khảo

- [TechZone Portal](https://techzone.ibm.com)
- [TechZone Documentation](https://techzone.ibm.com/help)
- [TechZone Slack Channel](https://ibm.enterprise.slack.com/archives/C01234567) (Internal)
- [OpenShift on TechZone Guide](https://techzone.ibm.com/collection/openshift-on-ibm-cloud)

## 🔄 Next Steps

1. ✅ Reserve TechZone environment
2. ✅ Access cluster
3. ✅ Deploy Banking Demo
4. ✅ Test application
5. ✅ Setup monitoring (optional)
6. ✅ Demo to team!

## 📞 Support

### TechZone Issues
- Slack: #techzone-support (IBM Internal)
- Email: techzone@ibm.com
- Portal: https://techzone.ibm.com/help

### Banking Demo Issues
- Check [Troubleshooting Guide](../docs/troubleshooting.md)
- Review logs: `kubectl logs -f <pod-name> -n banking`

---

**Happy Learning! 🎓**

*TechZone là môi trường tuyệt vời để bắt đầu với IBM Cloud và Kubernetes!*