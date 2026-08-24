# AI Platform Overview

## Purpose

The AI Platform provides a Kubernetes-native control plane for deploying and operating model workloads through a higher-level REST API and the `ModelService` custom resource.

Its goal is to reduce direct Kubernetes complexity for model/application users while preserving secure, auditable, reproducible platform operations.

## User-Facing Abstraction

Instead of manually managing:

```text
Deployment
Service
PVC
ServiceAccount
Policies
HTTPRoute
```

a platform user expresses a smaller set of model intent.

Conceptual request:

```json
{
  "name": "fraud-model",
  "image": "fraud-model:v3",
  "replicas": 2
}
```

The platform flow is:

```text
ML / Application Engineer
          |
          v
AI Platform REST API
          |
          v
ModelService
          |
          v
Go Operator
          |
          v
Kubernetes Resources
```

## Project Goals

The platform is designed to provide:

- simple model deployment interface
- Kubernetes-native reconciliation
- GitOps delivery
- centralized identity
- secure Argo access
- immutable deployments
- CI security gates
- SBOM/provenance
- admission-time artifact trust
- drift detection and repair
- monitoring and alerting
- auditable promotion
- reproducible recovery

## Major Components

### AI Platform REST API

Endpoint:

```text
https://api.ai-platform.local
```

Receives higher-level model requests.

### ModelService CRD

API:

```text
platform.anselem.dev/v1alpha1
```

Kind:

```text
ModelService
```

Represents model deployment desired state.

### Go Operator

Watches `ModelService` and reconciles lower-level Kubernetes resources.

### Argo CD

Version:

```text
v3.5.1
```

Owns GitOps reconciliation.

### Keycloak

Endpoint:

```text
https://auth.ai-platform.local
```

Realm:

```text
ai-platform
```

Provides OIDC authentication.

### Envoy Gateway

Provides controlled HTTP(S) exposure.

### Vault

Endpoint:

```text
https://vault.platform.local:8200
```

Provides secret/PKI foundation.

### Sigstore Policy Controller

Namespace:

```text
cosign-system
```

Verifies trusted artifact evidence at admission.

### Prometheus / Grafana

Provide platform observability.

## Kubernetes Control Loop

The operator reconciles desired state continuously.

```text
ModelService
    |
    v
Go Operator
    |
    v
Deployment / Service / ...
    |
    v
drift / deletion
    |
    v
operator reconciles
```

This is different from a one-time deployment script.

## GitOps Operating Model

```text
Source repository
   |
   v
CI / release
   |
   v
GHCR immutable digest
   |
   v
GitOps PR
   |
   v
human merge
   |
   v
Argo CD
   |
   v
Kubernetes admission
   |
   v
runtime
```

CI does not normally run direct deployment commands against the target cluster.

## Source Security

Pre-merge controls include:

```text
Lint
Tests
E2E
go vet
govulncheck
CodeQL
Gitleaks
```

## Container Security

Images use:

```text
Go 1.26.6 builder
CGO_ENABLED=0
distroless static Debian 13
non-root UID/GID 65532
Trivy HIGH/CRITICAL gate
```

## Software Supply Chain

The release creates:

```text
GHCR image
immutable digest
SPDX SBOM
provenance attestation
SBOM attestation
```

## GitOps Security

GitOps PR validation checks:

```text
Kustomize render
kubeconform
approved GHCR path
full SHA-256 digest
secret patterns
git diff --check
```

## Admission Security

Native Kubernetes policies enforce:

```text
approved registry
full sha256 digest
```

Coverage includes:

```text
regular containers
init containers
ephemeral containers
direct Pods
```

Sigstore independently verifies trusted artifact evidence.

## Identity Model

Keycloak groups:

```text
platform-viewer
platform-deployer
platform-admin
```

These map into Argo CD RBAC.

## Networking

Development endpoints:

```text
https://auth.ai-platform.local
https://argocd.ai-platform.local
https://api.ai-platform.local
```

Argo `argocd-server` remains:

```text
ClusterIP
```

and is exposed through the shared Gateway architecture.

## Monitoring

Policy Controller observability includes:

```text
ServiceMonitor
PrometheusRule
controller metrics
target health
reconcile failure alert
webhook certificate failure alert
```

## Promotion Model

Current environment:

```text
dev
```

Future:

```text
staging
prod
```

Promotion principle:

```text
Build once
Verify once
Promote the same immutable digest
```

## How to Validate the Platform

### Argo

```bash
argocd app list
```

### Workloads

```bash
kubectl get pods -A
```

### Images

```bash
kubectl get deployment -A \
  -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{" -> "}{.spec.template.spec.containers[*].image}{"\n"}{end}'
```

### Admission Negative Test

```bash
kubectl run final-registry-negative \
  -n ai-platform \
  --image=nginx:latest \
  --restart=Never \
  --dry-run=server \
  -o yaml
```

Expected:

```text
Denied
```

### Sigstore Fake Digest Test

Use a syntactically valid fake digest for the approved repository.

Expected denial includes:

```text
no valid bundles exist in registry
```

## What This Platform Intentionally Avoids

- direct CI-to-cluster deployment
- floating deployment tags
- shared long-lived PATs for cross-repository automation
- routine use of Argo local admin
- plaintext secrets in Git
- unrestricted Argo AppProject wildcards
- trusting a single security gate

## Official References

- Kubernetes operator pattern: https://kubernetes.io/docs/concepts/extend-kubernetes/operator/
- Argo CD: https://argo-cd.readthedocs.io/en/stable/
- OpenGitOps: https://opengitops.dev/
- Sigstore: https://docs.sigstore.dev/
- Gateway API: https://gateway-api.sigs.k8s.io/
