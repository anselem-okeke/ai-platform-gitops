# Design Decisions

## Purpose

This document records the **major architecture and implementation decisions that define the current AI Platform**, together with the practical reasons for each decision and the operational consequences engineers must preserve.

It is not intended as a generic architecture essay.

Each decision answers four questions:

```text
What was chosen?
What alternative was rejected or deferred?
Why was the decision made?
What must engineers preserve when changing the platform?
```

The current platform is built around these principles:

```text
Git is the deployment source of truth
source CI does not deploy directly
release artifacts are immutable by digest
GitOps promotion is human-authorized
admission is fail-closed
runtime trust is verified independently
secrets do not live in Git
platform access uses OIDC + RBAC
security controls are observable
rollback uses Git, not mutable tags
```

---

# 1. Decision — Use GitOps as the Deployment Model

## Chosen

```text
Source repository
    |
    v
Release workflow
    |
    v
GitOps pull request
    |
    v
Human merge
    |
    v
Argo CD
    |
    v
Kubernetes
```

## Rejected

```text
source CI directly running kubectl apply
source CI directly changing live image
source CI directly invoking Argo sync
```

## Why

This separates:

```text
artifact creation
```

from:

```text
deployment authorization
```

and creates an auditable deployment source of truth.

## Operational consequence

Engineers must not normalize:

```bash
kubectl set image
kubectl patch
kubectl edit
```

as the standard deployment method.

---

# 2. Decision — Use Argo CD Instead of Flux

## Chosen

```text
Argo CD
```

## Why

For this project, Argo CD was selected because it fits the platform's desired operating model:

```text
visible Application model
AppProject isolation
manual root control
automated child reconciliation
OIDC integration
RBAC integration
strong UI/CLI operational workflow
Application health and drift visibility
```

Flux was considered a valid alternative, but the project already implemented and validated the Argo model.

## Operational consequence

Do not introduce Flux alongside Argo for the same resources.

The platform should have one GitOps reconciliation authority per resource set.

---

# 3. Decision — Keep the Root Application Manual

## Chosen

```text
ai-platform-root
manual sync
```

## Child Applications

```text
automated sync
selfHeal
prune
```

## Why

The root Application controls high-impact topology:

```text
child Applications
repositories
destinations
Helm sources
namespace topology
security components
```

Automatic root reconciliation would increase the blast radius of an accidental Git change.

## Operational consequence

Before syncing root:

```bash
argocd app diff \
  ai-platform-root
```

Review all additions, removals, repository changes, and destination changes.

---

# 4. Decision — Use App-of-Apps

## Chosen

```text
clusters/dev/root-application.yaml
        |
        v
clusters/dev/apps/
```

Child Applications include:

```text
operator
api
gateway
monitoring
modelservices
policies
namespaces
policy-controller
trust-policies
```

## Why

This gives explicit application boundaries and allows:

```text
different health states
different reconciliation behavior
isolated troubleshooting
isolated sync
clear ownership
```

## Operational consequence

Do not collapse the entire platform into one monolithic Argo Application unless the lifecycle model is deliberately redesigned.

---

# 5. Decision — Keep AppProject Bootstrap-Managed

## Chosen

File:

```text
argocd/projects/ai-platform.yaml
```

Apply manually:

```bash
kubectl apply \
  --dry-run=server \
  -f argocd/projects/ai-platform.yaml

kubectl apply \
  -f argocd/projects/ai-platform.yaml
```

## Why

The AppProject defines Argo's own deployment authority:

```text
repositories
destinations
cluster resource kinds
```

The platform intentionally avoids making Argo fully self-authorize its own permissions.

## Operational consequence

AppProject changes require deliberate review and manual application.

---

# 6. Decision — Use Exact AppProject Permissions

## Chosen

Explicit allowlisting of:

```text
GitOps repository
Helm OCI repositories
specific namespaces
specific cluster-scoped resource kinds
```

## Rejected

```yaml
group: '*'
kind: '*'
```

as the normal model.

## Why

A broad AppProject would allow compromised or mistaken Git state to request more authority than required.

## Operational consequence

When adding a new component, add only the exact required:

```text
repo
namespace
API group
kind
```

---

# 7. Decision — Keep Argo Server as ClusterIP

## Chosen

```text
argocd-server = ClusterIP
```

Access path:

```text
User
  |
  v
Envoy Gateway
  |
  v
HTTPS
  |
  v
Argo CD
```

## Rejected

```text
direct public LoadBalancer exposure
```

## Why

The Gateway provides the intended TLS and routing boundary.

Direct public Service exposure is unnecessary.

## Operational consequence

Do not change Argo service type for convenience.

Use port-forward only for bootstrap or break-glass:

```bash
kubectl port-forward \
  -n argocd \
  svc/argocd-server \
  8080:443
```

---

# 8. Decision — Use Keycloak as the Identity Provider

## Chosen

Validated version:

```text
Keycloak 26.7.0
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

## Why

The platform needed centralized identity that could map directly into Argo RBAC and later be reused by platform APIs.

## Operational consequence

Routine access should use OIDC rather than local Argo accounts.

---

# 9. Decision — Use Authorization Code + PKCE

## Chosen

Argo OIDC client:

```text
ai-platform-argocd
```

CLI client:

```text
ai-platform-cli
```

Properties:

```text
standard flow enabled
direct access grants disabled
PKCE S256
```

## Rejected

```text
Resource Owner Password / direct grant
```

## Why

PKCE avoids requiring reusable password-based client flows and fits browser/CLI login.

## Operational consequence

Do not enable password grants just to simplify automation.

---

# 10. Decision — Disable Routine Local Argo Admin

## Chosen

```text
OIDC for normal access
break-glass local access only
```

## Why

Persistent local admin access creates a separate identity path that can bypass centralized authorization.

## Operational consequence

After recovery/bootstrap:

```text
restore OIDC
rotate emergency credential
disable routine local admin usage
```

---

# 11. Decision — Use Envoy Gateway and Gateway API

## Chosen

```text
Envoy Gateway
Gateway API
HTTPRoute
TLS
```

Validated Gateway LB:

```text
172.19.255.200
```

## Why

This provides a common routing layer for:

```text
Keycloak
Argo CD
AI Platform API
```

and creates a consistent future path for model-serving endpoints.

## Operational consequence

New externally reachable services should integrate through Gateway API rather than arbitrary service exposure.

---

# 12. Decision — Use Digest-Pinned Images

## Chosen

```text
ghcr.io/...@sha256:<64hex>
```

## Rejected

Final deployment using:

```text
latest
dev
main
v1
newTag
```

## Why

Tags are mutable.

Digests identify exact image content.

## Operational consequence

All promotion, rollback, and runtime verification must use digests.

---

# 13. Decision — Allow Placeholder Tags in Bases

## Chosen

Base manifests may contain placeholders such as:

```text
controller:latest
ai-platform-api:dev
```

## Why

The security boundary is the fully rendered overlay, not the reusable base.

Kustomize overlays replace placeholders with:

```text
approved GHCR repository
immutable digest
```

## Operational consequence

Validation must inspect rendered state.

Do not reject the raw base simply because it contains a placeholder if the final overlay safely replaces it.

---

# 14. Decision — Use GHCR for First-Party Images

## Chosen

```text
ghcr.io/anselem-okeke/ai-platform-operator
ghcr.io/anselem-okeke/ai-platform-api
```

## Why

GHCR integrates naturally with:

```text
GitHub Actions
artifact attestations
GitHub App workflow
Sigstore/GitHub trust policy
```

## Operational consequence

New first-party images should use a similarly narrow and explicit repository trust model.

---

# 15. Decision — Harden Runtime Images with Distroless

## Chosen

Builder:

```text
golang:1.26.6
```

Runtime:

```text
gcr.io/distroless/static-debian13:nonroot
```

User:

```text
65532
```

Build flags include:

```text
CGO_ENABLED=0
-trimpath
-ldflags
```

## Why

The runtime image should contain only what is needed to execute the binary.

## Operational consequence

Do not add shell/package-manager tooling to production images merely for debugging convenience.

---

# 16. Decision — Use Trivy as a Blocking Release Gate

## Chosen

```text
HIGH,CRITICAL
ignore-unfixed
exit code 1
```

## Why

Image scanning must affect release outcome.

## Operational consequence

A Trivy failure must prevent promotion.

Do not change the workflow so scanning becomes informational.

---

# 17. Decision — Use govulncheck for Reachable Go Vulnerabilities

## Chosen

Validated CLI:

```text
govulncheck v1.7.0
```

## Why

Reachability-aware analysis gives better signal than simply listing every vulnerable imported module.

## Important interpretation

Validated state:

```text
0 reachable vulnerabilities
```

Do not document:

```text
0 vulnerabilities in dependency graph
```

unless independently proven.

---

# 18. Decision — Use CodeQL on Pull Requests

## Chosen

CodeQL required by branch protection.

Pinned action:

```text
f205ea1c3313d32999d8d6a48b4f6530d4437b38
```

## Why

Code scanning must happen before source merge, not only after release.

## Operational consequence

Do not remove CodeQL from required checks.

---

# 19. Decision — Use Gitleaks as an Enforcement Gate

## Chosen

```text
Gitleaks required check
history/current scanning
```

## Why

Secret detection only helps if merge is blocked.

## Operational consequence

If a real secret is found:

```text
revoke first
clean Git second
```

---

# 20. Decision — Keep Secrets Out of Git

## Chosen

Vault:

```text
https://vault.platform.local:8200
```

as source of truth.

Git stores:

```text
secret references
```

not values.

## Rejected

```text
committed Kubernetes Secret YAML with real values
base64 as fake encryption
plaintext `.env`
```

## Operational consequence

Recovery and runtime provisioning must restore secret values outside Git.

---

# 21. Decision — Do Not Claim External Secrets or Vault CSI Yet

## Chosen

Current documentation states:

```text
Vault is source of truth
runtime Secrets may be provisioned outside Git
```

## Deferred

```text
External Secrets Operator
Vault CSI
Secrets Store CSI
```

## Why

These have not been verified as installed.

## Operational consequence

Do not add `ExternalSecret` or CSI manifests to documentation as if they are current implementation.

---

# 22. Decision — Use GitHub App for Cross-Repository Promotion

## Chosen

Bot:

```text
ai-platform-gitops-bot[bot]
```

Action:

```text
actions/create-github-app-token
```

Pinned SHA:

```text
bcd2ba49218906704ab6c1aa796996da409d3eb1
```

## Rejected

```text
developer PAT
long-lived static cross-repo token
```

## Why

GitHub App authentication offers:

```text
short-lived installation token
narrow repository scope
explicit permissions
machine identity
```

---

# 23. Decision — Limit GitHub App Permissions

## Chosen

```text
Contents: Read & write
Pull requests: Read & write
Metadata: Read
```

Installed only on:

```text
ai-platform-gitops
```

## Why

The bot only needs to create a branch and PR.

## Operational consequence

Do not grant repository administration or organization-wide access without a real requirement.

---

# 24. Decision — Promotion Changes Exactly Two Files

## Chosen

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

## Why

This limits the release workflow's authority.

It should promote images, not rewrite platform topology or security policy.

## Operational consequence

If additional files change during a normal release, fail the promotion and investigate.

---

# 25. Decision — Human Merge for Promotion

## Chosen

```text
bot opens PR
human merges
```

## Rejected

```text
auto-merge after release
```

## Why

Human merge is the approval point between:

```text
artifact creation
```

and:

```text
deployment authorization
```

## Operational consequence

Do not silently add automerge to the promotion workflow.

---

# 26. Decision — Validate Final Rendered GitOps State

## Chosen

GitOps CI renders:

```text
operator
API
gateway
monitoring
policies
modelservices
clusters/dev/apps
```

and validates the result.

## Why

Kustomize bases can intentionally contain placeholders.

The final render is what Argo deploys.

## Operational consequence

Security checks should target rendered output wherever possible.

---

# 27. Decision — Use kubeconform 0.7.0 with Checksum Verification

## Chosen

```text
kubeconform 0.7.0
strict
summary
ignore missing schemas
checksum verified
```

## Why

GitOps validation tooling itself is part of the supply chain.

## Operational consequence

Future upgrades should preserve version pinning and checksum verification.

---

# 28. Decision — Use Native Admission for Structural Image Policy

## Chosen

```text
ValidatingAdmissionPolicy
ValidatingAdmissionPolicyBinding
```

Intended behavior:

```text
failurePolicy: Fail
validationActions: Deny
```

## Why

Kubernetes-native CEL is suitable for structural image restrictions.

## Responsibilities

```text
approved repository
digest syntax
containers
initContainers
ephemeralContainers
direct Pods
workload templates where implemented
```

---

# 29. Decision — Use Sigstore for Artifact Trust

## Chosen

Policy Controller:

```text
chart 0.10.6
app 0.13.1
namespace cosign-system
```

Trust policies:

```text
v0.7.0
```

TrustRoot:

```text
github
```

ClusterImagePolicy:

```text
github-policy
```

## Why

Native admission can validate structure but cannot prove provenance.

Sigstore verifies trusted evidence associated with the digest.

---

# 30. Decision — Keep Native Policy and Sigstore Separate

## Chosen

```text
Native admission:
Is this reference structurally allowed?

