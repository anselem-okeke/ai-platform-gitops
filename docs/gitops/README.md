# AI Platform

A Kubernetes-native AI platform that exposes model deployment through a higher-level REST API and `ModelService` custom resource while keeping deployment, identity, GitOps, software supply-chain security, admission policy, and observability under explicit platform control.

This repository is the **GitOps source of truth** for the development environment.

---

## What This Platform Provides

The platform combines:

- Kubernetes custom resources and a Go operator
- a REST API for model deployment
- Argo CD GitOps
- Kustomize bases and overlays
- Envoy Gateway and Gateway API routing
- Keycloak OIDC authentication
- Argo CD RBAC
- Vault-backed PKI / secret-management architecture
- immutable GHCR image deployment
- GitHub Actions CI
- Trivy container scanning
- SBOM generation
- GitHub artifact attestations
- Sigstore Policy Controller
- native Kubernetes admission policies
- Prometheus / Grafana observability
- Git-based rollback and environment promotion

---

# Architecture

```text
Developer
   |
   v
Source Repository
   |
   v
Required PR Checks
   |
   +--> Lint
   +--> Tests
   +--> E2E
   +--> go vet
   +--> govulncheck
   +--> CodeQL
   +--> Gitleaks
   |
   v
Protected main
   |
   v
Release Workflow
   |
   +--> Build Operator
   +--> Build API
   +--> Trivy
   +--> SPDX SBOM
   +--> Provenance Attestation
   +--> SBOM Attestation
   |
   v
GHCR Immutable Digests
   |
   v
GitHub App
   |
   v
GitOps Pull Request
   |
   +--> Kustomize Render
   +--> kubeconform
   +--> Digest Validation
   +--> Secret Checks
   |
   v
Human Merge
   |
   v
Argo CD
   |
   v
Kubernetes Admission
   |
   +--> Approved Registry
   +--> Full SHA-256 Digest
   +--> Pod / Init / Ephemeral Policy
   +--> Sigstore Artifact Verification
   |
   v
Running Platform
   |
   v
Prometheus / Grafana / Alerts
```

---

# Repository Model

The platform intentionally separates **source code** from **deployment state**.

## Source Repository

Local path:

```text
/mnt/data/ai-platform-operator
```

Remote:

```text
git@github.com:anselem-okeke/ai-platform-operator.git
```

Responsibilities:

```text
Go operator
REST API
unit tests
E2E tests
lint
go vet
govulncheck
CodeQL
Gitleaks
container builds
Trivy
SBOM
provenance
GHCR publishing
GitOps update automation
```

## GitOps Repository

Local path:

```text
/mnt/data/ai-platform-gitops
```

Remote:

```text
https://github.com/anselem-okeke/ai-platform-gitops.git
```

Responsibilities:

```text
Argo CD topology
AppProject
Kustomize
namespaces
operator/API desired state
ModelService resources
Gateway
monitoring
admission policies
Sigstore Policy Controller
GitHub artifact trust policies
promotion
rollback
operations documentation
```

The central ownership rule is:

```text
Source repository builds artifacts.
GitOps repository decides what runs.
Argo CD reconciles approved desired state.
Kubernetes admission decides what is allowed to run.
```

---

# GitOps Repository Structure

```text
ai-platform-gitops/
├── argocd/
│   ├── bootstrap/
│   ├── projects/
│   ├── applicationsets/
│   └── exposure/
├── clusters/
│   └── dev/
│       ├── apps/
│       │   ├── kustomization.yaml
│       │   ├── operator.yaml
│       │   ├── api.yaml
│       │   ├── gateway.yaml
│       │   ├── monitoring.yaml
│       │   ├── modelservices.yaml
│       │   ├── policies.yaml
│       │   ├── namespaces.yaml
│       │   ├── policy-controller.yaml
│       │   └── trust-policies.yaml
│       └── root-application.yaml
├── platform/
│   ├── operator/
│   │   ├── base/
│   │   └── overlays/dev/
│   ├── api/
│   │   ├── base/
│   │   └── overlays/dev/
│   ├── gateway/
│   │   ├── base/
│   │   └── overlays/dev/
│   ├── monitoring/
│   │   ├── base/
│   │   └── overlays/dev/
│   ├── namespaces/
│   │   ├── base/
│   │   └── overlays/dev/
│   └── policies/
│       ├── base/
│       └── overlays/dev/
├── modelservices/
│   ├── base/
│   └── overlays/dev/
├── docs/
├── .github/workflows/
├── .gitignore
└── README.md
```

---

# Development Environment

## Kubernetes

```text
Cluster: ai-platform-policy
Context: kind-ai-platform-policy
Kubernetes: v1.36.1
```

Validate:

```bash
kubectl config current-context
kubectl get nodes -o wide
kubectl version
```

