# Taste (Continuously Learned by [CommandCode][cmd])

[cmd]: https://commandcode.ai/

# python-dependency-upgrades
- When upgrading package versions, actively identify and implement new features and API improvements from the newer versions rather than only bumping versions with minimal compatibility-preserving changes. Confidence: 0.65
- Verify that bumped dependency versions are harmonious and installable together (check transitive dependency compatibility) rather than blindly bumping each package to its latest individual version. Confidence: 0.65

# instana
- In Instana agent configuration.yaml, `com.instana.plugin.kubernetes` is the legacy internal tracer, not the Kubernetes cluster sensor; the K8s cluster sensor is auto-deployed as a separate `k8sensor` pod when the agent is installed via Helm/Operator/DaemonSet. Confidence: 0.65
- When the Instana host agent runs on the host outside the Kubernetes cluster, k8s internal DNS names (`*.svc.cluster.local`) are not resolvable from the host; use the Kubernetes Service's ClusterIP or a NodePort for host agent sensor configuration instead. Confidence: 0.70
