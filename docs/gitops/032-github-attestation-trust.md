# GitHub Artifact Attestation Trust

## Purpose

This document is the **reproducible implementation and verification guide** for the trust relationship between GitHub Artifact Attestations and Kubernetes admission in the AI Platform.

The goal is to ensure that the cluster does not trust an image merely because:

```text
the registry exists
the image uses a SHA-256 digest
the image comes from GHCR
```

Instead, the cluster verifies that the exact immutable image digest carries trusted evidence produced by the approved GitHub release workflow.

The validated trust chain is:

```text
source commit
    |
    v
GitHub Actions release
    |
    +--> build image
    +--> scan image
    +--> push image
    +--> capture immutable digest
    +--> provenance attestation
    +--> SBOM attestation
    |
    v
GHCR image@sha256:<digest>
    |
    v
GitOps promotion
    |
    v
Kubernetes admission request
    |
    v
Sigstore Policy Controller
    |
    +--> TrustRoot/github
    +--> ClusterImagePolicy/github-policy
    |
    +--> valid trusted bundle for exact digest -> ALLOW
    |
    +--> missing/untrusted evidence -> DENY
```

A new engineer should be able to:

```text
understand the trust model
recreate the GitHub trust policy
verify TrustRoot and ClusterImagePolicy
validate trusted-image admission
validate fake-digest rejection
troubleshoot missing attestations
verify organization/image scope
rotate or replace trust configuration safely
```

using this guide and the platform repositories.

---

# 1. Components Involved

The trust path spans both repositories and the Kubernetes cluster.

## Source Repository

```text
/mnt/data/ai-platform-operator
```

Responsible for:

```text
building images
publishing images
creating attestations
```

## GitOps Repository

```text
/mnt/data/ai-platform-gitops
```

Responsible for:

```text
trust-policy desired state
protected namespace labels
promotion of immutable digests
```

## Cluster Components

```text
Sigstore Policy Controller
TrustRoot/github
ClusterImagePolicy/github-policy
GitHub Artifact Attestations trust policy chart
Kubernetes admission webhooks
```

---

# 2. Validated Versions

Validated trust-policy Helm chart:

```text
trust-policies
```

Version:

```text
v0.7.0
```

Repository:

```text
ghcr.io/github/artifact-attestations-helm-charts
```

Policy Controller:

```text
chart 0.10.6
app version 0.13.1
namespace cosign-system
```

---

# 3. Why Digest Pinning Alone Is Not Trust

A digest proves immutability of content identity.

Example:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>
```

This tells Kubernetes:

```text
pull these exact bytes
```

It does **not** prove:

```text
who built them
which workflow built them
which source commit produced them
whether security checks passed
whether the image belongs to an approved release process
```

Therefore the platform combines:

```text
digest pinning
    +
trusted attestation verification
```

---

# 4. Why GHCR Location Alone Is Not Trust

An image under:

```text
ghcr.io/anselem-okeke/
```

is not automatically safe.

A compromised workflow or incorrectly published image could still exist in the same registry namespace.

The runtime policy therefore verifies:

```text
registry scope
image scope
digest identity
attestation trust
```

---

# 5. Source Release Attestation Step

The source release workflow uses GitHub Artifact Attestations.

Validated pinned action:

```text
actions/attest
```

Pinned commit:

```text
508db95dd578ae2727ebd6217d5ba78e4fbda05d
```

Validated release evidence includes:

```text
provenance attestation
SBOM attestation
```

The attestation must refer to the exact digest later promoted through GitOps.

---

# 6. Workflow Permission Requirement

GitHub Artifact Attestations typically require explicit workflow permissions.

A representative release-workflow permission block may look like:

```yaml
permissions:
  contents: read
  packages: write
  id-token: write
  attestations: write