Expected context:

```text
kind-ai-platform-policy
```

## Important Namespaces

```text
ai-platform
ai-platform-operator-system
argocd
keycloak
gateway-system
envoy-gateway-system
monitoring
cosign-system
```

Validate:

```bash
kubectl get namespaces
```

## Development Endpoints

```text
https://auth.ai-platform.local
https://argocd.ai-platform.local
https://api.ai-platform.local
```

## Vault

```text
https://vault.platform.local:8200
```

## Gateway Address

Observed development address:

```text
172.19.255.200
```

Environment-specific addresses must not be assumed in staging or production.

---

# Platform API

The platform API exposes a higher-level model deployment interface.

Conceptually:

```bash
curl -X POST \
  https://api.ai-platform.local/models \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "fraud-model",
    "image": "fraud-model:v3",
    "replicas": 2
  }'
```

The platform translates model intent into:

```text
ModelService
```

which is reconciled by the Go operator.

Custom resource API:

```text
apiVersion: platform.anselem.dev/v1alpha1
kind: ModelService
```

---

# Reconciliation Model

Two reconciliation loops exist.

## Argo CD

```text
Git
 |
 v
Kubernetes desired state
```

Argo detects manual drift and restores Git-defined state.

## Go Operator

```text
ModelService
 |
 v
Deployment / Service / PVC / ServiceAccount / Policies / HTTPRoute
```

If an operator-owned child resource is deleted or drifts, the operator reconciles it.

---

# Argo CD

Implemented version:

```text
v3.5.1
```

Namespace:

```text
argocd
```

Project:

```text
ai-platform
```

The `argocd-server` Service remains:

```text
ClusterIP
```

Observed ClusterIP:

```text
10.96.128.244
```

Normal access:

```text
Browser / CLI
      |
      v
HTTPS
      |
      v
Envoy Gateway
      |
      v
HTTPRoute
      |
      v
argocd-server
```

Bootstrap port-forward:

```bash
kubectl port-forward \
  -n argocd \
  svc/argocd-server \
  8080:443
```

---

# Argo CD Root and Child Applications

Root:

```text
clusters/dev/root-application.yaml
```

Application:

```text
ai-platform-root
```

The root Application is intentionally **manual**.

Changes under:

```text
clusters/dev/apps/
```

require:

```bash
argocd app get ai-platform-root --refresh
argocd app sync ai-platform-root
argocd app wait ai-platform-root --sync --health --timeout 300
```

Changes inside an existing child Application's source path can auto-sync.

Typical child policy:

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

---

# AppProject

AppProject:

```text
ai-platform
```

Git location:

```text
argocd/projects/ai-platform.yaml
```

This resource is intentionally **bootstrap-managed**, not currently tracked by an Argo Application.

After changing it:

```bash
kubectl apply \
  --dry-run=server \
  -f argocd/projects/ai-platform.yaml
```

Then:

```bash
kubectl apply \
  -f argocd/projects/ai-platform.yaml
```

Verify:

```bash
argocd proj get ai-platform
```

---

# Identity and Authentication

Keycloak endpoint:

```text
https://auth.ai-platform.local
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

Argo CD client:

```text
ai-platform-argocd
```

CLI client:

```text
ai-platform-cli
```

CLI callback:

```text
http://127.0.0.1:18080/callback
```

PKCE:

```text
S256
```

Argo CD uses the Keycloak `groups` claim for RBAC.

Validate the current Argo identity:

```bash
argocd account get-user-info
```

---

# Container Images

Images:

```text
ghcr.io/anselem-okeke/ai-platform-operator
ghcr.io/anselem-okeke/ai-platform-api
```

Runtime deployments use immutable digests:

```text
ghcr.io/anselem-okeke/<image>@sha256:<64-hex-digest>
```

The deployment path intentionally does not depend on floating tags.

---

# Container Hardening

Validated build characteristics:

```text
Go builder: 1.26.6
CGO_ENABLED=0
-trimpath
distroless static Debian 13
non-root UID/GID 65532:65532
```

Operator binary:

```text
/manager
```

API binary:

```text
/platform-api
```

---

# Source CI

Before merge, source changes are protected by required checks including:

```text
Gitleaks
Lint
Tests
E2E
govulncheck
CodeQL
```

Local validation:

```bash
cd /mnt/data/ai-platform-operator

