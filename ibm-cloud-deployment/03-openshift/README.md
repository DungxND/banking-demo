# Red Hat OpenShift on IBM Cloud - Deployment Guide

## 🔴 Tổng Quan

Red Hat OpenShift on IBM Cloud là enterprise Kubernetes platform với nhiều tính năng built-in cho security, CI/CD, và developer experience.

**Ưu điểm:**
- ✅ Enterprise-grade platform
- ✅ Built-in CI/CD với Tekton Pipelines
- ✅ Integrated monitoring (Prometheus, Grafana)
- ✅ Service Mesh built-in
- ✅ Advanced security features
- ✅ Developer-friendly với odo CLI
- ✅ Web console mạnh mẽ

**Chi phí:**
- Trial: 60 days free (limited resources)
- Production: ~$300-500/tháng (smallest cluster)
- Enterprise: $1000+/tháng

## 📋 Prerequisites

Trước khi bắt đầu:
- [ ] Đọc [PREREQUISITES.md](../PREREQUISITES.md)
- [ ] Có IBM Cloud account
- [ ] Đã cài đặt IBM Cloud CLI
- [ ] Đã cài đặt OpenShift CLI (oc)
- [ ] Đã cài đặt kubectl và helm
- [ ] Hiểu về OpenShift concepts (Projects, Routes, SCCs)

## 🚀 Quick Start

### Bước 1: Setup OpenShift CLI

```bash
# Install OpenShift CLI
# Windows
choco install openshift-cli

# macOS
brew install openshift-cli

# Linux
wget https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest/openshift-client-linux.tar.gz
tar -xvf openshift-client-linux.tar.gz
sudo mv oc /usr/local/bin/

# Verify
oc version
```

### Bước 2: Tạo OpenShift Cluster

#### Option A: Sử dụng IBM Cloud Console (Recommended)

```
1. Login vào IBM Cloud Console
2. Navigate to: Kubernetes > Clusters > Create cluster
3. Chọn "Red Hat OpenShift"
4. Configure:
   - Cluster name: banking-demo-ocp
   - Resource group: Default
   - Location: Dallas (us-south)
   - OpenShift version: 4.14
   - Worker pool: 2 workers (4 vCPU, 16GB RAM each)
5. Click "Create"
6. Đợi 30-45 phút
```

#### Option B: Sử dụng CLI

```bash
# Login IBM Cloud
ibmcloud login

# Set target region
ibmcloud target -r us-south

# Create OpenShift cluster
ibmcloud oc cluster create vpc-gen2 \
  --name banking-demo-ocp \
  --version 4.14_openshift \
  --zone us-south-1 \
  --flavor bx2.4x16 \
  --workers 2

# Check status
ibmcloud oc cluster get --cluster banking-demo-ocp
```

### Bước 3: Access OpenShift Cluster

```bash
# Get cluster info
ibmcloud oc cluster get --cluster banking-demo-ocp

# Login to cluster
ibmcloud oc cluster config --cluster banking-demo-ocp --admin

# Verify
oc whoami
oc get nodes
oc get projects
```

### Bước 4: Create Project

```bash
# Create project (namespace)
oc new-project banking

# Verify
oc project banking
oc get project banking
```

### Bước 5: Setup Security Context Constraints (SCC)

```bash
# Apply custom SCC for banking app
oc apply -f security/scc-banking.yaml

# Add SCC to service account
oc adm policy add-scc-to-user banking-scc \
  system:serviceaccount:banking:default
```

### Bước 6: Deploy Banking Demo

```bash
# Run deployment script
cd scripts
./deploy-app.sh

# Hoặc deploy manually
oc apply -f ../../k8s/secret.yaml
oc apply -f ../../k8s/postgres.yaml
oc apply -f ../../k8s/redis.yaml
oc apply -f ../../k8s/kong.yaml
oc apply -f ../../k8s/auth-service.yaml
oc apply -f ../../k8s/account-service.yaml
oc apply -f ../../k8s/transfer-service.yaml
oc apply -f ../../k8s/notification-service.yaml
oc apply -f ../../k8s/frontend.yaml

# Apply OpenShift Routes
oc apply -f routes/frontend-route.yaml
oc apply -f routes/api-route.yaml
```

### Bước 7: Access Application

```bash
# Get Routes
oc get routes -n banking

# Access application
# Frontend: https://banking-frontend-banking.apps.<cluster-domain>
# API: https://banking-api-banking.apps.<cluster-domain>
```

