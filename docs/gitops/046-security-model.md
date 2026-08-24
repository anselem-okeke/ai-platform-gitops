# Security Model

## Purpose

This document defines the **implemented security model of the AI Platform** and explains how the controls fit together operationally.

It is written for engineers who need to understand:

```text
what is trusted
what is not trusted
where enforcement happens
what identity is used
what can block a change
what can block a deployment
what can block a workload
where secrets live
how GitOps constrains runtime state
how supply-chain evidence is verified
how the platform should respond when a control fails
```

The security model is built around one principle:

> **Trust is granted only after explicit verification at each boundary.**

The platform does not assume that because one earlier stage was trusted, all later stages should be trusted automatically.

---

# 1. Security Model Overview

The platform uses multiple independent but connected trust boundaries:

```text
Developer
   |
   v
Source Repository
   |
   +--> branch protection
   +--> required CI checks
   |
   v
Release Pipeline
   |
   +--> hardened image build
   +--> vulnerability scanning
   +--> SBOM
   +--> provenance
   |
   v
GHCR
   |
   v
GitHub App Promotion
   |
   v
GitOps Repository
   |
   +--> digest-only validation
   +--> secret checks
   +--> protected main
   |
   v
Argo CD
   |
   v
Kubernetes Admission
   |
   +--> native image policy
   +--> Sigstore verification
   |
   v
Runtime Workload
   |
   v
Prometheus / Alerting
```

The design deliberately avoids a single security gate.

If one control is bypassed or misconfigured, another downstream control should still prevent unsafe execution where possible.

---

# 2. Primary Trust Boundaries

The major trust boundaries are:

```text
human -> GitHub
source Git -> release workflow
release workflow -> GHCR
release workflow -> GitOps
GitOps -> Argo CD
Argo CD -> Kubernetes API
Kubernetes API -> admission controls
admission -> runtime workload
runtime workload -> platform services
```

Each transition must be verified independently.

---

# 3. Security Boundary 1 — Developer to Source Repository

The developer is not allowed to treat `main` as a direct deployment path.

Source repository:

```text
/mnt/data/ai-platform-operator
```

Protected branch:

```text
main
```

Validated source ruleset:

```text
Source Main Protection
ID 21120105
state: active
bypass actors: none
```

Required controls:

```text
pull request required
deletion blocked
non-fast-forward blocked
required checks
```

---

# 4. Required Source Checks

The protected source branch currently requires:

```text
Gitleaks
Lint / Run on Ubuntu (pull_request)
E2E Tests / Run on Ubuntu (pull_request)
Tests / Run on Ubuntu (pull_request)
govulncheck
CodeQL
```

These are not advisory.

Expected behavior:

```text
check fails
    |
    v
merge blocked
```

This is the first major enforcement point.

---

# 5. Why Source CI Alone Is Not Enough

A workflow can fail while a repository still allows merge.

Therefore:

```text
CI execution
```

and:

```text
branch enforcement
```

must both exist.

The security model is:

```text
CI detects
ruleset enforces
```

If a check exists but is not required, the control is incomplete.

---

# 6. Security Boundary 2 — Source Main to Release Pipeline

The release workflow runs from:

```text
protected source main
```

not arbitrary feature branches.

This means the release pipeline trusts only code that has already passed the source merge gate.

The release pipeline does not independently redefine source approval.

It builds on top of the branch-protection decision.

---

# 7. Release Pipeline Responsibilities

The release pipeline is responsible for:

```text
building operator image
building API image
scanning images
pushing images to GHCR
capturing immutable digests
generating SPDX JSON SBOM
creating provenance attestation
creating SBOM attestation
opening GitOps promotion PR
```

A failure in these steps must block promotion.

---

# 8. Build Security

Validated builder:

```text
golang:1.26.6
```

Validated runtime:

```text
gcr.io/distroless/static-debian13:nonroot
```

Validated runtime user:

```text
65532
```

Build properties include:

```text
CGO_ENABLED=0
-trimpath
-ldflags
multi-stage build
distroless runtime
non-root execution
```

The build environment is not trusted to become the runtime environment.

The final image intentionally excludes the full toolchain.

---

# 9. Why Distroless Matters

The runtime image reduces:

```text
package manager surface
shell-based post-exploitation options
unused binaries
toolchain exposure
```

This does not make the image invulnerable.

It reduces unnecessary attack surface.

---

# 10. Security Boundary 3 — Build to Vulnerability Gate

Trivy scans the release images.

Validated policy:

```text
severity:
HIGH,CRITICAL

ignore-unfixed:
true

exit code:
1
```