make lint-config
make lint
make test
go vet ./...
govulncheck ./...
```

Validated `govulncheck` state:

```text
0 reachable vulnerabilities
```

This does not mean every imported module is vulnerability-free.

---

# Release Security

The release pipeline performs:

```text
container build
Trivy HIGH/CRITICAL scan
SPDX SBOM generation
GHCR push
provenance attestation
SBOM attestation
digest capture
```

If either the operator or API build fails, the GitOps update job does not run.

---

# GitHub App GitOps Automation

A GitHub App provides short-lived cross-repository credentials.

Expected branch:

```text
automation/image-<source-sha>
```

Expected files changed:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

Expected commit / PR title:

```text
chore(dev): deploy images from <source-sha>
```

The PR is **not auto-merged**.

Human merge remains the promotion boundary.

---

# GitOps Validation

Workflow:

```text
.github/workflows/validate.yml
```

Required check:

```text
Validate GitOps Manifests
```

Validation includes:

```text
Kustomize rendering
kubeconform 0.7.0
approved GHCR validation
full SHA-256 digest validation
mutable final image rejection
secret pattern checks
git diff --check
```

Local render:

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize platform/operator/overlays/dev >/tmp/operator.yaml
kubectl kustomize platform/api/overlays/dev >/tmp/api.yaml
kubectl kustomize platform/gateway/overlays/dev >/tmp/gateway.yaml
kubectl kustomize platform/monitoring/overlays/dev >/tmp/monitoring.yaml
kubectl kustomize platform/policies/overlays/dev >/tmp/policies.yaml
kubectl kustomize modelservices/overlays/dev >/tmp/modelservices.yaml
kubectl kustomize clusters/dev/apps >/tmp/apps.yaml

git diff --check
```

---

# Admission Security

The platform uses two independent admission layers.

## Native Kubernetes Policy

Enforces:

```text
approved registry
full SHA-256 digest
```

Coverage includes:

```text
regular containers
init containers
ephemeral containers
direct Pods
```

Example denied workload:

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

## Sigstore Policy Controller

Namespace:

```text
cosign-system
```

Chart:

```text
policy-controller 0.10.6
```

Application version:

```text
0.13.1
```

Protected namespaces:

```text
ai-platform
ai-platform-operator-system
```

must include:

```text
policy.sigstore.dev/include=true
```

Trust resources:

```text
TrustRoot/github
ClusterImagePolicy/github-policy
```

A syntactically valid but untrusted digest is denied with a result such as:

```text
no valid bundles exist in registry
```

---

# Monitoring

Policy Controller metrics Service:

```text
policy-controller-webhook-metrics
```

Port:

```text
9090
```

GitOps-managed resources:

```text
ServiceMonitor/monitoring/policy-controller
PrometheusRule/monitoring/policy-controller
```

PrometheusRule requires:

```text
release=kps
```

because the Prometheus CR selects rules with that label.

Port-forward:

```bash
kubectl port-forward \
  -n monitoring \
  svc/kps-kube-prometheus-stack-prometheus \
  19091:9090
```

Validate Policy Controller scrape:

```bash
curl -fsSG \
  'http://127.0.0.1:19091/api/v1/query' \
  --data-urlencode 'query=up{namespace="cosign-system"}'
```

Expected Policy Controller target:

```text
1
```

Important alerts:

```text
PolicyControllerTargetDown
PolicyControllerReconcileFailures
PolicyControllerWebhookCertificateFailures
```

---

# Secrets

Git must not contain live secret material.

Examples prohibited from Git:

```text
Vault tokens
GitHub App private keys
passwords
JWTs
registry credentials
private keys
OIDC client secrets
```

Vault is the platform secret/PKI foundation.

GitHub Actions secrets store CI credentials.

Kubernetes `Secret` values are base64-encoded, not inherently protected merely because they are in YAML.

Both repositories are protected with Gitleaks and hardened `.gitignore` rules.

Full-history scan:

```bash
gitleaks git \
  --redact \
  --verbose \
  .
```

---

# Rollback

Rollback is Git-based.

```text
bad GitOps commit
    |
    v
git revert
    |
    v
validated PR
    |
    v
merge
    |
    v
Argo
    |
    v
previous immutable digest
```

Example:

```bash
cd /mnt/data/ai-platform-gitops

git log --oneline -- \
  platform/api/overlays/dev/kustomization.yaml

git switch -c rollback/<description>

git revert <bad-commit>
```

After merge:

```bash
argocd app wait \
  ai-platform-api \
  --sync \
  --health \
  --timeout 300
```

---

# Disaster Recovery

A full rebuild order is documented in:

```text
docs/042-disaster-recovery-and-rebuild.md
```

High-level order:

```text
1. restore repositories
2. restore Kubernetes cluster
3. restore core networking/DNS
4. restore Vault/PKI prerequisite
5. restore Keycloak
6. install Argo CD
7. apply AppProject
8. restore Argo secure access/OIDC/RBAC
9. apply root Application
10. sync child Applications
11. restore namespaces/workloads
12. restore native admission
13. restore Policy Controller
14. restore GitHub trust policy
15. restore monitoring
16. run security validation suite
```

Git restores declarative state.

