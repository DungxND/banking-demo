# Chi Phí IBM Cloud - Phân Tích Chi Tiết

## 💰 Tổng Quan Chi Phí

Tài liệu này phân tích chi tiết chi phí khi triển khai Banking Demo lên các môi trường IBM Cloud.

## 🎓 IBM Technology Zone - MIỄN PHÍ 100% ⭐

### Chi Phí
```
✅ $0 - HOÀN TOÀN MIỄN PHÍ
```

### Chi Tiết
- **Không cần credit card**
- **Không bị charge bất kỳ khoản nào**
- **Không giới hạn số lần reserve**
- **Thời gian**: 2-4 tuần per reservation
- **Có thể extend** thêm 1-2 tuần
- **Tự động cleanup** sau khi hết hạn

### Yêu Cầu
- ✅ Là nhân viên IBM (có IBM ID/w3id)
- ✅ Truy cập: https://techzone.ibm.com

### Phù Hợp Cho
- ✅ Learning và training
- ✅ Demos và presentations
- ✅ POC (Proof of Concept)
- ✅ Short-term testing (< 4 tuần)

### 🎯 **ĐÂY LÀ LỰA CHỌN TỐT NHẤT CHO NHÂN VIÊN MỚI IBM!**

---

## ☸️ IBM Cloud Kubernetes Service (IKS)

### Free Tier (30 ngày đầu)

#### Chi Phí: $0
```
✅ MIỄN PHÍ trong 30 ngày:
- 1 worker node (2 vCPU, 4GB RAM)
- Control plane (managed by IBM)
- Basic networking
- Ingress Controller (ALB)
```

#### Không Bao Gồm (Phải Trả):
```
💰 CÁC KHOẢN PHÍ BỔ SUNG:
- Persistent Storage: ~$0.10/GB/tháng
- Load Balancer: ~$15/tháng (nếu dùng)
- Outbound data transfer: ~$0.09/GB
- Public IP addresses: ~$5/tháng
```

#### ⚠️ Lưu Ý Quan Trọng:
```
1. CẦN credit card để verify account
2. Không tự động charge trong 30 ngày
3. SAU 30 ngày:
   - Nếu KHÔNG xóa cluster → Bị charge
   - Nếu XÓA cluster → Không bị charge
```

### Paid Tier (Sau 30 ngày hoặc > 1 node)

#### Worker Nodes
| Flavor | vCPU | RAM | Storage | Giá/tháng |
|--------|------|-----|---------|-----------|
| b3c.4x16 | 4 | 16GB | 100GB | ~$100 |
| b3c.8x32 | 8 | 32GB | 100GB | ~$200 |
| b3c.16x64 | 16 | 64GB | 100GB | ~$400 |

#### Storage
| Type | Giá |
|------|-----|
| Block Storage (Bronze) | $0.10/GB/tháng |
| Block Storage (Silver) | $0.20/GB/tháng |
| Block Storage (Gold) | $0.35/GB/tháng |
| File Storage | $0.10-0.35/GB/tháng |

#### Networking
| Service | Giá |
|---------|-----|
| Load Balancer | $15-20/tháng |
| Public IP | $5/tháng |
| Outbound Data Transfer | $0.09/GB |

### Chi Phí Banking Demo trên IKS

#### Minimum Setup (2 nodes)
```
Worker Nodes (2x b3c.4x16):     $200/tháng
Block Storage (20GB):            $2/tháng
Load Balancer:                   $15/tháng
Public IPs (2):                  $10/tháng
Data Transfer (~10GB):           $1/tháng
─────────────────────────────────────────
TỔNG:                           ~$228/tháng
```

#### Recommended Setup (3 nodes)
```
Worker Nodes (3x b3c.4x16):     $300/tháng
Block Storage (50GB):            $5/tháng
Load Balancer:                   $15/tháng
Public IPs (3):                  $15/tháng
Data Transfer (~20GB):           $2/tháng
─────────────────────────────────────────
TỔNG:                           ~$337/tháng
```