Sigstore:
Is this digest trusted?
```

## Why

These are different security questions.

Combining them conceptually makes troubleshooting and testing harder.

## Operational consequence

Use different negative tests:

```text
nginx:latest
```

for structural denial.

Use:

```text
approved repo + fake full digest
```

for trust denial.

---

# 31. Decision — Cover Init Containers

## Chosen

Security policy includes:

```text
spec.initContainers[]
```

## Why

An init container executes before the primary workload and can modify state.

Ignoring it would create a real bypass.

## Operational consequence

Keep init-container negative tests after policy changes.

---

# 32. Decision — Cover Sidecars / All Containers

## Chosen

All regular containers are evaluated.

## Why

A trusted primary image does not make an arbitrary sidecar trusted.

## Operational consequence

Policy expressions should use all-container evaluation rather than validating only one element.

---

# 33. Decision — Cover Ephemeral Containers

## Chosen

Admission stack is expected to deny untrusted ephemeral images.

Empirical validation:

```text
nginx:latest ephemeral image denied
```

## Why

`kubectl debug` must not bypass the runtime image trust model.

## Operational consequence

Preserve periodic ephemeral-container testing.

---

# 34. Decision — Protect Direct Pod Creation

## Chosen

Direct Pod creation is part of the image-policy threat model.

## Why

A user should not bypass workload-template policy by creating a Pod directly.

---

# 35. Decision — Protect Only Intended Namespaces

## Chosen

Validated protected namespaces:

```text
ai-platform
ai-platform-operator-system
```

Label:

```text
policy.sigstore.dev/include=true
```

## Why

The first-party image allowlist is not necessarily appropriate for:

```text
kube-system
argocd
monitoring
cosign-system
```

## Operational consequence

Namespace scope must remain explicit.

---

# 36. Decision — Narrow Sigstore Trust Scope

## Chosen

```yaml
images:
  - "ghcr.io/anselem-okeke/ai-platform-operator**"
  - "ghcr.io/anselem-okeke/ai-platform-api**"