Expected behavior:

```text
matching vulnerability
    |
    v
build job fails
    |
    v
promotion job does not run
```

The security model requires this failure connection.

---

# 11. Vulnerability Scanning Scope

Trivy and govulncheck serve different purposes.

govulncheck:

```text
Go reachable vulnerability analysis
```

Trivy:

```text
container/package/image vulnerability analysis
```

Current validated govulncheck result:

```text
0 reachable vulnerabilities
```

Do not interpret this as:

```text
all dependencies contain zero vulnerabilities
```

---

# 12. Security Boundary 4 — Build to Artifact Identity

The image digest is the canonical release identity.

Valid form:

```text
sha256:<64 lowercase hexadecimal characters>
```

Deployment does not trust mutable tags.

The model is:

```text
tag = convenience
digest = identity
```

---

# 13. Why Mutable Tags Are Not Trusted

A tag can be moved.

Examples:

```text
latest
dev
main
v1
```

The same tag may point to different bytes over time.

A digest identifies exact content.

Therefore GitOps final state must use:

```text
image@sha256:<digest>
```

---

# 14. Security Boundary 5 — Artifact to Supply-Chain Evidence

Every released image is paired with evidence.

Validated evidence:

```text
SPDX JSON SBOM
provenance attestation
SBOM attestation
```

Validated attestation action:

```text
actions/attest
```

Pinned SHA:

```text
508db95dd578ae2727ebd6217d5ba78e4fbda05d
```

---

# 15. Supply-Chain Identity Invariant

The following must refer to the same digest:

```text
pushed GHCR artifact
SBOM subject
provenance subject
GitOps promoted image
runtime deployment image
```

If one differs, traceability is broken.

---

# 16. Security Boundary 6 — Source Release to GitOps Repository

The source workflow does not deploy directly to Kubernetes.

Instead:

```text
source release
    |
    v
GitHub App
    |
    v
GitOps branch
    |
    v
GitOps pull request
```

This separates:

```text
artifact creation
```

from:

```text
deployment authorization
```

---

# 17. GitHub App Security Model

Bot identity:

```text
ai-platform-gitops-bot[bot]
```

Installation target:

```text
anselem-okeke/ai-platform-gitops
```

Required repository permissions:

```text
Contents: Read & write
Pull requests: Read & write
Metadata: Read
```

The App should not require broad organization access.

---

# 18. Why GitHub App Is Preferred Over PAT

The GitHub App model provides:

```text
narrow repository installation
explicit permissions
short-lived installation tokens
clear machine identity
revocable private keys
```

This is preferable to a long-lived developer PAT for cross-repository automation.

---

# 19. Short-Lived Token Model

The GitHub App private key is stored in GitHub Actions Secrets.

The release workflow uses it to mint a short-lived installation token.

Validated action:

```text
actions/create-github-app-token
```

Pinned SHA:

```text
bcd2ba49218906704ab6c1aa796996da409d3eb1
```

The installation token should exist only for the workflow run.

---

# 20. Security Boundary 7 — GitOps Promotion Branch

Expected promotion branch:

```text
automation/image-<source-sha>
```

Expected changed files:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

The bot is not trusted to modify arbitrary GitOps state during normal image promotion.

---

# 21. GitOps Promotion Scope

A normal image promotion should change exactly two files.

This limits automation authority.

If the automation changes:

```text
admission policies
AppProject
Gateway
monitoring
namespaces
```

during a normal image promotion, the security boundary has been violated.

---

# 22. Human Promotion Boundary

Current model:

```text
bot creates PR
human reviews
human merges
```

There is no automatic promotion merge.

This is intentional.

The human merge is the authorization step between:

```text
artifact release
```

and:

```text
deployment desired state
```

---

# 23. Security Boundary 8 — GitOps Repository Validation

GitOps CI validates final rendered state.

Validated workflow:

```text
.github/workflows/validate.yml
```

It renders key paths including:

```text
platform/operator/overlays/dev
platform/api/overlays/dev
platform/gateway/overlays/dev
platform/monitoring/overlays/dev
platform/policies/overlays/dev
modelservices/overlays/dev
clusters/dev/apps
```

---

# 24. GitOps Image Validation

The final rendered state must satisfy:

```text
approved GHCR repository
full @sha256:<64hex> digest
no final floating tag
no newTag as final identity
```

The raw base may contain placeholders.

Security enforcement targets the rendered overlay.

---

# 25. GitOps Schema Validation

Validated tool:

```text
kubeconform 0.7.0
```

The workflow:

```text
pins version
verifies checksum
renders manifests
runs strict validation
```