---

## 🔴 Red Hat OpenShift on IBM Cloud

### Trial (60 ngày)
```
⚠️ Limited trial available
- Cần credit card để verify
- Limited resources
- Đủ để test nhưng không phù hợp production
```

### Production Pricing

#### Smallest Cluster
```
OpenShift License:              $150/tháng
Worker Nodes (2x b3c.4x16):     $200/tháng
Storage (20GB):                  $2/tháng
Load Balancer:                   $15/tháng
Networking:                      $10/tháng
─────────────────────────────────────────
TỔNG:                           ~$377/tháng
```

#### Recommended Cluster
```
OpenShift License:              $150/tháng
Worker Nodes (3x b3c.8x32):     $600/tháng
Storage (100GB):                 $10/tháng
Load Balancer:                   $15/tháng
Networking:                      $15/tháng
Monitoring & Logging:            $50/tháng
─────────────────────────────────────────
TỔNG:                           ~$840/tháng
```

#### Enterprise Cluster
```
OpenShift License:              $300/tháng
Worker Nodes (5x b3c.16x64):   $2000/tháng
Storage (500GB):                 $50/tháng
Load Balancers (multiple):       $50/tháng
Networking:                      $30/tháng
Monitoring & Logging:           $100/tháng
Backup & DR:                    $100/tháng
─────────────────────────────────────────
TỔNG:                          ~$2630/tháng
```

---

## 📊 So Sánh Chi Phí 3 Tháng

### Scenario 1: Learning & Demo (Nhân viên IBM)
| Tháng | TechZone | IKS Free | IKS Paid | OpenShift |
|-------|----------|----------|----------|-----------|
| Tháng 1 | $0 | $0 | $228 | $377 |
| Tháng 2 | $0 | - | $228 | $377 |
| Tháng 3 | $0 | $0 | $228 | $377 |
| **TỔNG** | **$0** | **$0** | **$684** | **$1,131** |

### Scenario 2: Production (Startup)
| Tháng | IKS (2 nodes) | IKS (3 nodes) | OpenShift |
|-------|---------------|---------------|-----------|
| Tháng 1 | $228 | $337 | $377 |
| Tháng 2 | $228 | $337 | $377 |
| Tháng 3 | $228 | $337 | $377 |
| Tháng 6 | $228 | $337 | $377 |
| Tháng 12 | $228 | $337 | $377 |
| **Năm 1** | **$2,736** | **$4,044** | **$4,524** |

---

## 💡 Chiến Lược Tiết Kiệm Chi Phí

### Giai Đoạn 1: Learning (0-2 tháng) - $0
```
✅ Dùng TechZone
   Week 1-2: Reserve OpenShift cluster
   Week 3-4: Deploy và test Banking Demo
   Week 5-6: Reserve lại, tiếp tục học
   Week 7-8: Advanced features

Chi phí: $0
```

### Giai Đoạn 2: Testing (tháng 3) - $0
```
✅ Dùng IKS Free Tier
   Day 1-7: Setup cluster
   Day 8-21: Deploy và test
   Day 22-28: Performance testing
   Day 29: XÓA cluster (quan trọng!)

Chi phí: $0
```

### Giai Đoạn 3: Production (từ tháng 4) - ~$228/tháng
```
💰 Chuyển sang IKS Paid
   - 2 worker nodes
   - Minimal storage
   - 1 Load Balancer

Chi phí: ~$228/tháng
```

### Tổng Chi Phí 6 Tháng
```
Tháng 1-2: TechZone          $0
Tháng 3: IKS Free            $0
Tháng 4-6: IKS Paid (3 tháng) $684
─────────────────────────────────
TỔNG 6 THÁNG:               $684
```

---

## ⚠️ Cảnh Báo & Lưu Ý

### Để KHÔNG Bị Charge Tiền:

#### 1. Dùng TechZone (Nhân viên IBM)
```bash
✅ Hoàn toàn miễn phí
✅ Không cần credit card
✅ Tự động cleanup sau khi hết hạn
✅ Không có hidden charges
```

#### 2. Dùng IKS Free Tier
```bash
# XÓA cluster TRƯỚC ngày 30
ibmcloud login
ibmcloud ks cluster rm --cluster banking-demo-free -f

# Verify đã xóa
ibmcloud ks clusters

# Xóa tất cả resources liên quan
ibmcloud resource service-instances
ibmcloud resource service-instance-delete <name>
```

#### 3. Set Budget Alerts
```bash
# Trong IBM Cloud Console:
1. Navigate to: Manage → Billing and usage
2. Click "Spending notifications"
3. Set alert threshold: $10
4. Add email notification
```

### Hidden Costs Cần Lưu Ý:

#### Data Transfer
```
- Inbound: FREE
- Outbound: $0.09/GB
- Giữa các zones: $0.01/GB

Ước tính Banking Demo: ~$1-2/tháng
```

#### Storage Snapshots
```
- Snapshot storage: $0.05/GB/tháng
- Nếu enable auto-backup: +$5-10/tháng
```

#### Load Balancer
```
- Basic LB: $15/tháng
- Multi-zone LB: $30/tháng
- Application LB: $50/tháng
```

---

## 🎯 Khuyến Nghị Theo Nhu Cầu

### Cho Nhân Viên Mới IBM (Learning)
```
✅ DÙNG: IBM Technology Zone
Chi phí: $0
Thời gian: 2-4 tuần (có thể extend)
Lý do: Miễn phí, đủ tính năng, không lo bị charge
```

### Cho Startup/SMB (Production)
```
✅ DÙNG: IKS (2-3 nodes)
Chi phí: $228-337/tháng
Lý do: Chi phí hợp lý, đủ tính năng, scalable
```

### Cho Enterprise (Production)
```
✅ DÙNG: OpenShift
Chi phí: $377-840/tháng
Lý do: Đầy đủ tính năng, security, compliance
```

---

## 📋 Checklist Tránh Bị Charge

### Trước Khi Bắt Đầu:
- [ ] Đọc kỹ pricing documentation
- [ ] Setup budget alerts
- [ ] Hiểu rõ free tier limitations
- [ ] Biết cách xóa resources

### Trong Quá Trình Sử Dụng:
- [ ] Monitor usage hàng ngày
- [ ] Check billing dashboard
- [ ] Xóa unused resources
- [ ] Scale down khi không dùng

### Trước Khi Hết Free Tier:
- [ ] Backup data quan trọng
- [ ] Export configurations
- [ ] XÓA cluster (nếu không cần tiếp)
- [ ] Verify không còn resources nào

### Sau Khi Xóa:
- [ ] Check billing dashboard
- [ ] Verify $0 charges
- [ ] Confirm email không có invoice

---

## 🔗 Tài Liệu Tham Khảo

- [IBM Cloud Pricing Calculator](https://cloud.ibm.com/estimator)
- [IKS Pricing](https://cloud.ibm.com/kubernetes/catalog/about)
- [OpenShift Pricing](https://cloud.ibm.com/kubernetes/catalog/about?platformType=openshift)
- [TechZone Portal](https://techzone.ibm.com)

---

## 📞 Support

### Billing Questions:
- IBM Cloud Support: https://cloud.ibm.com/unifiedsupport/supportcenter
- Phone: 1-866-325-0045 (US)

### TechZone Questions:
- Slack: #techzone-support (IBM Internal)
- Email: techzone@ibm.com

---

**Kết Luận:**

- **TechZone**: $0 - Tốt nhất cho learning
- **IKS**: $0 (30 ngày) → $228/tháng - Tốt cho production
- **OpenShift**: $377+/tháng - Tốt cho enterprise

**Khuyến nghị cho bạn:** Bắt đầu với TechZone (miễn phí) để học và demo! 🎓