## 📁 Cấu Trúc Thư Mục

```
03-openshift/
├── README.md              # File này
├── routes/                # OpenShift Routes
│   ├── frontend-route.yaml
│   ├── api-route.yaml
│   └── websocket-route.yaml
├── security/              # Security configs
│   ├── scc-banking.yaml
│   ├── network-policy.yaml
│   └── rbac.yaml
├── pipelines/             # Tekton Pipelines
│   ├── pipeline.yaml
│   ├── tasks/
│   │   ├── build-task.yaml
│   │   ├── deploy-task.yaml
│   │   └── test-task.yaml
│   └── triggers/
│       └── github-trigger.yaml
└── scripts/               # Automation scripts
    ├── setup-project.sh
    ├── deploy-app.sh
    └── setup-pipeline.sh
```

## 🔧 OpenShift-Specific Configurations

### 1. Routes vs Ingress

OpenShift sử dụng **Routes** thay vì Ingress (hoặc có thể dùng cả hai):

```yaml
# routes/frontend-route.yaml
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: banking-frontend
  namespace: banking
spec:
  to:
    kind: Service
    name: frontend
  port:
    targetPort: 80
  tls:
    termination: edge
    insecureEdgeTerminationPolicy: Redirect
```

### 2. Security Context Constraints (SCC)

OpenShift có security policies nghiêm ngặt hơn Kubernetes:

```yaml
# security/scc-banking.yaml
apiVersion: security.openshift.io/v1
kind: SecurityContextConstraints
metadata:
  name: banking-scc
allowPrivilegedContainer: false
allowHostDirVolumePlugin: false
allowHostNetwork: false
allowHostPorts: false
allowHostPID: false
allowHostIPC: false
readOnlyRootFilesystem: false
runAsUser:
  type: MustRunAsRange
seLinuxContext:
  type: MustRunAs
fsGroup:
  type: MustRunAs
supplementalGroups:
  type: RunAsAny
volumes:
  - configMap
  - downwardAPI
  - emptyDir
  - persistentVolumeClaim
  - projected
  - secret
```

### 3. ImageStreams

```bash
# Tạo ImageStream cho services
oc create imagestream auth-service -n banking
oc create imagestream account-service -n banking
oc create imagestream transfer-service -n banking
oc create imagestream notification-service -n banking

# Tag images
oc tag docker.io/your-registry/auth-service:latest auth-service:latest -n banking
```

### 4. BuildConfigs (Optional)

```yaml
# Build image trực tiếp trên OpenShift
apiVersion: build.openshift.io/v1
kind: BuildConfig
metadata:
  name: auth-service
spec:
  source:
    type: Git
    git:
      uri: https://github.com/your-repo/banking-demo
      ref: main
    contextDir: services/auth-service
  strategy:
    type: Docker
    dockerStrategy:
      dockerfilePath: Dockerfile
  output:
    to:
      kind: ImageStreamTag
      name: auth-service:latest
```

## 🔄 CI/CD với Tekton Pipelines

### Setup Tekton Pipeline

```bash
# Tekton đã được cài sẵn trong OpenShift

# Apply pipeline resources
oc apply -f pipelines/tasks/
oc apply -f pipelines/pipeline.yaml

# Create PipelineRun
oc create -f pipelines/pipelinerun.yaml

# Watch pipeline
tkn pipelinerun logs -f -n banking
```

### Pipeline Structure

```yaml
# pipelines/pipeline.yaml
apiVersion: tekton.dev/v1beta1
kind: Pipeline
metadata:
  name: banking-demo-pipeline
spec:
  params:
    - name: git-url
    - name: git-revision
    - name: image-name
  workspaces:
    - name: shared-workspace
  tasks:
    - name: fetch-repository
      taskRef:
        name: git-clone
    - name: build-image
      taskRef:
        name: buildah
      runAfter:
        - fetch-repository
    - name: deploy
      taskRef:
        name: openshift-client
      runAfter:
        - build-image
```

## 🔒 Security Best Practices

### 1. Network Policies

```bash
# Apply network policies
oc apply -f security/network-policy.yaml

# Verify
oc get networkpolicy -n banking
```

### 2. RBAC

```bash
# Create service account
oc create serviceaccount banking-app -n banking

# Grant permissions
oc adm policy add-role-to-user edit \
  system:serviceaccount:banking:banking-app \
  -n banking
```

### 3. Secrets Management