```

## Rejected

```text
trust every image under organization
trust arbitrary public registries
```

## Why

Trust should match the actual first-party release surface.

---

# 37. Decision — Use GitHub Artifact Attestations

## Chosen

Validated action:

```text
actions/attest
```

Pinned SHA:

```text
508db95dd578ae2727ebd6217d5ba78e4fbda05d
```

Evidence:

```text
provenance
SBOM attestation
```

## Why

This provides a verifiable relationship between the released image digest and the GitHub build workflow.

---

# 38. Decision — Generate SPDX JSON SBOM

## Chosen

```text
SPDX JSON
```

Generated using Anchore tooling.

## Why

The platform needs a machine-readable artifact inventory that can be attached to the exact image digest.

---

# 39. Decision — Keep Rollback Git-Driven

## Chosen

```text
Git revert
-> GitOps PR
-> merge
-> Argo
```

## Rejected

```text
kubectl set image
rebuilding old version
using an old mutable tag
```

## Why

Rollback must preserve:

```text
traceability
digest identity
Git review
admission trust
```

---

# 40. Decision — Use Argo Self-Heal for Child Drift

## Chosen

Child Applications:

```text
automated
selfHeal
prune
```

## Why

Manual drift should not become lasting state.

## Operational consequence

If live state is intentionally changed during incident response, update Git before allowing self-heal to erase the change.

---

# 41. Decision — Be Cautious with Prune

## Chosen

Prune enabled for child Apps.

## Validation boundary

The project has validated:

```text
drift reconciliation
Git rollback
```

but has not exhaustively validated:

```text
whole-resource destructive prune scenarios
```

## Operational consequence

Do not claim destructive prune is fully battle-tested.

Review high-impact removals before merge.

---

# 42. Decision — Use Narrow `ignoreDifferences`

## Chosen

Only known controller-managed fields are ignored.

Known example:

```yaml
- key: webhooks.knative.dev/exclude
  operator: DoesNotExist
```

and:

```text
RespectIgnoreDifferences=true
```

## Rejected

Ignoring entire webhook resources.

## Why

Broad ignores can hide genuine security drift.

---

# 43. Decision — Keep Policy Controller in `cosign-system`

## Chosen

```text
namespace = cosign-system
release = policy-controller
```

## Why

A prior attempt to install another release elsewhere created CRD ownership conflict.

The standard release already owned cluster-scoped CRDs.

## Operational consequence

Do not install a second Policy Controller release in:

```text
artifact-attestations
```

or another namespace without redesigning ownership.

---

# 44. Decision — Monitor Policy Controller

## Chosen

Metrics service:

```text
policy-controller-webhook-metrics
```

Port:

```text
9090
```

ServiceMonitor:

```text
platform/monitoring/base/policy-controller-servicemonitor.yaml
```

PrometheusRule:

```text
platform/monitoring/base/policy-controller-prometheusrule.yaml
```

## Why

Admission security is operational infrastructure.

If it fails silently, the platform may become unavailable or less trustworthy.

---

# 45. Decision — Use `release: kps` on PrometheusRule

## Chosen

```yaml
metadata:
  labels:
    release: kps
```

## Why

The Prometheus selector required this label.

A previous mismatch caused the rule not to be selected.

## Operational consequence

Do not remove this label without checking current Prometheus selectors.

---

# 46. Decision — Alert on Target Down

## Chosen

```promql
up{
  namespace="cosign-system",
  service="policy-controller-webhook-metrics"
} == 0
```

For:

```text
5m
```

Severity:

```text
critical
```

## Why

Loss of the security-controller metrics target is operationally significant.

---

# 47. Decision — Alert on Reconcile Failures

## Chosen

```promql
sum(
  increase(
    policy_controller_reconcile_count{
      success="false"
    }[10m]
  )
) > 5
```

For:

```text
5m
```

Severity:

```text
warning
```

## Why

Sustained reconciliation failure is more meaningful than a single transient error.

---

# 48. Decision — Alert on Webhook Certificate Failures

## Chosen

```promql
increase(
  policy_controller_reconcile_count{
    reconciler="WebhookCertificates",
    success="false"
  }[10m]
) > 0
```

For:

```text
5m
```

Severity:

```text
critical
```

## Why

Webhook certificate failure directly affects admission availability and trust enforcement.

---

# 49. Decision — Do Not Claim Alert Firing Was Fully Tested

## Current validation

Validated:

```text
Prometheus target up=1
policy_controller_reconcile_count present
PrometheusRule loaded
```

Not empirically validated:

```text
all alerts forced to fire
all Alertmanager routes tested
all notifications delivered
```

## Why

Documentation must distinguish configured state from tested behavior.

---

# 50. Decision — Use Git as Runtime Desired-State Authority

## Chosen

When live state differs:

```text
Git wins
```

unless the incident process explicitly decides that the live emergency state should first be captured in Git.

## Why

Otherwise Argo would continuously fight manual changes and the platform would lose reproducibility.

---

# 51. Decision — Do Not Store Generated Secret Material in Git

## Chosen

Runtime Secrets may be created from secure external values.

Representative:

```bash
kubectl create secret generic <SECRET_NAME> \
  -n <NAMESPACE> \
  --from-literal=<KEY>="$VALUE" \
  --dry-run=client \
  -o yaml \
  | kubectl apply -f -