Persistent application data requires a separate backup/restore strategy.

---

# Quick Health Check

```bash
kubectl config current-context
kubectl get nodes
kubectl get pods -A
argocd app list
```

Then:

```bash
kubectl get validatingadmissionpolicy
kubectl get validatingadmissionpolicybinding
kubectl get trustroot github
kubectl get clusterimagepolicy github-policy
```

Then inspect runtime images:

```bash
kubectl get deployment -A \
  -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{" -> "}{.spec.template.spec.containers[*].image}{"\n"}{end}'
```

---

# Documentation

The detailed engineering knowledge base is under:

```text
docs/
```

Start with:

- [`000-documentation-index.md`](docs/000-documentation-index.md)
- [`001-platform-overview.md`](docs/001-platform-overview.md)
- [`002-architecture.md`](docs/002-architecture.md)
- [`003-repository-architecture.md`](docs/003-repository-architecture.md)
- [`004-cluster-and-environment.md`](docs/004-cluster-and-environment.md)

Then follow the numbered sequence through:

```text
050-phase-7-completion-checklist.md
```

## Key Operational Documents

- [`040-end-to-end-delivery-workflow.md`](docs/040-end-to-end-delivery-workflow.md)
- [`041-validation-and-security-tests.md`](docs/041-validation-and-security-tests.md)
- [`042-disaster-recovery-and-rebuild.md`](docs/042-disaster-recovery-and-rebuild.md)
- [`043-troubleshooting-guide.md`](docs/043-troubleshooting-guide.md)
- [`044-operations-runbook.md`](docs/044-operations-runbook.md)
- [`045-command-reference.md`](docs/045-command-reference.md)
- [`046-security-model.md`](docs/046-security-model.md)
- [`047-design-decisions.md`](docs/047-design-decisions.md)
- [`048-known-limitations.md`](docs/048-known-limitations.md)
- [`049-future-environments-and-promotion.md`](docs/049-future-environments-and-promotion.md)
- [`050-phase-7-completion-checklist.md`](docs/050-phase-7-completion-checklist.md)

---

# Current Limitations

This development implementation does not claim completed production validation for:

```text
production Kubernetes topology
staging/prod environments
full persistent-volume disaster recovery
production Keycloak HA/DR
production Vault DR exercise
destructive whole-resource prune test
production Alertmanager routing
multi-reviewer production governance
```

See:

```text
docs/048-known-limitations.md
```

---

# Future Promotion Model

Future staging and production environments should promote the **same immutable digest** built once by CI.

```text
build digest X
    |
    v
dev
    |
    v
staging
    |
    v
production
```

Do not rebuild the same release separately for each environment.

---

# Security Model Summary

The platform follows defense in depth:

| Threat | Primary Control |
|---|---|
| Broken source | required tests/lint |
| Reachable Go vulnerability | govulncheck |
| Static-analysis issue | CodeQL |
| Secret committed | Gitleaks |
| Vulnerable container package | Trivy |
| Mutable image identity | digest pinning |
| CI action tag hijack | full SHA action pinning |
| Unknown artifact origin | provenance attestation |
| Unknown contents | SBOM |
| CI bypasses GitOps | separate repositories + PR |
| Invalid manifests | Kustomize + kubeconform |
| Unapproved registry | native admission |
| Non-digest image | native admission |
| Untrusted digest | Sigstore |
| Direct Pod bypass | Pod admission policy |
| Init-container bypass | init-container policy |
| Ephemeral-container bypass | ephemeral-container policy |
| Manual drift | Argo self-heal |
| Admission controller failure | Prometheus alerts |
| Bad release | Git rollback |

---

# Official References

- Kubernetes: https://kubernetes.io/docs/
- Kubernetes Operator Pattern: https://kubernetes.io/docs/concepts/extend-kubernetes/operator/
- Argo CD: https://argo-cd.readthedocs.io/en/stable/
- Kustomize: https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/
- Gateway API: https://gateway-api.sigs.k8s.io/
- Envoy Gateway: https://gateway.envoyproxy.io/
- Keycloak: https://www.keycloak.org/documentation
- HashiCorp Vault: https://developer.hashicorp.com/vault/docs
- GitHub Actions: https://docs.github.com/actions
- GitHub Artifact Attestations: https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations
- GitHub Container Registry: https://docs.github.com/packages/working-with-a-github-packages-registry/working-with-the-container-registry
- Sigstore: https://docs.sigstore.dev/
- Sigstore Policy Controller: https://docs.sigstore.dev/policy-controller/overview/
- Prometheus: https://prometheus.io/docs/
- Prometheus Operator: https://prometheus-operator.dev/
- Grafana: https://grafana.com/docs/grafana/latest/
- OpenGitOps: https://opengitops.dev/
- SLSA: https://slsa.dev/