This protects the GitOps repository from invalid Kubernetes desired state.

---

# 26. GitOps Secret Defense

GitOps also performs secret-pattern checks.

Combined with:

```text
Gitleaks
.gitignore
review
```

this reduces accidental secret exposure.

Git is trusted to store:

```text
secret references
```

but not:

```text
secret values
```

---

# 27. Security Boundary 9 — GitOps Main to Argo CD

GitOps `main` is the deployment source of truth.

Argo CD consumes desired state from Git.

Source CI does not call:

```text
kubectl apply
kubectl set image
direct Argo sync
```

as the normal deployment path.

---

# 28. Argo Root vs Child Trust Model

Root Application:

```text
manual sync
```

Child Applications:

```text
automated sync
selfHeal
prune
```

The root is more privileged because it controls:

```text
child topology
repository sources
destinations
Helm sources
permissions
```

Therefore it is intentionally not fully automated.

---

# 29. AppProject Security Boundary

AppProject:

```text
ai-platform
```

Bootstrap-managed file:

```text
argocd/projects/ai-platform.yaml
```

It restricts:

```text
allowed repositories
destinations
cluster-scoped resource kinds
```

The model avoids broad wildcards where exact permissions are sufficient.

---

# 30. Why AppProject Is Bootstrap-Managed

The AppProject controls Argo's own deployment authority.

If Argo fully managed the object that defines its own permissions, a misconfiguration could create circular or overly broad authority.

The current model keeps AppProject changes deliberate and manually applied.

---

# 31. Security Boundary 10 — Argo to Kubernetes API

Argo can request resource changes.

Kubernetes admission decides whether those requests are allowed.

Argo is not the final authority.

This is important because:

```text
Git may contain a bad image reference
Argo may attempt to apply it
admission can still reject it
```

---

# 32. Native Admission Layer

The native admission layer uses:

```text
ValidatingAdmissionPolicy
ValidatingAdmissionPolicyBinding
```

Intended enforcement:

```text
failurePolicy: Fail
validationActions: Deny
```

The exact production policy names and CEL expressions must be read from the GitOps repository.

---

# 33. Native Admission Responsibilities

Native policy checks structural requirements such as:

```text
approved image repository
full SHA-256 digest
regular containers
init containers
ephemeral containers
direct Pods
workload templates where implemented
```

This layer does not prove artifact provenance.

It proves the reference is structurally allowed.

---

# 34. Why Structural Validation Is Separate

A reference can be structurally valid but still untrusted.

Example:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:aaaaaaaa...64
```

This can satisfy:

```text
approved repository
valid digest syntax
```

but still refer to no trusted artifact.

That is where Sigstore takes over.

---

# 35. Security Boundary 11 — Sigstore Trust

Policy Controller validates artifact trust.

Validated version:

```text
chart 0.10.6
app v0.13.1
namespace cosign-system
```

Trust policy chart:

```text
v0.7.0
```

---

# 36. GitHub Attestation Trust

Validated trust configuration:

```yaml
policy:
  enabled: true
  organization: anselem-okeke
  images:
    - "ghcr.io/anselem-okeke/ai-platform-operator**"
    - "ghcr.io/anselem-okeke/ai-platform-api**"
```

TrustRoot:

```text
github
```

ClusterImagePolicy:

```text
github-policy
```

---

# 37. Sigstore Security Responsibility

Sigstore answers:

```text
Does this digest have trusted evidence?
```

Native admission answers:

```text
Is this image reference structurally permitted?
```

Both are required.

---

# 38. Positive Admission Model

Trusted released image:

```text
approved repository
full digest
valid GitHub attestation
protected namespace
```

Expected:

```text
allowed
```

This is the positive security path.

---

# 39. Mutable Image Negative Model

Example:

```text
ghcr.io/anselem-okeke/ai-platform-api:latest
```

Expected:

```text
native admission denies
```

Sigstore should not be the first or only defense for this case.

---

# 40. Public Image Negative Model

Example:

```text
nginx:latest
```

Expected:

```text
denied
```

This proves the protected namespace cannot run arbitrary public images.

---

# 41. Fake Digest Negative Model

Example:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
```

Expected:

```text
native structure may pass
Sigstore denies
```

Validated observed error:

```text
no valid bundles exist in registry
```

---

# 42. Init Container Security

The security model covers:

```text
spec.initContainers[]
```

An untrusted init image must not be able to execute before the trusted main workload.

This matters because init containers can:

```text
modify volumes
prepare configuration
write files
contact external systems
```

---

# 43. Sidecar Security