```

The exact current source workflow should be inspected before rebuilding.

Do not add broader permissions such as:

```text
administration
issues write
pull requests write
```

to attestation jobs unless they are separately required.

---

# 7. Representative Provenance Attestation Snippet

A representative pattern is:

```yaml
- name: Attest image provenance
  uses: actions/attest@508db95dd578ae2727ebd6217d5ba78e4fbda05d
  with:
    subject-name: ghcr.io/anselem-okeke/ai-platform-api
    subject-digest: ${{ steps.build.outputs.digest }}
    push-to-registry: true
```

The exact `subject-name` and digest-output step IDs must match the actual workflow.

The important invariant is:

```text
subject-digest == digest promoted through GitOps
```

---

# 8. Representative SBOM Attestation Snippet

The release pipeline also generates an SPDX JSON SBOM.

Representative pattern:

```yaml
- name: Attest SBOM
  uses: actions/attest@508db95dd578ae2727ebd6217d5ba78e4fbda05d
  with:
    subject-name: ghcr.io/anselem-okeke/ai-platform-api
    subject-digest: ${{ steps.build.outputs.digest }}
    sbom-path: /tmp/api.spdx.json
    push-to-registry: true
```

Use the actual workflow field names and file paths from the repository.

---

# 9. Why the Attestation Must Use the Pushed Digest

Correct:

```text
build
  |
  v
push
  |
  v
digest X
  |
  +--> attest X
  |
  +--> promote X
```

Incorrect:

```text
build A
attest A
rebuild B
push B
promote B
```

The attestation would no longer describe the runtime artifact.

---

# 10. Inspect Attestation Workflow in Source Repository

Run:

```bash
cd /mnt/data/ai-platform-operator

grep -RIn \
  -A25 -B10 \
  'actions/attest\|attest\|sbom\|subject-digest' \
  .github/workflows
```

Confirm:

```text
the action is pinned
subject digest comes from the pushed image
SBOM path exists
attestation occurs before GitOps promotion
```

---

# 11. Trust Policy Helm Values

The validated trust-policy values are:

```yaml
policy:
  enabled: true
  organization: anselem-okeke
  images:
    - "ghcr.io/anselem-okeke/ai-platform-operator**"
    - "ghcr.io/anselem-okeke/ai-platform-api**"
```

This is the main trust-scope configuration.

---

# 12. Meaning of `organization`

```yaml
organization: anselem-okeke
```

This constrains trust to GitHub Artifact Attestations associated with the approved GitHub owner/organization.

Do not broaden this to unrelated organizations.

---

# 13. Meaning of `images`

Validated image patterns:

```yaml
images:
  - "ghcr.io/anselem-okeke/ai-platform-operator**"
  - "ghcr.io/anselem-okeke/ai-platform-api**"
```

This limits policy scope to the first-party platform images.

Do not use a wildcard such as:

```yaml
images:
  - "ghcr.io/**"
```

because that would trust a much larger image space.

---

# 14. Temporary Values File Used During Manual Validation

A rebuild/troubleshooting values file can be created as:

```bash
cat >/tmp/github-attestation-policy-values.yaml <<'EOF'
policy:
  enabled: true
  organization: anselem-okeke
  images:
    - "ghcr.io/anselem-okeke/ai-platform-operator**"
    - "ghcr.io/anselem-okeke/ai-platform-api**"
EOF
```

Validate:

```bash
cat /tmp/github-attestation-policy-values.yaml
```

This file contains no secret material.

---

# 15. Manual Helm Command Used During Validation

Validated command:

```bash
helm upgrade trust-policies --install \
  --rollback-on-failure \
  --namespace cosign-system \
  oci://ghcr.io/github/artifact-attestations-helm-charts/trust-policies \
  --version v0.7.0 \
  -f /tmp/github-attestation-policy-values.yaml
