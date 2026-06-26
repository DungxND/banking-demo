variable "environment" {
  description = "Tên môi trường"
  type        = string
  default     = "vps-dev"
}

variable "server_name" {
  description = "Tên logic của VPS"
  type        = string
}

variable "public_ip" {
  description = "Địa chỉ IP public của VPS"
  type        = string
}

variable "ssh_user" {
  description = "User SSH"
  type        = string
  default     = "root"
}

variable "ssh_port" {
  description = "Cổng SSH"
  type        = number
  default     = 22
}

variable "ssh_private_key_path" {
  description = "Đường dẫn private key"
  type        = string
}

variable "domain_name" {
  description = "Domain hoặc host ingress"
  type        = string
  default     = ""
}

variable "enable_argocd" {
  description = "Có bootstrap ArgoCD hay không"
  type        = bool
  default     = true
}

variable "enable_monitoring" {
  description = "Có cài monitoring hay không"
  type        = bool
  default     = true
}

variable "enable_phase4_bootstrap" {
  description = "Có apply project/application phase 4 hay không"
  type        = bool
  default     = true
}

variable "k3s_version" {
  description = "Phiên bản K3s"
  type        = string
  default     = "v1.34.6+k3s1"
}

variable "kubeconfig_path" {
  description = "Đường dẫn kubeconfig trên server"
  type        = string
  default     = "/etc/rancher/k3s/k3s.yaml"
}

variable "repo_url" {
  description = "Repo GitHub"
  type        = string
  default     = "https://github.com/dungxnd/banking-demo.git"
}

variable "repo_branch" {
  description = "Branch cần checkout"
  type        = string
  default     = "main"
}

variable "repo_path_on_server" {
  description = "Đường dẫn clone repo trên server"
  type        = string
  default     = "/opt/banking-demo"
}

variable "argocd_app_name" {
  description = "Tên app ArgoCD"
  type        = string
  default     = "banking-demo-phase4"
}

variable "helm_chart_path" {
  description = "Path chart Helm"
  type        = string
  default     = "phase2-helm-chart/banking-demo"
}