All regular containers are subject to validation.

A trusted primary container does not authorize an untrusted sidecar.

The policy should evaluate:

```text
all containers
```

not only the first one.

---

# 44. Ephemeral Container Security

The security model also considers:

```text
spec.ephemeralContainers[]
```

This is important because `kubectl debug` can inject a container into an existing Pod.

The admission stack must not allow debugging to bypass the image trust model.

---

# 45. Direct Pod Security

A user should not be able to bypass Deployment-level policy by creating a Pod directly.

The security model requires direct Pod admission coverage in protected namespaces.

---

# 46. Protected Namespace Scope

Validated protected namespaces:

```text
ai-platform
ai-platform-operator-system
```

Validated label:

```text
policy.sigstore.dev/include=true
```

The image allowlist should not accidentally apply globally to unrelated system namespaces unless intentionally designed.

---

# 47. Security Boundary 12 — Runtime Identity

At runtime, the Pod should still use the same digest that was approved in GitOps.

Verification path:

```text
GitOps overlay
    |
    v
Kustomize render
    |
    v
Argo revision
    |
    v
Deployment image
    |
    v
Pod ImageID
```

Any divergence is a security investigation.

---

# 48. GitOps Drift Model

Manual live changes are treated as drift.

Child Applications use self-heal.

Expected:

```text
manual change
    |
    v
Argo detects OutOfSync
    |
    v
Git state restored
```

Git remains authoritative.

---

# 49. Why Manual `kubectl set image` Is Not Normal Operations

A manual image patch:

```text
bypasses Git review
breaks traceability
creates drift
may be self-healed
```

Normal deployment and rollback both flow through Git.

---

# 50. Rollback Security Model

Rollback uses:

```text
Git revert
```

to restore a previously approved digest.

The old digest must still:

```text
exist
be trusted
pass native admission
pass Sigstore
```

Rollback does not disable security controls.

---

# 51. Security Boundary 13 — Secrets

Secret values do not belong in Git.

Validated Vault endpoint:

```text
https://vault.platform.local:8200
```

Vault is the source of truth for runtime secret material.

---

# 52. Current Secret Delivery Model

Current honest model:

```text
Vault
    |
    v
authorized provisioning
    |
    v
Kubernetes Secret
    |
    v
workload
```

The project does not currently claim:

```text
External Secrets Operator
Vault CSI
Secrets Store CSI
```

are installed.

---

# 53. Git Secret Model

Allowed in Git:

```text
secret names
secretKeyRef
secret volume references
Vault references/config
```

Not allowed:

```text
real passwords
private keys
JWTs
tokens
base64-encoded real credentials
```

---

# 54. GitHub Actions Secret Model

CI-only sensitive material such as:

```text
GitHub App private key
```

belongs in:

```text
GitHub Actions Secrets
```

The workflow should mint temporary credentials when needed.

---

# 55. Secret Scanning Model

Controls include:

```text
Gitleaks
Git history scanning
GitOps secret-pattern check
.gitignore
review
```

The project has validated clean current/history scans for both source and GitOps repositories.

---

# 56. `.gitignore` Security Role

Validated GitOps patterns include:

```text
.local/
*.jwt
*.key
*.pem
.env
secret YAML patterns
```

No broad:

```text
*.crt
```

because public certificates are not automatically secret.

`.gitignore` is defense in depth, not an enforcement scanner.

---

# 57. Keycloak Identity Model

Keycloak is the central identity provider for platform access.

Validated version:

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

---

# 58. Argo OIDC Security Model

Argo uses Keycloak OIDC.

Validated client:

```text
ai-platform-argocd
```

Properties:

```text
public client
standard flow enabled
direct access grants disabled
PKCE S256
groups claim
```

The design avoids password-grant authentication.

---

# 59. CLI Authentication Model

Validated CLI client:

```text
ai-platform-cli
```

Callback:

```text
http://127.0.0.1:18080/callback
```

Authentication uses:

```text
Authorization Code + PKCE
```

This avoids storing a reusable password grant for CLI automation.

---

# 60. Argo Authorization Model

Keycloak groups map to Argo RBAC roles.

Conceptual mapping:

```text
platform-viewer
    -> read-only

platform-deployer
    -> controlled deployment actions

platform-admin
    -> administrative access
```

The exact RBAC policy must be read from the committed Argo configuration.

---

# 61. Local Argo Admin Model

Local admin is not the routine access method.

Expected lifecycle:

```text
bootstrap
    |
    v
configure OIDC
    |
    v
validate Keycloak access
    |
    v
disable routine local admin
```