```

This was useful during implementation validation.

The final desired state is GitOps-managed through Argo CD.

---

# 16. GitOps Argo Application

Representative manifest:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: trust-policies
  namespace: argocd
spec:
  project: ai-platform

  source:
    repoURL: ghcr.io/github/artifact-attestations-helm-charts
    chart: trust-policies
    targetRevision: v0.7.0
    helm:
      values: |
        policy:
          enabled: true
          organization: anselem-okeke
          images:
            - "ghcr.io/anselem-okeke/ai-platform-operator**"
            - "ghcr.io/anselem-okeke/ai-platform-api**"

  destination:
    server: https://kubernetes.default.svc
    namespace: cosign-system

  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

Use the actual GitOps manifest when rebuilding if its Helm-values layout differs.

---

# 17. AppProject Requirements

The AppProject must permit:

```text
source:
ghcr.io/github/artifact-attestations-helm-charts

destination:
cosign-system
```

and the generated cluster-scoped policy resources.

Representative allowlist:

```yaml
clusterResourceWhitelist:
  - group: policy.sigstore.dev
    kind: TrustRoot

  - group: policy.sigstore.dev
    kind: ClusterImagePolicy
```

Do not use broad wildcards if exact resource kinds are known.

---

# 18. Verify Argo Application

```bash
argocd app get \
  trust-policies \
  --refresh
```

Expected:

```text
Sync Status: Synced
Health Status: Healthy
```

Also:

```bash
kubectl get application \
  trust-policies \
  -n argocd
```

---

# 19. TrustRoot

The trust-policy chart creates:

```text
TrustRoot/github
```

Verify:

```bash
kubectl get trustroots.policy.sigstore.dev
```

Expected:

```text
github
```

Inspect:

```bash
kubectl get trustroot \
  github \
  -o yaml
```

---

# 20. ClusterImagePolicy

The chart creates:

```text
ClusterImagePolicy/github-policy
```

Verify:

```bash
kubectl get clusterimagepolicies.policy.sigstore.dev
```

Expected:

```text
github-policy
```

Inspect:

```bash
kubectl get clusterimagepolicy \
  github-policy \
  -o yaml
```

---

# 21. TrustRoot and ClusterImagePolicy Relationship

Conceptually:

```text
TrustRoot/github
    |
    | defines trusted verification roots/material
    v
ClusterImagePolicy/github-policy
    |
    | defines image/attestation verification policy
    v
Policy Controller admission
```

The exact generated internals are chart-controlled and should not be manually edited unless deliberately replacing the chart.

---

# 22. Do Not Hand-Edit Generated Trust Resources

Avoid:

```bash
kubectl edit trustroot github
kubectl edit clusterimagepolicy github-policy
```

for persistent changes.

These resources are GitOps/Helm-managed.

Manual changes may be reverted by Argo and create unsupported drift.

---

# 23. Protected Namespace Label

Trust verification is only meaningful where Policy Controller enforcement is enabled.

Representative namespace:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ai-platform
  labels:
    policy.sigstore.dev/include: "true"
```

Operator namespace:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ai-platform-operator-system
  labels:
    policy.sigstore.dev/include: "true"
```

---

# 24. Verify Enforcement Labels

```bash
kubectl get ns \
  ai-platform \
  ai-platform-operator-system \
  --show-labels
```

Expected both contain:

```text
policy.sigstore.dev/include=true
```

---

# 25. Positive Test — Trusted API Digest

Use a real digest produced by the source release workflow.

```bash
kubectl run attestation-positive-api \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:<REAL_TRUSTED_DIGEST>' \
  --restart=Never \
  --dry-run=server \
  -o yaml
```

Expected:

```text
request allowed
```

The test does not persist the Pod.

---

# 26. Positive Test — Trusted Operator Digest

```bash
kubectl run attestation-positive-operator \
  -n ai-platform-operator-system \
  --image='ghcr.io/anselem-okeke/ai-platform-operator@sha256:<REAL_TRUSTED_DIGEST>' \
  --restart=Never \
  --dry-run=server \
  -o yaml
```

Expected:

```text
allowed
```

---

# 27. Negative Test — Public Mutable Image

```bash
kubectl run attestation-negative-nginx \
  -n ai-platform \
  --image=nginx:latest \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

This verifies protected namespace admission.

---

# 28. Negative Test — Valid-Looking Fake Digest

Use:

```text
sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
```

Representative:

```bash
kubectl run attestation-fake-digest \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

Observed Policy Controller error:

```text
no valid bundles exist in registry
```

This is one of the strongest validation results in the trust model.

---

# 29. What the Fake-Digest Test Proves

The image reference has:

```text
approved repository
valid digest syntax
```

but lacks:

```text
trusted artifact evidence
```

Therefore:

```text
registry + digest syntax
```

does not bypass:

```text
attestation verification
```

---

# 30. Malformed Digest Test

Example:

```bash
kubectl run malformed-digest \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:1234' \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
rejected
```

This may fail before Sigstore verification because the digest itself is malformed.

Keep this test separate from the valid-looking fake-digest trust test.

---

# 31. Direct Pod Test

```bash
kubectl run direct-untrusted-pod \
  -n ai-platform \
  --image=nginx:latest \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

This ensures users cannot bypass policy by creating Pods directly.

---

# 32. Init Container Test

Representative manifest:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: attestation-init-negative
  namespace: ai-platform
spec:
  restartPolicy: Never

  initContainers:
    - name: setup
      image: nginx:latest
      command: ["sh", "-c", "echo setup"]

  containers:
    - name: api
      image: ghcr.io/anselem-okeke/ai-platform-api@sha256:<TRUSTED_DIGEST>
```

Test:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/attestation-init-negative.yaml
```

Expected:

```text
DENIED
```

---

# 33. Ephemeral Container Test

The platform also validated an untrusted ephemeral container path.

Conceptually:

```text
trusted running Pod
      |
      +--> add debug ephemeral container
             image = nginx:latest
      |
      v
DENIED
```

This prevents a debug path from bypassing supply-chain policy.

---

# 34. Native Policy and Sigstore Relationship

The platform has both:

```text
native Kubernetes validation
Sigstore Policy Controller
```

Native policy can reject:

```text
wrong registry
mutable tag
malformed digest
unapproved repository
```

Sigstore verifies:

```text
trusted evidence for the exact digest
```

Both are required for defense in depth.

---

# 35. Runtime Trust Sequence

A request may be evaluated conceptually as:

```text
image reference
    |
    +--> repository allowed?
    |
    +--> digest pinned?
    |
    +--> digest syntactically valid?
    |
    +--> attestation bundle exists?
    |
    +--> bundle is trusted for GitHub org?
    |
    +--> image matches trusted policy scope?
    |
    v
ALLOW
```

Failure at any required stage results in denial.

---

# 36. Verify Actual Live Deployments

API:

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Operator:

```bash
kubectl get deployment \
  ai-platform-operator-controller-manager \
  -n ai-platform-operator-system \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Expected:

```text
@sha256:
```

---

# 37. Verify the Digests Match GitOps

Render API:

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/api/overlays/dev \
  | grep 'image:'
```

Render operator:

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  | grep 'image:'
```

Live and Git-rendered digests should match after Argo reconciliation.

---

# 38. Verify Attestation Step Precedes GitOps Update

Inspect source release:

```bash
cd /mnt/data/ai-platform-operator

grep -nE \
  'attest|update-gitops' \
  .github/workflows/release-images.yml
```

The job dependencies should ensure:

```text
attestation success
    before
GitOps promotion PR
```

If the update job does not depend on the completed build/attestation jobs, fix the dependency graph.

---

# 39. Verify Build Job Dependency

Expected:

```yaml
update-gitops:
  needs:
    - build-operator
    - build-api
```

The build jobs themselves must include their scan/publish/attestation controls.

---

# 40. Troubleshooting: Trusted Image Is Denied

Check in this order:

```text
1. protected namespace label
2. exact image digest
3. image exists in GHCR
4. source release completed
5. provenance/SBOM attestation step succeeded
6. trust-policies Argo Application is Healthy
7. TrustRoot/github exists
8. ClusterImagePolicy/github-policy exists
9. organization matches anselem-okeke
10. image matches configured image pattern
11. Policy Controller webhook is Ready
```

---

# 41. Troubleshooting: Missing Namespace Label

Check:

```bash
kubectl get ns \
  ai-platform \
  --show-labels