```

## Why

The generated Kubernetes Secret object is runtime state, not source-controlled plaintext secret material.

---

# 52. Decision — Use `.gitignore` as Defense in Depth

Validated GitOps patterns:

```text
.local/
*.jwt
*.key
*.pem
.env
secret YAML patterns
```

No blanket:

```text
*.crt
```

## Why

Public certificate files are not automatically sensitive.

## Operational consequence

Do not confuse `.gitignore` with secret scanning.

Gitleaks remains necessary.

---

# 53. Decision — Use Security Controls as Blocking Gates

The platform explicitly rejects the anti-pattern:

```text
security workflow reports failure
release continues anyway
```

Blocking points include:

```text
source merge
release promotion
GitOps merge
Kubernetes admission
```

This is a core design principle.

---

# 54. Decision — Preserve Traceability Across Repositories

The release chain includes:

```text
SOURCE_SHA
release run
operator digest
API digest
automation/image-SOURCE_SHA
GitOps PR
GitOps merge SHA
Argo revision
live digest
```

## Why

A running workload should be traceable back to the source commit that produced it.

---

# 55. Decision — Use Human Review Between Source and Deployment

There are two separate human-controlled merge boundaries:

```text
source PR merge
GitOps promotion PR merge
```

## Why

These represent different decisions:

```text
Is the code acceptable?
Should this built artifact be deployed?
```

Combining them would remove an important control boundary.

---

# 56. Decision — Keep Source and GitOps Repositories Separate

## Chosen

Source:

```text
ai-platform-operator
```

GitOps:

```text
ai-platform-gitops
```

## Why

This separates:

```text
software development history
deployment desired-state history
```

and makes promotion explicit.

## Operational consequence

Cross-repository automation must remain narrowly scoped.

---

# 57. Decision — Keep Promotion Bot Non-Administrative

The promotion bot should not:

```text
modify rulesets
change repository settings
merge its own PR
alter arbitrary platform files
```

Its purpose is:

```text
write image digests
open PR
```

---

# 58. Decision — Use Server-Side Dry-Run Before High-Risk Changes

For cluster-aware validation:

```bash
kubectl apply \
  --dry-run=server \
  -f <FILE>
```

## Why

This tests:

```text
API compatibility
CRD availability
admission behavior
schema acceptance
```

without persisting the change.

---

# 59. Decision — Use Architecture-First, Explicit Boundaries

The platform separates responsibilities between:

```text
API
ModelService CR
operator
GitOps
admission
identity
monitoring
```

## Why

Avoid turning one component into a giant integration layer.

This becomes especially important in Phase 8.

---

# 60. Decision — Operator Reconciles Kubernetes State

The Go operator is responsible for:

```text
watching ModelService
reconciling desired state
updating status
```

It should not become the place where every external business integration is implemented.

---

# 61. Decision — API Owns Higher-Level Deployment Intent

For future model-registry integration, the preferred direction is:

```text
API resolves approved model/version
    |
    v
ModelService contains resolved reference
    |
    v
operator reconciles KServe
```

rather than:

```text
operator directly becomes MLflow client + policy engine + deployment engine
```

This preserves separation of concerns.

---

# 62. Decision — Use Real CPU Model in Phase 8

Deferred implementation decision already agreed:

```text
use a real CPU inference model
```

Initial KServe validation should use a known simple model, such as the official sklearn/Iris example, before integrating full platform flow.

## Why

This validates actual inference behavior without introducing GPU complexity too early.

---

# 63. Decision — Keep GPU as Future Capability

Phase 8 is CPU-first.

GPU architecture should be documented but not required for Phase 8 completion.

## Why

The platform needs to prove:

```text
register
store
deploy
predict
observe
rollback
```

before adding accelerator scheduling complexity.

---

# 64. Decision — Make Object Storage First-Class in Phase 8

Future model artifacts require durable object storage.

Preferred conceptual direction:

```text
MLflow
   |
   v
S3-compatible object storage
   |
   v