Break-glass access remains documented separately.

---

# 62. Gateway Security Boundary

External access uses:

```text
Envoy Gateway
Gateway API
TLS
```

Validated public/internal hostnames:

```text
auth.ai-platform.local
argocd.ai-platform.local
api.ai-platform.local
```

Argo server itself remains:

```text
ClusterIP
```

---

# 63. Why Argo Server Remains ClusterIP

This limits direct service exposure.

The expected path is:

```text
user
    |
    v
Envoy Gateway
    |
    v
HTTPS route
    |
    v
Argo ClusterIP
```

Do not change service type simply for operational convenience.

---

# 64. TLS Security Model

TLS private keys are secret.

Public certificates are not equivalent to private keys.

Validated architectural source:

```text
Vault PKI
```

The exact certificate issuance workflow must be verified from the current implementation.

---

# 65. Security Boundary 14 — Monitoring and Detection

Security controls must be observable.

Policy Controller metrics service:

```text
policy-controller-webhook-metrics
```

Namespace:

```text
cosign-system
```

Port:

```text
9090
```

---

# 66. ServiceMonitor Security Role

Validated GitOps file:

```text
platform/monitoring/base/policy-controller-servicemonitor.yaml
```

Prometheus target validation:

```promql
up{
  namespace="cosign-system",
  service="policy-controller-webhook-metrics"
}
```

Validated healthy result:

```text
1
```

---

# 67. PrometheusRule Security Role

Validated file:

```text
platform/monitoring/base/policy-controller-prometheusrule.yaml
```

Required selector label:

```text
release: kps
```

Without it, the rule may exist but not be selected.

---

# 68. Security Alert — Target Down

Expression:

```promql
up{
  namespace="cosign-system",
  service="policy-controller-webhook-metrics"
} == 0
```

Duration:

```text
5m
```

Severity:

```text
critical
```

Purpose:

```text
detect lost visibility or target failure
```

---

# 69. Security Alert — Reconcile Failures

Expression:

```promql
sum(
  increase(
    policy_controller_reconcile_count{
      success="false"
    }[10m]
  )
) > 5
```

Duration:

```text
5m
```

Severity:

```text
warning
```

Purpose:

```text
detect sustained controller reconciliation problems
```

---

# 70. Security Alert — Webhook Certificate Failure

Expression:

```promql
increase(
  policy_controller_reconcile_count{
    reconciler="WebhookCertificates",
    success="false"
  }[10m]
) > 0
```

Duration:

```text
5m
```

Severity:

```text
critical
```

Purpose:

```text
detect TLS/admission certificate reconciliation failure
```

---

# 71. Current Monitoring Validation Boundary

Validated:

```text
Prometheus target up=1
reconcile metrics non-empty
PrometheusRule selected
```

Not empirically validated:

```text
all alerts intentionally fired
all Alertmanager routes tested
all notification channels tested
```

Do not overstate these.

---

# 72. Security Boundary 15 — Drift and Controller Mutation

Some Kubernetes controllers legitimately mutate resources.

The security model does not assume every diff is malicious.

But it requires narrow classification.

Known Policy Controller mutation:

```yaml
- key: webhooks.knative.dev/exclude
  operator: DoesNotExist
```

---

# 73. Argo `ignoreDifferences` Security Rule

Only controller-owned fields should be ignored.

The current model uses narrow ignore behavior with:

```text
RespectIgnoreDifferences=true
```

Do not ignore entire:

```text
MutatingWebhookConfiguration
ValidatingWebhookConfiguration
```

resources.

Broad ignores would hide meaningful security drift.

---

# 74. Security Failure Classification

Failures should be classified by boundary.

Examples:

```text
source CI failure
branch enforcement failure
release gate failure
artifact identity failure
attestation failure
GitHub App failure
GitOps validation failure
Argo reconciliation failure
native admission failure
Sigstore failure
runtime failure
monitoring failure
secret failure
```

Fix the first broken layer.

---

# 75. Security Model for Release Failure

If Trivy fails:

```text
do not promote
```

If attestation fails:

```text
do not promote
```

If GitHub App fails:

```text
do not bypass with manual direct deployment
```

If GitOps validation fails:

```text
do not merge
```

---

# 76. Security Model for Admission Failure

If a trusted release is denied:

```text
investigate trust chain
```

Do not:

```text
disable native admission
remove namespace label
disable Policy Controller
switch to mutable tag
```

The security boundary should remain intact while the root cause is diagnosed.

---

# 77. Security Model for Runtime Failure

If a properly trusted image crashes:

```text
admission did its job
```