```

If absent, fix the GitOps namespace manifest:

```yaml
metadata:
  labels:
    policy.sigstore.dev/include: "true"
```

Do not rely only on a live manual label.

---

# 42. Troubleshooting: No TrustRoot

```bash
kubectl get trustroots.policy.sigstore.dev
```

If `github` is missing:

```text
trust-policies Application may not have synced
AppProject may block cluster-scoped resource
Helm chart may have failed
```

Check:

```bash
argocd app get \
  trust-policies \
  --refresh
```

---

# 43. Troubleshooting: No ClusterImagePolicy

```bash
kubectl get clusterimagepolicies.policy.sigstore.dev
```

If `github-policy` is missing, inspect:

```text
Helm values
chart version
AppProject permissions
trust-policies sync errors
```

---

# 44. Troubleshooting: Wrong GitHub Organization

Inspect Argo Application/Helm values.

Expected:

```yaml
organization: anselem-okeke
```

If the release actually belongs to another GitHub owner, the current trust configuration intentionally does not trust it.

---

# 45. Troubleshooting: Wrong Image Scope

Expected:

```yaml
images:
  - "ghcr.io/anselem-okeke/ai-platform-operator**"
  - "ghcr.io/anselem-okeke/ai-platform-api**"
```

If a new first-party image is introduced, it will not automatically be trusted.

That is intentional.

Add it through reviewed GitOps change.

---

# 46. Adding a New Trusted First-Party Image

Example future Phase 8 runtime:

```text
ghcr.io/anselem-okeke/fraud-model-runtime
```

Do not immediately wildcard the entire organization.

Add a precise pattern:

```yaml
images:
  - "ghcr.io/anselem-okeke/ai-platform-operator**"
  - "ghcr.io/anselem-okeke/ai-platform-api**"
  - "ghcr.io/anselem-okeke/fraud-model-runtime**"
```

Then:

```text
review
merge
Argo sync
positive/negative admission test
```

---

# 47. Troubleshooting: Attestation Step Failed

Inspect workflow run:

```bash
gh run list \
  --workflow release-images.yml \
  --limit 10
```

Then:

```bash
gh run view <RUN_ID> \
  --log-failed
```

Look for:

```text
attest action error
OIDC/id-token permission error
subject digest missing
registry push failure
SBOM path missing
```

---

# 48. Troubleshooting: `id-token` Permission Missing

GitHub attestation workflows rely on GitHub OIDC identity.

If the workflow lacks:

```yaml
id-token: write
```

attestation can fail.

Add only the minimum required permission.

---

# 49. Troubleshooting: `attestations: write` Missing

If GitHub reports attestation permission errors, confirm:

```yaml
attestations: write
```

is available to the job/workflow.

---

# 50. Troubleshooting: Subject Digest Empty

Inspect release outputs:

```bash
grep -nE \
  'outputs:|subject-digest|digest' \
  .github/workflows/release-images.yml
```

The attestation step must receive:

```text
sha256:<64hex>
```

from the actual pushed image.

---

# 51. Troubleshooting: Attestation Created for Wrong Subject

The `subject-name` must identify the same image repository being promoted.

API:

```text
ghcr.io/anselem-okeke/ai-platform-api
```

Operator:

```text
ghcr.io/anselem-okeke/ai-platform-operator
```

Do not accidentally attest:

```text
tagged alias
different registry path
temporary build repository
```

if GitOps promotes another subject.

---

# 52. Troubleshooting: Image Exists but No Valid Bundle

Observed error:

```text
no valid bundles exist in registry
```

Possible causes:

```text
image was pushed without attestation
wrong digest promoted
attestation step failed
attestation associated with different subject
trust policy org/image scope mismatch
registry metadata unavailable
```

Use release run + GitOps digest + live digest to trace the mismatch.

---

# 53. Trace a Failing Digest End to End

Record:

```text
source SHA
release run ID
GHCR subject
digest
GitOps PR
GitOps merge commit
Argo revision
live Deployment image
admission error
```

The same digest should appear throughout.

---

# 54. Promotion Should Never Rewrite the Digest

The digest produced by the build job must be copied unchanged into GitOps.

Bad:

```text
build digest X
GitOps digest Y
```

Correct:

```text
build digest X
attest digest X
promote digest X
admit digest X
run digest X
```

---

# 55. Trust Policy Drift

Because trust resources are managed by Argo:

```text
manual edit
   |
   v