KServe model load
```

Likely local/dev option:

```text
MinIO
```

subject to version/compatibility validation.

## Why

A model registry alone is not the artifact store.

---

# 65. Decision — Keep Container Registry and Model Artifact Store Separate

Current container registry:

```text
GHCR
```

Future model artifact store:

```text
S3-compatible object storage
```

## Why

Container images and model artifacts have different lifecycles and consumers.

Do not force model artifacts into GHCR merely because containers already use it.

---

# 66. Decision — MLflow for Metadata/Registry, Object Storage for Artifacts

Future architecture direction:

```text
MLflow
  -> model metadata/version
  -> artifact URI

Object storage
  -> actual model artifact bytes
```

## Why

This matches the natural separation between registry metadata and artifact storage.

---

# 67. Decision — KServe as Serving Abstraction

Future Phase 8 direction:

```text
ModelService
    |
    v
Go Operator
    |
    v
KServe InferenceService
```

## Why

The platform should not reinvent a model-serving control plane if KServe provides a mature Kubernetes-native abstraction.

The exact KServe version and deployment mode must still be validated against Kubernetes 1.36.1.

---

# 68. Decision — Verify KServe Compatibility Before Install

Do not guess KServe version.

Before Phase 8:

```text
check current official KServe release
check Kubernetes 1.36.1 compatibility
choose Standard/RawDeployment vs Serverless/Knative
```

## Operational consequence

Version selection is a pre-install gate.

---

# 69. Decision — Avoid AI Agent Complexity in Phase 8

The platform does not need an AI agent to prove the serving architecture.

## Why

The goal is infrastructure/platform capability:

```text
model registration
artifact storage
deployment
prediction
monitoring
rollback
```

Adding an agent would distract from the control-plane validation.

---

# 70. Decision — Keep Documentation Reproducible

The project explicitly rejected short architecture-summary documents as sufficient implementation documentation.

Current documentation standard:

```text
prerequisites
versions
files/paths
commands
snippets
expected output
validation
failure/root cause/fix
rollback/recovery
security rationale
references
```

## Why

A new engineer must be able to rebuild and troubleshoot the platform without needing the original chat history.

---

# 71. Decision — Preserve Original Documentation Filenames

The repaired documentation keeps original filenames such as:

```text
033-image-admission-policies.md
034-pod-init-and-ephemeral-container-policy.md
036-prometheus-alerting.md
037-secret-management-strategy.md
038-secret-scanning.md
039-software-supply-chain-security.md
040-end-to-end-delivery-workflow.md
041-validation-and-security-tests.md
042-disaster-recovery-and-rebuild.md
043-troubleshooting-guide.md
044-operations-runbook.md
045-command-reference.md
046-security-model.md
047-design-decisions.md
```

## Why

Filename stability preserves existing references and prevents documentation drift.

---

# 72. Decision — Distinguish Verified Facts from Representative Snippets

Where exact repo evidence is unavailable, documentation must say:

```text
representative
verify actual repo
```

rather than presenting invented YAML as exact implementation.

## Why

Implementation documentation must be accurate enough to trust.

---

# 73. Decision — Use the Repository as Exact Source of Truth

When documentation and repository disagree:

```text
inspect repository
inspect live cluster
correct documentation
```

Do not automatically change working code to match stale documentation.

---

# 74. Decision — Keep Security Controls Observable After Upgrades

After upgrades to:

```text
Argo
Policy Controller
trust-policies
Prometheus
Keycloak
Kubernetes
```

re-run:

```text
positive admission
mutable image denial
public image denial
fake digest denial
init denial
ephemeral denial
Prometheus target
reconcile metrics
OIDC login
Argo drift
```

## Why

Version upgrades can change behavior without obvious YAML errors.

---

# 75. Decision — Treat Security Workflow Changes as Security Changes

Changes to:

```text
CodeQL
Gitleaks
govulncheck
Trivy
attestation
GitOps image validation
admission policy
trust policy
```

require stronger review than normal implementation changes.

## Why

These workflows define enforcement, not only automation.

---

# 76. Decision — Keep Action Versions SHA-Pinned

Known validated pins:

```text
CodeQL:
<COMMIT_SHA>

actions/attest:
<COMMIT_SHA>

