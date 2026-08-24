# AI Platform Architecture

## Purpose

This document describes the platform's control planes, trust boundaries, delivery path, reconciliation architecture, identity flow, networking, security controls, and observability.

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
   +----------------------+
   |                      |
   v                      v
GHCR                 GitOps Repository
immutable images     desired state
   |                      |
   +----------+-----------+
              |
              v
           Argo CD
              |
              v
          Kubernetes
              |
      +-------+--------+
      |                |
      v                v
AI Platform API     Go Operator
      |                |
      v                v
 Kubernetes API    Reconciled Resources
      |
      v
 ModelService
```

## Architectural Planes

### Source Plane

Repository:

```text
/mnt/data/ai-platform-operator
```

Owns source code, tests, CI, image production, security scanning, SBOM/provenance, and GHCR publishing.

### GitOps Plane

Repository:

```text
/mnt/data/ai-platform-gitops
```

Owns desired state, Argo topology, Kustomize overlays, namespaces, routing, monitoring, security policies, and environment promotion.

### Reconciliation Plane

Argo CD compares Git with cluster state.

```text
Git desired state
      |
      v
Argo comparison
   /       \
Synced   OutOfSync
           |
           v
       Reconcile
           |
           v
       Kubernetes
```

The root Application is intentionally manual. Existing child Applications are automated where appropriate.

### Platform Control Plane

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
Deployment / Service / PVC / ServiceAccount / Policies / HTTPRoute
```

### Security and Trust Plane

```text
Source PR checks
      |
      v
Container scan
      |
      v
Artifact attestations
      |
      v
GitOps validation
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

### Observability Plane

```text
Policy Controller
      |
      v
Metrics Service :9090
      |
      v
ServiceMonitor
      |
      v
Prometheus
      |
      +--> PrometheusRule
      +--> Grafana / queries
```

## End-to-End Delivery

```text
Developer
  |
  v
Source PR
  |
  +-- lint
  +-- tests
  +-- E2E
  +-- govulncheck
  +-- CodeQL
  +-- Gitleaks
  |
  v
Protected main
  |
  v
Release
  |
  +-- build operator
  +-- build API
  +-- Trivy
  +-- SBOM
  +-- GHCR
  +-- provenance/SBOM attestations
  |
  v
Immutable digests
  |
  v
GitHub App token
  |
  v
GitOps bot branch
  |
  v
Digest-only PR
  |
  v
Validation + human merge
  |
  v
Argo CD
  |
  v
Kubernetes admission
  |
  v
Deployment
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

Important behavior:

```text
clusters/dev/apps/* change
  -> root manual sync

existing child source-path change
  -> child auto-sync
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

Rendered overlays are the deployment truth. Raw bases may contain placeholders that are replaced by overlays, so image policy validation is performed on rendered output.

## Identity Flow

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
Authorized action
```

Groups:

```text
platform-viewer
platform-deployer
platform-admin
```

## Network Flow

Important endpoints:

```text
auth.ai-platform.local
argocd.ai-platform.local
api.ai-platform.local
```

Envoy Gateway provides HTTP(S) exposure. Argo CD remains a `ClusterIP`.

## Artifact Trust Flow

```text
Source commit
    |
    v
Required checks
    |
    v
Build + Trivy
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
Native registry/digest admission
    |
    v
Sigstore verification
    |
    v
Allowed workload
```

Native admission handles structural image policy. Sigstore handles artifact-trust verification.

## Monitoring Architecture

Policy Controller exposes metrics including:

```text
policy_controller_reconcile_count
policy_controller_reconcile_latency
policy_controller_client_latency
policy_controller_client_results
```

Prometheus discovers its `ServiceMonitor`.

Custom rules require:

```yaml
metadata:
  labels:
    release: kps
```

because Prometheus selects rules with:

```yaml
ruleSelector:
  matchLabels:
    release: kps
```

## Failure and Recovery

- Git drift -> Argo self-heal
- operator-managed workload drift -> operator reconciliation
- untrusted image -> admission denial
- bad GitOps PR -> validation gate
- failed release -> no GitOps update
- bad deployment -> Git revert to previous immutable digest

## Architectural Principles

1. Git is the deployment source of truth.
2. CI builds artifacts but does not directly deploy them.
3. Production identity is an immutable digest.
4. Promotion is auditable and pull-request controlled.
5. Authentication and authorization are centralized.
6. Security is defense-in-depth.
7. Trust is re-evaluated at admission.
8. Desired state is continuously reconciled.
9. Policy enforcement is observable.
10. Recovery is based on version-controlled desired state.

## Related Documentation

- [000-documentation-index.md](000-documentation-index.md)
- [001-platform-overview.md](001-platform-overview.md)
- [003-repository-architecture.md](003-repository-architecture.md)
- [004-cluster-and-environment.md](004-cluster-and-environment.md)