OutOfSync
   |
   v
selfHeal
```

Do not manually alter:

```text
organization
image patterns
TrustRoot
ClusterImagePolicy
```

as an operational shortcut.

---

# 56. Emergency Trust Policy Changes

Treat trust-policy broadening as a security-sensitive emergency change.

If needed:

```text
document why
make the narrowest possible change
use Git
require review
validate with test workload
revert temporary broadening
```

Do not use:

```yaml
images:
  - "**"
```

as a quick workaround.

---

# 57. Removing a Trusted Image Pattern

Before removing:

```text
confirm no live workload still uses that image
confirm rollback paths do not depend on it
confirm decommission plan
```

Otherwise future rollout/restart may fail admission.

---

# 58. Rotating Trust Configuration

The GitHub trust policy chart can evolve over time.

Safe update process:

```text
1. review upstream chart release
2. verify Policy Controller compatibility
3. update chart targetRevision in GitOps PR
4. inspect generated resource diff
5. merge
6. verify TrustRoot
7. verify ClusterImagePolicy
8. positive trusted-image test
9. negative fake-digest test
10. verify live rollout still works
```

---

# 59. Do Not Delete TrustRoot During Routine Upgrade

Deleting trust resources can create an admission outage.

Let Helm/Argo manage supported upgrades.

If CRD/schema migration is required, follow upstream upgrade guidance.

---

# 60. GitOps Validation for Trust Policy

The GitOps PR should validate the Application manifest structurally.

Before merge:

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  clusters/dev/apps \
  >/tmp/apps.yaml
```

Then:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/apps.yaml
```

---

# 61. AppProject Validation

If the trust-policy chart requires a new resource kind, update the AppProject deliberately.

Validate:

```bash
kubectl apply \
  --dry-run=server \
  -f argocd/projects/ai-platform.yaml
```

Then bootstrap-apply.

Do not add wildcard cluster access merely to unblock sync.

---

# 62. Positive Test Should Use Server Dry Run

Preferred:

```text
--dry-run=server
```

Why:

```text
executes real admission
does not persist test object
safe for repeated validation
```

This is ideal for trust-policy testing.

---

# 63. Negative Tests Should Use Fake Data

Never use a real secret or compromised artifact to test denial.

Use:

```text
nginx:latest
synthetic fake SHA-256
dummy init container
```

---

# 64. Trust Validation Test Matrix

| Test | Expected |
|---|---|
| Trusted API digest | Allowed |
| Trusted operator digest | Allowed |
| Public mutable image | Denied |
| Wrong repository digest | Denied |
| Malformed digest | Rejected |
| Valid-looking fake digest | Denied |
| Untrusted init container | Denied |
| Untrusted ephemeral container | Denied |
| Direct untrusted Pod | Denied |

---

# 65. Operational Checklist

```text
[ ] trust-policies Application Synced
[ ] trust-policies Application Healthy
[ ] TrustRoot/github exists
[ ] ClusterImagePolicy/github-policy exists
[ ] organization = anselem-okeke
[ ] API image pattern present
[ ] operator image pattern present
[ ] protected namespaces labelled
[ ] trusted API digest allowed
[ ] trusted operator digest allowed
[ ] nginx:latest denied
[ ] fake digest denied
[ ] init-container bypass denied
[ ] ephemeral-container bypass denied
[ ] live workloads use sha256 digests
```

---

# 66. Security Checklist

```text
[ ] GitHub attestation action pinned
[ ] release workflow permissions minimal
[ ] id-token write only where required
[ ] attestations write only where required
[ ] subject digest comes from pushed image
[ ] GitOps promotes exact digest
[ ] trust organization narrowly scoped
[ ] image patterns narrowly scoped
[ ] no broad trust wildcard
[ ] namespace enforcement explicit
[ ] fake valid digest denied
[ ] no manual live trust edits
```

---

# 67. Rebuild from Zero

```text
[ ] install Policy Controller
[ ] verify CRDs
[ ] verify webhook
[ ] add GitHub trust-policy repo to AppProject
[ ] allow TrustRoot
[ ] allow ClusterImagePolicy
[ ] bootstrap-apply AppProject
[ ] create trust-policies Argo Application
[ ] pin chart v0.7.0
[ ] configure organization anselem-okeke
[ ] configure API image pattern
[ ] configure operator image pattern
[ ] merge GitOps PR
[ ] manually sync root if Application is new
[ ] wait for trust-policies Healthy
[ ] verify TrustRoot/github
[ ] verify ClusterImagePolicy/github-policy
[ ] label protected namespaces
[ ] verify source release attestation steps
[ ] verify trusted API digest allowed
[ ] verify trusted operator digest allowed
[ ] verify nginx:latest denied
[ ] verify fake digest denied
[ ] verify init container denied
[ ] verify ephemeral container denied
[ ] document final state
```

---

# 68. Known Implementation Facts

Validated:

```text
GitHub attestation action:
actions/attest

