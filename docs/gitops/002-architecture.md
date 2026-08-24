# AI Platform Architecture

## Purpose

This document describes the full architecture, including:

- source/build plane
- GitOps plane
- Kubernetes reconciliation plane
- application control plane
- identity plane
- network/TLS plane
- software supply-chain trust plane
- observability plane

## High-Level Architecture

```text
Developer
   |
   v
Source Repository
   |
   v
GitHub Actions
   |
   +-------------------+
   |                   |
   v                   v
GHCR              GitOps Repository
digest +          desired state
attestations           |
   |                   v
   +---------------> Argo CD
                       |
                       v
                   Kubernetes
                       |
        +--------------+----------------+
        |              |                |
        v              v                v
    REST API       Go Operator      Envoy Gateway
        |              |
        v              v
 Kubernetes API   ModelService
                       |
                       v
              Reconciled Resources
```

## Plane 1: Source and Build

Repository:

```text
/mnt/data/ai-platform-operator
```

Responsibilities:

```text
source
tests
lint
security analysis
container build
Trivy
SBOM
provenance
GHCR
GitOps PR automation
```

## Plane 2: GitOps

Repository:

```text
/mnt/data/ai-platform-gitops
```

Responsibilities:

```text
Argo topology
Kustomize
namespaces
operator/API desired state
Gateway
monitoring
admission policies
Policy Controller
trust policy
environment promotion
```

## Plane 3: Argo Reconciliation

```text
Git
 |
 v
Argo comparison
 |
 +--> Synced
 |
 +--> OutOfSync
        |
        v
     reconcile
        |
        v
    Kubernetes
```

Child Applications auto-sync where appropriate.

Root topology is manual.

## Plane 4: Platform Application Control

```text
Client
 |
 v
AI Platform API
 |
 v
Kubernetes API
 |
 v
ModelService
 |
 v
Go Operator
 |
 v
Deployment / Service / PVC / identity / policies / routes
```

## Plane 5: Identity

```text
User
 |
 v
Keycloak
 |
 | OIDC groups
 v
Argo CD
 |
 | RBAC
 v
authorized action
```

Groups:

```text
platform-viewer
platform-deployer
platform-admin
```

## Plane 6: Network and TLS

```text
Client
 |
 | HTTPS
 v
Envoy Gateway
 |
 v
HTTPRoute
 |
 v
Service
 |
 v
Pod
```

Development hostnames:

```text
auth.ai-platform.local
argocd.ai-platform.local
api.ai-platform.local
```

Vault PKI is the trust foundation for platform TLS.

## Plane 7: Software Supply Chain

```text
Source PR
 |
 +--> required checks
 |
 v
Protected main
 |
 v
Build
 |
 +--> Trivy
 +--> SBOM
 +--> provenance
 |
 v
GHCR digest
 |
 v
GitOps PR
 |
 v
human merge
 |
 v
Argo
 |
 v
Native admission
 |
 v
Sigstore verification
 |
 v
Runtime
```

## Plane 8: Observability

```text
Policy Controller
   |
   v
metrics service :9090
   |
   v
ServiceMonitor
   |
   v
Prometheus
   |
   +--> alert rules
   +--> queries
   +--> Grafana
```

## GitOps Topology

```text
clusters/dev/root-application.yaml
        |
        v
ai-platform-root
        |
        v
clusters/dev/apps/
├── operator.yaml
├── api.yaml
├── gateway.yaml
├── monitoring.yaml
├── modelservices.yaml
├── policies.yaml
├── namespaces.yaml
├── policy-controller.yaml
└── trust-policies.yaml
```

## Kustomize Topology

```text
platform/
├── operator/{base,overlays/dev}
├── api/{base,overlays/dev}
├── gateway/{base,overlays/dev}
├── monitoring/{base,overlays/dev}
├── namespaces/{base,overlays/dev}
└── policies/{base,overlays/dev}

modelservices/{base,overlays/dev}
```

## Trust Flow

```text
source revision
    |
    v
required checks
    |
    v
build
    |
    v
Trivy
    |
    v
GHCR digest
    |
    v
GitHub attestations
    |
    v
GitOps digest PR
    |
    v
native image policy
    |
    v
Sigstore/GitHub trust
    |
    v
allowed Pod
```

## Native vs Sigstore Responsibilities

Native policy:

```text
approved registry
valid full sha256 digest
container-path coverage
```

Sigstore:

```text
artifact evidence and trust
```

These controls are complementary.

## Failure Handling

### Git drift

Argo self-heal.

### Operator child resource deleted

Go operator reconciles from `ModelService`.

### Invalid image

Native admission rejects.

### Structurally valid but untrusted digest

Sigstore rejects.

### Policy Controller failure

Prometheus metrics/alerts expose the issue.

### Bad deployment

Git revert restores prior digest.

## Rebuild Order

A full rebuild is documented in:

```text
042-disaster-recovery-and-rebuild.md
```

High-level order:

```text
cluster
Vault/PKI
Keycloak
Argo
AppProject
root
children
admission
Policy Controller
trust
monitoring
validation
```

## Architecture Validation Commands

### Argo

```bash
argocd app list
```

### Gateway

```bash
kubectl get gateway,httproute -A
```

### Identity

```bash
argocd account get-user-info
```

### Admission

```bash
kubectl get validatingadmissionpolicy
kubectl get validatingadmissionpolicybinding
```

### Sigstore

```bash
kubectl get trustroot github
kubectl get clusterimagepolicy github-policy
```

### Monitoring

```bash
kubectl get servicemonitor,prometheusrule \
  -n monitoring
```

## Official References

- Kubernetes architecture: https://kubernetes.io/docs/concepts/architecture/
- Argo CD: https://argo-cd.readthedocs.io/en/stable/
- Gateway API: https://gateway-api.sigs.k8s.io/
- Sigstore: https://docs.sigstore.dev/
- Prometheus Operator: https://prometheus-operator.dev/