```bash
# Sử dụng OpenShift Secrets
oc create secret generic postgres-secret \
  --from-literal=username=banking \
  --from-literal=password=<secure-password> \
  -n banking

# Hoặc sử dụng External Secrets Operator
oc apply -f ../common/secrets/external-secret.yaml
```

### 4. Pod Security

```yaml
# Set security context trong deployment
securityContext:
  runAsNonRoot: true
  seccompProfile:
    type: RuntimeDefault
  capabilities:
    drop:
      - ALL
```

## 📊 Monitoring & Observability

### Built-in Monitoring

OpenShift có monitoring stack built-in:

```bash
# Access Prometheus
oc get route prometheus-k8s -n openshift-monitoring

# Access Grafana
oc get route grafana -n openshift-monitoring

# Access AlertManager
oc get route alertmanager-main -n openshift-monitoring
```

### Custom Metrics

```bash
# Enable user workload monitoring
oc apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: cluster-monitoring-config
  namespace: openshift-monitoring
data:
  config.yaml: |
    enableUserWorkload: true
EOF

# Create ServiceMonitor
oc apply -f ../common/monitoring/servicemonitor.yaml
```

### Logging

```bash
# Install OpenShift Logging Operator
oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: cluster-logging
  namespace: openshift-logging
spec:
  channel: stable
  name: cluster-logging
  source: redhat-operators
  sourceNamespace: openshift-marketplace
EOF
```

## 🚀 Advanced Features

### 1. Service Mesh

```bash
# Install Red Hat OpenShift Service Mesh
oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: servicemeshoperator
  namespace: openshift-operators
spec:
  channel: stable
  name: servicemeshoperator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
EOF

# Create ServiceMeshControlPlane
oc apply -f service-mesh/control-plane.yaml
```

### 2. GitOps với ArgoCD

```bash
# Install OpenShift GitOps Operator
oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: openshift-gitops-operator
  namespace: openshift-operators
spec:
  channel: stable
  name: openshift-gitops-operator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
EOF

# Access ArgoCD
oc get route openshift-gitops-server -n openshift-gitops
```

### 3. Serverless với Knative

```bash
# Install OpenShift Serverless
oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: serverless-operator
  namespace: openshift-serverless
spec:
  channel: stable
  name: serverless-operator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
EOF
```

## 💰 Cost Optimization

### 1. Auto-scaling

```bash
# Enable cluster autoscaler
ibmcloud oc cluster autoscale set \
  --cluster banking-demo-ocp \
  --min-size 2 \
  --max-size 5
```

### 2. Resource Quotas

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: banking-quota
  namespace: banking
spec:
  hard:
    requests.cpu: "4"
    requests.memory: 8Gi
    limits.cpu: "8"
    limits.memory: 16Gi
```

### 3. Limit Ranges

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: banking-limits
  namespace: banking
spec:
  limits:
    - max:
        cpu: "2"
        memory: 2Gi
      min:
        cpu: 100m
        memory: 128Mi
      type: Container
```

## 🆘 Troubleshooting

### SCC Issues

```bash
# Check SCC
oc get scc

# Check which SCC is used
oc describe pod <pod-name> -n banking | grep scc

# Debug SCC
oc adm policy who-can use scc banking-scc
```

### Route Issues

```bash
# Check routes
oc get routes -n banking

# Describe route
oc describe route banking-frontend -n banking

# Check router logs
oc logs -f deployment/router-default -n openshift-ingress
```

### Image Pull Issues

```bash
# Check image pull secrets
oc get secrets -n banking

# Create image pull secret
oc create secret docker-registry regcred \
  --docker-server=<registry> \
  --docker-username=<username> \
  --docker-password=<password> \
  -n banking

# Link to service account
oc secrets link default regcred --for=pull -n banking
```

## 📚 Tài Liệu Tham Khảo

- [OpenShift Documentation](https://docs.openshift.com/)
- [OpenShift on IBM Cloud](https://cloud.ibm.com/docs/openshift)
- [Tekton Documentation](https://tekton.dev/docs/)
- [OpenShift CLI Reference](https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html)

## 🔄 Next Steps

1. ✅ Tạo OpenShift cluster
2. ✅ Deploy Banking Demo
3. ✅ Setup Tekton Pipeline
4. ✅ Configure monitoring
5. ✅ Setup GitOps
6. ✅ Implement Service Mesh (optional)

---

**Enterprise Ready! 🔴**

*OpenShift là lựa chọn tốt nhất cho enterprise workloads với đầy đủ tính năng.*