The failure may now be:

```text
application bug
configuration error
secret error
dependency outage
resource issue
```

Do not attribute all runtime failures to supply-chain controls.

---

# 78. Security Model for Secret Failure

If a workload cannot start because a Secret is missing:

```text
restore secret from approved source
```

Do not commit plaintext secret YAML to restore availability.

Availability does not justify breaking the secret boundary.

---

# 79. Security Model for Rollback

A rollback is legitimate only if it preserves:

```text
Git review
digest identity
attestation trust
admission enforcement
traceability
```

The rollback path is:

```text
Git revert
    |
    v
GitOps PR
    |
    v
merge
    |
    v
Argo
    |
    v
admission
```

---

# 80. Security Model for Disaster Recovery

Recovery starts from:

```text
Git repositories
Vault
GitHub secure configuration
```

not from undocumented live-state reconstruction.

The minimum secure rebuild order is:

```text
cluster
Argo
AppProject
root Application
child Applications
Policy Controller
trust policies
native admission
runtime secrets
workloads
monitoring
validation
```

---

# 81. Threat — Direct Push to Source Main

Mitigation:

```text
Source Main Protection
PR requirement
no bypass
required checks
```

Expected result:

```text
direct push rejected
```

---

# 82. Threat — Security Check Fails but Release Continues

Mitigation:

```text
branch ruleset blocks merge
release runs only from protected main
```

For release-specific security:

```text
GitOps promotion depends on successful image jobs
```

---

# 83. Threat — Vulnerable Image Promotion

Mitigation:

```text
Trivy HIGH/CRITICAL gate
exit code 1
GitOps promotion depends on success
```

---

# 84. Threat — Mutable Image Replacement

Mitigation:

```text
GitOps final digest validation
native admission digest validation
```

Runtime uses immutable content identity.

---

# 85. Threat — Fake Digest with Correct Syntax

Mitigation:

```text
Sigstore Policy Controller
GitHub artifact attestation trust
```

Validated negative result:

```text
no valid bundles exist in registry
```

---

# 86. Threat — Arbitrary Public Image

Mitigation:

```text
native image repository allowlist
Sigstore trust scope
protected namespaces
```

Example denied:

```text
nginx:latest
```

---

# 87. Threat — Init Container Bypass

Mitigation:

```text
initContainers validation
```

An untrusted init container must not execute before trusted workload startup.

---

# 88. Threat — Sidecar Bypass

Mitigation:

```text
all regular containers validated
```

Policy should not validate only index zero.

---

# 89. Threat — `kubectl debug` Bypass

Mitigation:

```text
ephemeralContainers validation
admission webhook coverage
protected namespaces
```

Untrusted debug image should be denied.

---

# 90. Threat — Direct Pod Bypass

Mitigation:

```text
direct Pod admission coverage
```

Controller ownership is not considered a trust boundary by itself.

---

# 91. Threat — GitOps Bot Compromise

Mitigations:

```text
GitHub App installation scoped to one repo
minimal permissions
short-lived token
bot cannot merge main automatically
GitOps CI validates changes
human merge required
admission validates runtime
```

This is defense in depth.

---

# 92. Threat — GitOps Repository Compromise

Mitigations:

```text
protected main
PR validation
digest validation
secret scanning
Argo AppProject restrictions
native admission
Sigstore trust
```

Even malicious Git desired state should still encounter admission controls.

---

# 93. Threat — Argo Compromise

Mitigations:

```text
AppProject scope
Kubernetes RBAC
native admission
Sigstore admission
protected namespace policies
```

Argo is powerful, but not intended to be the final security authority.

---

# 94. Threat — Policy Controller Failure

Mitigations:

```text
native structural image policy still exists
metrics
Prometheus target alert
reconcile failure alert
webhook certificate alert
```

The exact fail-open/fail-closed behavior of the webhook must be verified from live configuration.

Do not assume behavior without inspection.

---

# 95. Threat — Native Policy Misconfiguration

Mitigations:

```text
GitOps validation
server dry-run
negative tests
Sigstore downstream verification
```

A structurally permitted fake digest should still fail Sigstore.

---

# 96. Threat — Secret Committed to Git

Mitigations:

```text
.gitignore
Gitleaks
GitOps secret-pattern check
branch protection
review
```

If leakage occurs:

```text
revoke first
clean Git second
```

---

# 97. Threat — Long-Lived Cross-Repository Token

Mitigation:

```text
GitHub App private key
short-lived installation token
narrow installation
```

Do not store installation tokens persistently.

---

# 98. Threat — Broad Argo Permission

Mitigation:

```text
AppProject allowlist
exact destinations
exact cluster resources
manual root
```

Avoid wildcard permissions where possible.

---

# 99. Threat — Broad Argo Ignore Rule

Mitigation:

```text
narrow ignoreDifferences
```

Only known controller-owned mutation is ignored.

Broad ignores can hide security drift.

---

# 100. Threat — Unauthorized Platform Access

Mitigation:

```text
Keycloak OIDC
group-based RBAC
PKCE
no routine local admin
TLS Gateway exposure
```

---

# 101. Threat — Password Grant Abuse

Mitigation:

```text
directAccessGrantsEnabled = false
Authorization Code + PKCE
```

This is validated for the Argo OIDC client.

---

# 102. Threat — Insecure Argo Exposure

Mitigation:

```text
argocd-server ClusterIP
Envoy Gateway
TLS
OIDC
```

Do not expose the service directly as a public LoadBalancer.

---

# 103. Threat — Runtime Image Drift

Mitigation:

```text
Argo self-heal
digest-pinned Git
live digest verification
```

Manual live image changes should not persist.

---

# 104. Threat — Stale Promotion PR

Mitigation:

```text
source SHA in branch
source SHA in commit/PR title
human review
close superseded PRs
```

Do not merge an older promotion after a newer release unintentionally.

---

# 105. Threat — Rollback to Untrusted Artifact

Mitigation:

```text
old digest must still pass admission
Git rollback does not bypass trust
```

If the old artifact is no longer trusted, create a new safe release instead.

---

# 106. Threat — Metrics Blindness

Mitigation:

```text
ServiceMonitor
Prometheus target query
PrometheusRule
```

A security controller without observability is incomplete.

---

# 107. Threat — Alert Rule Exists but Is Not Selected

Mitigation:

```text
release: kps
Prometheus ruleSelector verification
```

This exact issue occurred and was corrected.

---

# 108. Threat — Metrics Target Disappears Entirely

Current target-down rule detects:

```text
up == 0
```

A completely absent series may require separate `absent()` logic.

The current model does not claim this hardening is implemented.

---

# 109. Threat — Unauthorized Secret Read

Mitigation:

```text
Kubernetes RBAC
namespace scoping
Vault access policy
avoid unnecessary list/watch Secret permissions
```

Secret access is equivalent to credential access.

---

# 110. Threat — Secret Exposure in Logs

Mitigation:

```text
do not echo tokens
do not dump environments
use --redact
avoid set -x around secrets
```

GitHub masking is defense in depth, not the main control.

---

# 111. Threat — Secret Recovery Through Git

Mitigation:

```text
Git stores references only
Vault is source of truth
```

Disaster recovery must restore secrets separately.

---

# 112. Security Operating Model

During normal operations:

```text
source changes through PR
release through protected main
promotion through GitOps PR
deployment through Argo
runtime through admission
rollback through Git
secrets through Vault/secure stores
access through Keycloak OIDC
```

Any shortcut should be treated as a break-glass exception.

---

# 113. Break-Glass Model

Break-glass access may be needed for:

```text
OIDC outage
Argo bootstrap
critical recovery
```

Break-glass should be:

```text
time-limited
documented
audited
rotated afterward
removed from routine use
```

Do not leave emergency credentials enabled permanently.

---

# 114. Security Model After Platform Upgrade

After upgrading:

```text
Argo
Policy Controller
trust policies
Prometheus
Keycloak
Kubernetes
```

re-run:

```text
trusted image positive test
mutable image negative test
public image negative test
fake digest negative test
init container negative test
ephemeral container negative test
Prometheus target check
reconcile metric check
Argo drift check
OIDC login
```

Upgrades must not be assumed security-neutral.

---

# 115. Security Model for New First-Party Image

When adding a new platform image, update all relevant boundaries.

Required changes may include:

```text
release build
GHCR repository
SBOM/provenance
GitOps image validator
native repository allowlist
Sigstore trust image scope
admission tests
monitoring if applicable
```

Do not expand only one trust layer.

---

# 116. Security Model for Future Phase 8

Future AI-serving components such as:

```text
KServe
MLflow
object storage
model runtime images
```

must inherit this model.

New workloads should still require:

```text
trusted source
hardened image
vulnerability scan
digest identity
attestation
GitOps promotion
native admission
Sigstore trust
secret separation
monitoring
```

---

# 117. Model Artifact Security — Future Consideration

Container trust is not identical to model artifact trust.

Future Phase 8 should separately define:

```text
model artifact source
artifact checksum
MLflow registry trust
object-storage access
promotion approval
model version rollback
```

