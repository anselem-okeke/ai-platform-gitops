# Cluster and Environment

## Purpose

This document records the current development Kubernetes environment, namespaces, endpoints, domains, identity services, monitoring components, and operational identifiers.

## Host and Repositories

Development VM:

```text
192.168.0.58
```

Repository paths:

```text
/mnt/data/ai-platform-operator
/mnt/data/ai-platform-gitops
```

## Kubernetes Cluster

Cluster:

```text
ai-platform-policy
```

Context:

```text
kind-ai-platform-policy
```

Observed Kubernetes version:

```text
v1.36.1
```

Kubernetes Service ClusterIP:

```text
10.96.0.1
```

Observed API backend:

```text
172.19.0.3:6443
```

CoreDNS:

```text
10.96.0.10
```

## Gateway

Shared development Gateway LoadBalancer:

```text
172.19.255.200
```

Envoy Gateway provides controlled HTTP(S) exposure.

## Development Domains

```text
https://auth.ai-platform.local
https://argocd.ai-platform.local
https://api.ai-platform.local
```

These are development domains, not production naming requirements.

## Vault

Endpoint:

```text
https://vault.platform.local:8200
```

Vault is the secret-management/PKI foundation. Private credentials must not be stored in Git.

## Namespaces

```text
ai-platform
ai-platform-operator-system
argocd
cosign-system
envoy-gateway-system
gateway-system
keycloak
monitoring
```

### ai-platform

Primary application/model workload namespace.

Sigstore enforcement label:

```text
policy.sigstore.dev/include=true
```

### ai-platform-operator-system

Operator namespace.

Sigstore enforcement label:

```text
policy.sigstore.dev/include=true
```

### argocd

Argo CD control plane.

Argo CD version:

```text
v3.5.1
```

Project:

```text
ai-platform
```

`argocd-server` remains `ClusterIP`.

Observed ClusterIP:

```text
10.96.128.244
```

Ports:

```text
80/TCP
443/TCP
```

### keycloak

Identity provider.

Observed version:

```text
26.7.0
```

Groups:

```text
platform-viewer
platform-deployer
platform-admin
```

OIDC clients:

```text
ai-platform-argocd
ai-platform-cli
```

CLI PKCE callback:

```text
http://127.0.0.1:18080/callback
```

### cosign-system

Supply-chain policy namespace.

Policy Controller Helm chart:

```text
0.10.6
```

Application version:

```text
0.13.1
```

Important resources:

```text
TrustRoot/github
ClusterImagePolicy/github-policy
```

Metrics service:

```text
policy-controller-webhook-metrics
```

Metrics port:

```text
9090
```

### monitoring

Contains kube-prometheus-stack, Prometheus/Grafana integrations, ServiceMonitors, PrometheusRules, and dashboard ConfigMaps.

Observed Prometheus pod:

```text
prometheus-kps-kube-prometheus-stack-prometheus-0
```

ServiceMonitor discovery:

```yaml
serviceMonitorNamespaceSelector: {}
serviceMonitorSelector: {}
```

Prometheus rule selection:

```yaml
ruleSelector:
  matchLabels:
    release: kps
```

Therefore custom rules must include:

```yaml
metadata:
  labels:
    release: kps
```

## Argo CD Applications

Key Applications:

```text
ai-platform-root
ai-platform-api
ai-platform-operator
ai-platform-gateway
ai-platform-monitoring
ai-platform-modelservices
ai-platform-policies
ai-platform-namespaces
policy-controller
trust-policies
```

Root is intentionally manual. Existing children are automated where appropriate.

## Custom Resource API

```text
apiVersion: platform.anselem.dev/v1alpha1
kind: ModelService
```

## Container Registry

Organization prefix:

```text
ghcr.io/anselem-okeke/
```

Primary images:

```text
ghcr.io/anselem-okeke/ai-platform-operator
ghcr.io/anselem-okeke/ai-platform-api
```

Runtime deployment identity:

```text
@sha256:<64-hex-digest>
```

## Admission Scope

Security enforcement covers:

- Deployment containers
- direct Pods
- init containers
- ephemeral containers

Examples:

- `nginx:latest` -> rejected by native admission
- syntactically valid fake platform digest -> rejected by Sigstore when no trusted bundle exists

## Monitoring Validation

Policy Controller scrape health:

```promql
up{namespace="cosign-system"}
```

Validated result:

```text
1
```

Important metric:

```promql
policy_controller_reconcile_count
```

Important labels include:

```text
namespace_name
reconciler
success
```

GitOps-managed resources:

```text
ServiceMonitor/monitoring/policy-controller
PrometheusRule/monitoring/policy-controller
```

## Operational Commands

Current context:

```bash
kubectl config current-context
```

Nodes:

```bash
kubectl get nodes -o wide
```

Namespaces:

```bash
kubectl get namespaces
```

Argo applications:

```bash
argocd app list
```

All pods:

```bash
kubectl get pods -A
```

## Environment Boundary

Current implementation is development-only. Future staging and production should preserve architectural principles while replacing development-specific values such as:

- kind topology
- `.local` domains
- private IPs
- test users
- local callback ports

The intended promotion model remains:

```text
Build once
Verify once
Promote the same immutable digest
```

## Related Documentation

- [000-documentation-index.md](000-documentation-index.md)
- [001-platform-overview.md](001-platform-overview.md)
- [002-architecture.md](002-architecture.md)
- [003-repository-architecture.md](003-repository-architecture.md)