actions/create-github-app-token:
<COMMIT_SHA>
```

## Why

Mutable action tags are weaker supply-chain anchors.

---

# 77. Decision — Verify Tool Downloads with Checksums

Validated for:

```text
kubeconform 0.7.0
```

and kind tooling in source automation.

## Why

Installing a pinned version is not sufficient if the downloaded binary itself is not verified.

---

# 78. Decision — Do Not Treat Security Visibility as Security Enforcement

The project discovered that independent security workflows could report failures without blocking release.

This led to the current design rule:

```text
detection must connect to an enforcement boundary
```

Examples:

```text
Gitleaks -> required source check
Trivy -> release job failure
GitOps image validation -> required GitOps check
admission -> API server denial
```

---

# 79. Decision — Keep Positive and Negative Security Tests

Security implementation is not validated by successful deployment alone.

The platform tests:

```text
trusted image -> allow
mutable image -> deny
public image -> deny
fake digest -> deny
bad init -> deny
bad ephemeral -> deny
```

## Why

A positive test proves availability.

Negative tests prove enforcement.

---

# 80. Decision — Do Not Use Broad Wildcards to Fix Permissions

When AppProject or policy rejects a required resource, the fix is:

```text
add the exact needed permission
```

not:

```text
allow everything
```

## Why

Troubleshooting should not permanently weaken the security boundary.

---

# 81. Decision — Do Not Disable Admission to Fix Delivery

If Argo sync fails due to admission:

```text
fix the image, trust evidence, or policy
```

Do not remove:

```text
ValidatingAdmissionPolicy
Policy Controller
namespace enforcement
```

to make the deployment succeed.

---

# 82. Decision — Keep Recovery Security-Equivalent to Normal Delivery

Disaster recovery and rollback must preserve:

```text
Git
digests
attestations
admission
OIDC
secret separation
monitoring
```

## Why

Recovery is a high-risk period and should not become a permanent bypass mode.

---

# 83. Decision — Break-Glass Is Temporary

Break-glass access is allowed only for:

```text
bootstrap
OIDC outage
critical recovery
```

Afterward:

```text
restore normal identity
rotate emergency credential
disable routine local admin
```

---

# 84. Decision — Keep Runtime Trust Independent of Git Trust

Even if GitOps main is protected, Kubernetes admission still verifies images.

## Why

Git repository security and runtime artifact trust are different boundaries.

Defense in depth assumes either could fail.

---

# 85. Decision — Keep Model Artifact Trust Separate from Container Trust

Future Phase 8 must define model artifact integrity independently.

Container attestation proves:

```text
container image provenance
```

It does not automatically prove:

```text
model artifact provenance
model registry approval
model version integrity
```

This requires a separate design.

---

# 86. Decision — Keep Phase 8 on Hold Until Documentation Repair Is Complete

Current state:

```text
Phase 7 implementation complete
Phase 7 documentation repair in progress
Phase 8 implementation on hold
```

## Why

A reproducible Phase 7 baseline is required before introducing additional platform complexity.

---

# 87. Decision — Complete Phase 7 Documentation Before AI Integration

The current repair sequence prioritizes the operational/security documentation first.

The implementation standard is:

```text
another engineer can rebuild, validate, diagnose, and recover from docs + repos
```

Only then should Phase 8 begin.

---

# 88. Decision — Treat Whole-Resource Prune as Not Fully Proven

The project has not exhaustively tested destructive prune scenarios.

## Why

Deleting a whole managed resource can have different operational consequences from simple field drift.

## Operational consequence

Review resource removals carefully and do not claim exhaustive prune validation.

---

# 89. Decision — Do Not Claim Alert Delivery Without Testing It

The project has configured and loaded PrometheusRule alerts.

It has not yet fully demonstrated:

```text
all alerts firing
all Alertmanager routes
all notifications delivered
```

## Why

Configured != operationally proven.

---

# 90. Decision — Use Real Failure Evidence in Documentation

Known real failures include:

```text
GitHub App installation lookup -> Not Found
Policy Controller CRD ownership conflict
Kustomize patch target not found
PrometheusRule selector mismatch
Policy Controller webhook drift
fake digest -> no valid bundles exist in registry
```

## Why

Real failure cases produce more useful operational documentation than generic troubleshooting advice.

---

# 91. Decision — Keep Exact Secret Names Repository-Derived

The exact current GitHub Actions secret/variable names were not preserved in the design evidence.

Therefore documentation must inspect:

```text
.github/workflows/release-images.yml
```

before stating exact names.

## Why

Invented secret names break rebuild reproducibility.

---

# 92. Decision — Keep Exact Native Policy CEL Repository-Derived

The exact committed native policy names and CEL expressions must come from:

```text
platform/policies/
```

Representative snippets are useful for explanation but are not authoritative.

---

# 93. Decision — Keep Exact Monitoring Selectors Repository-Derived

The current validated facts include:

```text
ServiceMonitor path
namespace
metrics service
PrometheusRule expressions
release: kps
```

Exact service label selector/port name should still be verified from live/repo state.

---

# 94. Decision — Keep Exact Argo Application Names Verifiable

Documentation may refer to expected names like:

```text
ai-platform-api
ai-platform-operator
ai-platform-monitoring
```

but engineers should inspect:

```bash
argocd app list
```

before assuming names in a rebuilt environment.

---

# 95. Decision — Prefer Narrow, Explicit Security Rules

Across the design, the same pattern is used:

```text
narrow AppProject permissions
narrow GitHub App repo scope
narrow Sigstore image scope
narrow admission image allowlist
narrow Argo ignoreDifferences
narrow secret-scanner allowlists
```

## Why

Broad exceptions accumulate hidden risk.

---

# 96. Decision — Separate Availability from Security Validation

A running Pod does not prove:

```text
correct Git provenance
trusted digest
correct admission behavior
monitoring health
secret hygiene
```

Likewise, a denied Pod does not automatically mean:

```text
security is working correctly
```

The denial must happen for the expected reason.

---

# 97. Decision — Separate Structural and Trust Test Cases

For testing:

```text
nginx:latest
```

is used to validate structural/repository restrictions.

```text
approved repo + fake digest
```

is used to validate trust verification.

## Why

A single negative test cannot prove both layers independently.

---

# 98. Decision — Use Git Revert as Audit-Friendly Rollback

A revert creates:

```text
new Git history
clear incident record
preserved previous commit
reviewable PR
```

This is preferable to rewriting Git history for normal rollback.

---

# 99. Decision — Avoid Force Push in Normal Operations

Source ruleset blocks non-fast-forward updates.

GitOps should also preserve a protected main model.

## Why

History rewriting damages traceability and can bypass review.

Use force push only for exceptional history-cleanup incidents with explicit authorization.

---

# 100. Decision — Treat Repository Rulesets as Part of Infrastructure

Branch protection is not merely a GitHub UI preference.

It is part of the platform security architecture.

The source ruleset is explicitly documented with:

```text
ID 21120105
```

## Operational consequence

Ruleset changes require validation just like code changes.

---

# 101. Decision — Preserve Solo-Maintainer Practicality

Current source protection uses:

```text
0 required approvals
```

because the project is operated by a solo maintainer.

But it still requires:

```text
PR workflow
required checks
stale-review handling
last-push approval behavior
no bypass
```

## Why

Security controls must remain workable for the actual team model.

---

# 102. Decision — Do Not Fake Enterprise Process Where Team Size Does Not Support It

The platform aims for enterprise-grade technical controls without pretending there are multiple independent reviewers when there are not.

## Why

Accurate governance is better than ceremonial controls that do not exist in practice.

---

# 103. Decision — Keep Cross-Repository Promotion Explicit

The source repository does not directly alter cluster state.

It only updates deployment intent through the GitOps repository.

## Why

This creates a visible, reviewable handoff between build and deployment systems.

---

# 104. Decision — Preserve Digest Traceability in Promotion Commit

Promotion commit title:

```text
chore(dev): deploy images from <source-sha>
```

## Why

This links GitOps deployment state back to source history.

---

# 105. Decision — Keep Promotion Branch Named by Source SHA

Pattern:

```text
automation/image-<source-sha>
```

## Why

This makes concurrent/stale promotions easier to identify and audit.

---

# 106. Decision — Do Not Merge Stale Promotion PRs Accidentally

If a newer source release exists, older promotion PRs should be reviewed as stale.

## Why

Otherwise an old artifact can overwrite a newer deployment unintentionally.

---

# 107. Decision — Keep Documentation as an Engineering Deliverable

Documentation is part of the platform implementation, not an afterthought.

A Phase is not fully maintainable if another engineer cannot reproduce it.

---

# 108. Decision — Use Commands, Expected Output, and Failure Paths in Docs

The repaired docs intentionally prioritize:

```text
commands
manifest snippets
validation
expected output
failure diagnosis
recovery
```

over narrative summary.

## Why

Operational documentation must be executable.

---

# 109. Decision — Avoid Overstating Validation

The project explicitly distinguishes:

```text
implemented
validated
not yet empirically validated
future
representative
```

## Why

Trustworthy documentation is more valuable than optimistic claims.

---

# 110. Decision — Keep Phase Boundaries Explicit

Phase 7:

```text
GitOps
security
supply chain
admission
monitoring
operations
```

Phase 8:

```text
KServe
object storage
MLflow
real model deployment
model-serving observability
```

## Why

Separating phases keeps implementation and testing manageable.

---

# 111. What Must Be Verified from the Actual Repositories

Do not treat this document as a replacement for repository inspection.

Verify exact current implementation for:

```text
GitOps branch ruleset
native admission policy names
CEL expressions
Binding selectors
GitHub Actions secret names
GitHub Actions variable names
Argo RBAC policy
Keycloak helper paths
TLS issuance details
Vault auth method
Vault secret paths
Gateway resource names
operator Deployment name
```

Source:

```bash
cd /mnt/data/ai-platform-operator

find .github/workflows \
  -maxdepth 1 \
  -type f \
  -print \
  | sort

sed -n '1,520p' \
  .github/workflows/release-images.yml
```

GitOps:

```bash
cd /mnt/data/ai-platform-gitops

find argocd \
  clusters \
  platform \
  modelservices \
  -maxdepth 4 \
  -type f \
  -print \
  | sort

sed -n '1,500p' \
  .github/workflows/validate.yml
```

The repository and live cluster remain the implementation source of truth.

---

# 112. References

Argo CD:

```text
https://argo-cd.readthedocs.io/
```

OpenGitOps principles:

```text
https://opengitops.dev/
```

Kubernetes admission:

```text
https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/
```

Sigstore Policy Controller:

```text
https://docs.sigstore.dev/policy-controller/overview/
```

GitHub Actions security hardening:

```text
https://docs.github.com/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
```