Do not assume container attestation automatically proves model artifact integrity.

---

# 118. What Is Currently Strongly Validated

The project has empirically validated:

```text
required source checks
source ruleset enforcement
Gitleaks clean history/current state
source release path
GHCR digest output
GitHub App promotion PR
GitOps render validation
digest-only desired state
Argo reconciliation
drift self-heal
Git rollback
trusted digest admission
mutable/public image denial
fake digest denial
init container denial
ephemeral image denial
Policy Controller metrics scrape
reconcile metrics presence
```

---

# 119. What Is Not Yet Fully Empirically Validated

Do not claim:

```text
all Prometheus alerts were intentionally fired
all Alertmanager notification routes were tested
all destructive prune cases were tested
External Secrets Operator is installed
Vault CSI is installed
all possible native admission workload kinds are covered
production on-call escalation is implemented
```

These remain implementation/validation boundaries.

---

# 120. Security Verification Commands — Source

Inspect source ruleset:

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets/21120105
```

Run Gitleaks:

```bash
cd /mnt/data/ai-platform-operator

gitleaks git \
  --redact
```

Run govulncheck:

```bash
govulncheck ./...
```

Inspect security workflow:

```bash
sed -n '1,360p' \
  .github/workflows/security.yml
```

---

# 121. Security Verification Commands — Release

Inspect release workflow:

```bash
sed -n '1,520p' \
  /mnt/data/ai-platform-operator/.github/workflows/release-images.yml
```

Check action pins:

```bash
grep -nE \
  'f205ea1c3313d32999d8d6a48b4f6530d4437b38|508db95dd578ae2727ebd6217d5ba78e4fbda05d|bcd2ba49218906704ab6c1aa796996da409d3eb1' \
  /mnt/data/ai-platform-operator/.github/workflows/*.yml
```

---

# 122. Security Verification Commands — GitOps

Render API:

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/security-api.yaml
```

Render operator:

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/security-operator.yaml
```

Check final images:

```bash
grep -n \
  'image:' \
  /tmp/security-api.yaml \
  /tmp/security-operator.yaml
```

---

# 123. Security Verification Commands — Admission

Native:

```bash
kubectl get validatingadmissionpolicies
kubectl get validatingadmissionpolicybindings
```

Sigstore:

```bash
kubectl get trustroots.policy.sigstore.dev
kubectl get clusterimagepolicies.policy.sigstore.dev
```

Protected namespaces:

```bash
kubectl get ns \
  ai-platform \
  ai-platform-operator-system \
  --show-labels
```

---

# 124. Security Verification Commands — Monitoring

ServiceMonitor:

```bash
kubectl get servicemonitor \
  policy-controller \
  -n monitoring \
  -o yaml
```

PrometheusRule:

```bash
kubectl get prometheusrule \
  policy-controller \
  -n monitoring \
  -o yaml
```

Metrics service:

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system
```

---

# 125. Security Verification Commands — Secrets

Source scan:

```bash
cd /mnt/data/ai-platform-operator

gitleaks git --redact
```

GitOps scan:

```bash
cd /mnt/data/ai-platform-gitops

gitleaks git --redact
```

Sensitive tracked files:

```bash
git ls-files \
  | grep -Ei '\.(pem|key|jwt)$'
```

Private key marker:

```bash
git grep -nE \
  'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY'
```

---

# 126. Security Verification Commands — Identity

Keycloak groups:

```text
platform-viewer
platform-deployer
platform-admin
```

Argo OIDC client:

```text
ai-platform-argocd
```

CLI client:

```text
ai-platform-cli
```

Use actual KCADM helper scripts from the repository.

Do not expose token values in command logs.

---

# 127. What Must Be Verified from the Actual Repositories

Do not invent:

```text
exact native policy names
exact CEL expressions
exact Binding selector
exact GitOps branch-protection ruleset
exact GitHub Actions secret names
exact GitHub Actions variable names
exact Argo RBAC policy
exact Keycloak script paths
exact TLS issuance implementation
exact Vault auth method
exact Vault secret paths
```

Inspect source:

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

Inspect GitOps:

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

The repositories and live cluster remain the exact source of truth.

---

# 128. References

GitHub Actions security hardening:

```text
https://docs.github.com/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
```

Kubernetes admission control:

```text
https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/
```

Kubernetes ValidatingAdmissionPolicy:

```text
https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/
```

Sigstore Policy Controller:

```text
https://docs.sigstore.dev/policy-controller/overview/
```

Argo CD security:

```text
https://argo-cd.readthedocs.io/
```
