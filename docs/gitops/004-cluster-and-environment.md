# Cluster and Environment

## Purpose

This document records the currently implemented development environment and provides commands for validating each key environment fact.

Values in this document are development-specific unless explicitly described as architectural invariants.

## Host / Working Paths

Development host observed during implementation:

```text
192.168.0.58
```

Source repository:

```text
/mnt/data/ai-platform-operator
```

GitOps repository:

```text
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

## Validate Cluster Context

```bash
kubectl config current-context
```

Expected:

```text
kind-ai-platform-policy
```

## Validate Nodes

```bash
kubectl get nodes -o wide
```

## Validate Kubernetes Version

```bash
kubectl version
```

Record both client and server versions.

## Kubernetes API

Observed Kubernetes Service ClusterIP:

```text
10.96.0.1
```

Observed API backend:

```text
172.19.0.3:6443
```

Validation:

```bash
kubectl cluster-info
kubectl get svc kubernetes \
  -n default \
  -o wide
```

These addresses are environment-specific.

## CoreDNS

Observed service IP:

```text
10.96.0.10
```

Validate:

```bash
kubectl get svc kube-dns \
  -n kube-system \
  -o wide
```

## Gateway

Observed development Gateway LoadBalancer address:

```text
172.19.255.200
```

Validate:

```bash
kubectl get gateway -A
kubectl get svc -A | grep -E 'gateway|envoy'
```

The exact backing Service name depends on Envoy Gateway-generated resources.

## Development Domains

```text
auth.ai-platform.local
argocd.ai-platform.local
api.ai-platform.local
```

Validate local resolution:

```bash
getent hosts auth.ai-platform.local
getent hosts argocd.ai-platform.local
getent hosts api.ai-platform.local
```

or:

```bash
nslookup argocd.ai-platform.local
```

## Keycloak

Endpoint:

```text
https://auth.ai-platform.local
```

Namespace:

```text
keycloak
```

Observed version:

```text
26.7.0
```

Realm:

```text
ai-platform
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

CLI callback:

```text
http://127.0.0.1:18080/callback
```

Validate Pods:

```bash
kubectl get pods -n keycloak
```

Endpoint:

```bash
curl -I https://auth.ai-platform.local
```

## Argo CD

Namespace:

```text
argocd
```

Version:

```text
v3.5.1
```

Project:

```text
ai-platform
```

Endpoint:

```text
https://argocd.ai-platform.local
```

Observed `argocd-server`:

```text
Type: ClusterIP
ClusterIP: 10.96.128.244
Ports: 80/TCP,443/TCP
```

Validate:

```bash
kubectl get pods -n argocd
kubectl get svc argocd-server -n argocd -o wide
argocd version
argocd app list
```

## Vault

Endpoint:

```text
https://vault.platform.local:8200
```

Role in platform:

```text
secret management
PKI
```

Connectivity:

```bash
curl -I https://vault.platform.local:8200
```

If the development CA is not installed locally, temporary troubleshooting may use `-k`, but production validation should use a trusted CA.

## Important Namespaces

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

Validate:

```bash
kubectl get namespaces
```

## AI Platform Namespace

```text
ai-platform
```

Contains:

- REST API
- model workloads
- resources reconciled from ModelService

Sigstore enforcement label:

```text
policy.sigstore.dev/include=true
```

Validate:

```bash
kubectl get namespace ai-platform \
  --show-labels
```

## Operator Namespace

```text
ai-platform-operator-system
```

Sigstore enforcement label:

```text
policy.sigstore.dev/include=true
```

Validate:

```bash
kubectl get namespace ai-platform-operator-system \
  --show-labels
```

## Sigstore / Policy Controller

Namespace:

```text
cosign-system
```

Policy Controller chart:

```text
0.10.6
```

Application version:

```text
0.13.1
```

Trust resources:

```text
TrustRoot/github
ClusterImagePolicy/github-policy
```

Metrics Service:

```text
policy-controller-webhook-metrics
```

Port:

```text
9090
```

Validate:

```bash
kubectl get pods -n cosign-system
kubectl get trustroot github
kubectl get clusterimagepolicy github-policy
kubectl get svc policy-controller-webhook-metrics \
  -n cosign-system \
  -o wide
```

## Monitoring

Namespace:

```text
monitoring
```

Observed Prometheus Pod:

```text
prometheus-kps-kube-prometheus-stack-prometheus-0
```

Observed Prometheus version:

```text
v3.13.2-distroless
```

ServiceMonitor selection:

```yaml
serviceMonitorNamespaceSelector: {}
serviceMonitorSelector: {}
```

Rule selection:

```yaml
ruleSelector:
  matchLabels:
    release: kps
```

Validate:

```bash
kubectl get prometheus \
  -n monitoring \
  -o yaml \
  | grep -A15 -B3 \
    -E 'serviceMonitorSelector|serviceMonitorNamespaceSelector|ruleSelector|ruleNamespaceSelector'
```

## Custom Resource API

```text
apiVersion: platform.anselem.dev/v1alpha1
kind: ModelService
```

Validate CRD:

```bash
kubectl get crd | grep -i modelservice
```

List resources:

```bash
kubectl get modelservices -A
```

## Container Registry

Organization path:

```text
ghcr.io/anselem-okeke/
```

Images:

```text
ghcr.io/anselem-okeke/ai-platform-operator
ghcr.io/anselem-okeke/ai-platform-api
```

Runtime references must use:

```text
@sha256:<64-hex-digest>
```

Validate:

```bash
kubectl get deployment -A \
  -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{" -> "}{.spec.template.spec.containers[*].image}{"\n"}{end}' \
  | grep 'ghcr.io/anselem-okeke/'
```

## Argo Applications

Expected important Applications:

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

Validate:

```bash
argocd app list
```

## Policy Controller Metrics

Port-forward Prometheus:

```bash
kubectl port-forward \
  -n monitoring \
  svc/kps-kube-prometheus-stack-prometheus \
  19091:9090
```

Query:

```bash
curl -fsSG \
  'http://127.0.0.1:19091/api/v1/query' \
  --data-urlencode 'query=up{namespace="cosign-system"}'
```

Validated expected Policy Controller target value:

```text
1
```

## Environment-Specific Values

Do not assume these are reusable in production:

```text
kind cluster
192.168.0.58
172.19.255.200
172.19.0.3:6443
10.96.0.10
10.96.128.244
*.ai-platform.local
127.0.0.1:18080
development test users
```

## Architectural Values That Should Remain

```text
GitOps deployment
immutable digests
centralized identity
TLS
admission enforcement
trusted attestations
external secret store
reconciliation
observability
```

## Official References

- kind: https://kind.sigs.k8s.io/
- Kubernetes cluster administration: https://kubernetes.io/docs/tasks/administer-cluster/
- Keycloak: https://www.keycloak.org/documentation
- Argo CD: https://argo-cd.readthedocs.io/en/stable/
- Vault: https://developer.hashicorp.com/vault/docs
- Prometheus Operator: https://prometheus-operator.dev/