Pinned action SHA:
508db95dd578ae2727ebd6217d5ba78e4fbda05d

Trust-policy chart:
v0.7.0

Trust-policy repository:
ghcr.io/github/artifact-attestations-helm-charts

Policy Controller namespace:
cosign-system

Organization:
anselem-okeke

Trusted images:
ghcr.io/anselem-okeke/ai-platform-operator**
ghcr.io/anselem-okeke/ai-platform-api**

TrustRoot:
github

ClusterImagePolicy:
github-policy

Runtime trust:
exact digest

Empirical fake-digest result:
no valid bundles exist in registry
```

---

# 69. What Must Be Verified from the Actual Repository/Cluster

Do not invent:

```text
exact current attestation step IDs
exact build output names
exact current workflow permission block
exact generated TrustRoot content
exact generated ClusterImagePolicy internals
exact real trusted digest used for positive tests
exact current Argo Application YAML
```

Inspect:

```text
/mnt/data/ai-platform-operator/.github/workflows/release-images.yml
/mnt/data/ai-platform-gitops/clusters/dev/apps/
live Kubernetes trust resources
```

---

# 70. Official References

GitHub Artifact Attestations:

```text
https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations
```

GitHub attestation action:

```text
https://github.com/actions/attest
```

GitHub Artifact Attestations Helm charts:

```text
https://github.com/github/artifact-attestations-helm-charts
```

Sigstore Policy Controller:

```text
https://docs.sigstore.dev/policy-controller/overview/
```

Sigstore Policy Controller repository:

```text
https://github.com/sigstore/policy-controller
```

Kubernetes admission webhooks:

```text
https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/
```

GitHub Actions permissions:

```text
https://docs.github.com/actions/using-jobs/assigning-permissions-to-jobs
```

---

# 71. Related AI Platform Documentation

```text
019-source-ci-pipeline.md
020-container-build-and-hardening.md
021-container-vulnerability-scanning.md
022-sbom-and-provenance.md
023-github-container-registry.md
025-image-digest-update-workflow.md
028-promotion-workflow.md
031-sigstore-policy-controller.md
033-native-image-validation-policy.md
034-admission-policy-testing.md
035-policy-controller-observability.md
036-policy-controller-alerting.md
039-software-supply-chain-security.md
040-end-to-end-delivery-workflow.md
041-validation-and-security-tests.md
043-troubleshooting-guide.md
045-command-reference.md
047-design-decisions.md
