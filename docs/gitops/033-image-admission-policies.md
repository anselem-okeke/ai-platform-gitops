# Image Admission Policies

## Purpose

This document is the **reproducible implementation guide** for the AI Platform's native Kubernetes image-admission controls.

These policies are the first runtime gate for container image references.

Their job is to reject workloads that try to use:

```text
unapproved image repositories
mutable tags
missing digests
malformed SHA-256 digests
untrusted image forms in regular containers
untrusted image forms in init containers
untrusted image forms in ephemeral containers
```

The native admission layer works together with Sigstore Policy Controller.

The relationship is:

```text
Kubernetes workload request
        |
        v
Native ValidatingAdmissionPolicy
        |
        +--> approved image repository?
        +--> immutable @sha256 digest?
        +--> full 64-character SHA-256?
        +--> all container paths covered?
        |
        +--> NO  -> DENY
        |
        v
Sigstore Policy Controller
        |
        +--> trusted attestation exists for exact digest?
        |
        +--> NO  -> DENY
        |
        v
ALLOW
```

The native policies answer:

```text
"Is this image reference structurally allowed?"
```

Sigstore answers:

```text
"Is this exact digest backed by trusted release evidence?"
```

Both layers are required.

---

# 1. Scope

The policies protect first-party AI Platform workloads.

Current first-party image repositories:

```text
ghcr.io/anselem-okeke/ai-platform-api
ghcr.io/anselem-okeke/ai-platform-operator
```

Protected namespaces include:

```text
ai-platform
ai-platform-operator-system
```

The policies must evaluate:

```text
Pods
workload-generated Pod templates
regular containers
initContainers
ephemeralContainers
```

---

# 2. Why Native Admission Exists in Addition to Sigstore

A Sigstore policy can verify trusted evidence, but native Kubernetes policy provides a fast structural boundary.

The native layer can reject:

```text
nginx:latest
docker.io/example/app:v1
ghcr.io/anselem-okeke/ai-platform-api:dev
ghcr.io/anselem-okeke/ai-platform-api@sha256:1234
```

before deeper trust verification.

This produces defense in depth:

```text
repository allowlist
      +
immutable digest
      +
attestation trust
```

---

# 3. Core Policy Requirements

The admission layer should enforce these invariants:

```text
1. image must come from an approved repository namespace
2. image must use @sha256:
3. digest must contain exactly 64 hexadecimal characters
4. regular containers must comply
5. init containers must comply
6. ephemeral containers must comply
7. direct Pod creation must comply
8. higher-level workload Pod templates must comply
9. policy failure must deny, not silently allow
```

---

# 4. ValidatingAdmissionPolicy

The platform uses Kubernetes native admission policy resources.

API group:

```text
admissionregistration.k8s.io
```

Resources:

```text
ValidatingAdmissionPolicy
ValidatingAdmissionPolicyBinding
```

These resources allow Kubernetes to evaluate CEL expressions directly at admission time.

---

# 5. Why ValidatingAdmissionPolicy

Advantages:

```text
no custom admission server required
native Kubernetes API
CEL-based expressions
declarative
GitOps-managed
failure behavior explicit
namespace/resource matching explicit
```

This makes the policy easier to audit than an opaque custom webhook.

---

# 6. Policy Failure Behavior

Use:

```yaml
failurePolicy: Fail
```

Representative snippet:

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionPolicy
metadata:
  name: ai-platform-image-policy
spec:
  failurePolicy: Fail
```

Meaning:

```text
if policy evaluation cannot safely complete
    -> deny
```

For an enforcement policy, fail-open would weaken the security boundary.

---

# 7. Approved Repository Model

Current first-party image prefixes:

```text
ghcr.io/anselem-okeke/ai-platform-api@
ghcr.io/anselem-okeke/ai-platform-operator@
```

A broader organization prefix such as:

```text
ghcr.io/anselem-okeke/
```

may be acceptable only if the policy intentionally trusts every first-party runtime under that organization.

For the strongest current model, use exact repository allowlists where practical.

---

# 8. Full SHA-256 Digest Requirement

Valid final image form:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:<64hex>
```

Example shape:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```

Invalid:

```text
ghcr.io/anselem-okeke/ai-platform-api:latest
ghcr.io/anselem-okeke/ai-platform-api:v1
ghcr.io/anselem-okeke/ai-platform-api@sha256:1234
docker.io/anselem-okeke/ai-platform-api@sha256:<digest>
```

---

# 9. Representative CEL Regex

A useful structural pattern is:

```text
^ghcr\.io/anselem-okeke/(ai-platform-api|ai-platform-operator)@sha256:[0-9a-f]{64}$
```

This is representative of the intended validation logic.

The exact production CEL expression should be taken from the committed GitOps manifest.

---

# 10. Representative Pod Policy

A compact Pod-level policy can look like:

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionPolicy
metadata:
  name: ai-platform-pod-images
spec:
  failurePolicy: Fail

  matchConstraints:
    resourceRules:
      - apiGroups: [""]
        apiVersions: ["v1"]
        operations: ["CREATE", "UPDATE"]
        resources: ["pods"]

  validations:
    - expression: >-
        object.spec.containers.all(c,
          c.image.matches(
            '^ghcr\.io/anselem-okeke/(ai-platform-api|ai-platform-operator)@sha256:[0-9a-f]{64}$'
          )
        )
      message: >-
        All containers must use an approved AI Platform GHCR image
        pinned to a full SHA-256 digest.
```

This protects regular containers.

It is **not enough by itself** because init and ephemeral containers also need coverage.

---

# 11. Init Container Coverage

Init containers are optional.

A safe CEL expression should handle absence.

Representative:

```yaml
- expression: >-
    !has(object.spec.initContainers) ||
    object.spec.initContainers.all(c,
      c.image.matches(
        '^ghcr\.io/anselem-okeke/(ai-platform-api|ai-platform-operator)@sha256:[0-9a-f]{64}$'
      )
    )
  message: >-
    All init containers must use an approved AI Platform GHCR image
    pinned to a full SHA-256 digest.
```

This prevents bypass through:

```yaml
initContainers:
  - image: nginx:latest
```

---

# 12. Ephemeral Container Coverage

Ephemeral containers are another bypass path.

Representative:

```yaml
- expression: >-
    !has(object.spec.ephemeralContainers) ||
    object.spec.ephemeralContainers.all(c,
      c.image.matches(
        '^ghcr\.io/anselem-okeke/(ai-platform-api|ai-platform-operator)@sha256:[0-9a-f]{64}$'
      )
    )
  message: >-
    All ephemeral containers must use an approved AI Platform GHCR image
    pinned to a full SHA-256 digest.
```

This matters for:

```text
kubectl debug
ephemeral debugging containers
```

---

# 13. Why `has(...)` Matters

Optional Kubernetes fields may not exist.

Without safe handling, a CEL expression can fail unexpectedly.

Good pattern:

```text
!has(object.spec.initContainers) || ...
```

Meaning:

```text
if field absent -> valid
if field present -> validate all entries
```

---

# 14. Direct Pod Coverage

Direct Pod admission is critical.

Without it, a user might bypass Deployment-level validation by running:

```bash
kubectl run ...
```

The Pod policy ensures direct Pod creation is evaluated.

---

# 15. Higher-Level Workload Coverage

Pods are commonly created through:

```text
Deployment
StatefulSet
DaemonSet
Job
CronJob
```

A robust platform should ensure Pod templates in these workload APIs are also structurally validated.

There are two approaches:

```text
A. validate only resulting Pods
B. validate both workload templates and resulting Pods
```

The stronger approach is:

```text
both
```

because invalid desired state can be rejected earlier.

---

# 16. Representative Deployment Policy

Representative:

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionPolicy
metadata:
  name: ai-platform-deployment-images
spec:
  failurePolicy: Fail

  matchConstraints:
    resourceRules:
      - apiGroups: ["apps"]
        apiVersions: ["v1"]
        operations: ["CREATE", "UPDATE"]
        resources: ["deployments"]

  validations:
    - expression: >-
        object.spec.template.spec.containers.all(c,
          c.image.matches(
            '^ghcr\.io/anselem-okeke/(ai-platform-api|ai-platform-operator)@sha256:[0-9a-f]{64}$'
          )
        )
      message: >-
        Deployment containers must use approved digest-pinned AI Platform images.
```

Add equivalent checks for:

```text
object.spec.template.spec.initContainers
```

as required.

Ephemeral containers are primarily a Pod subresource concern rather than a normal Deployment template field.

---

# 17. Workload Resource Coverage Strategy

Recommended resource set:

```text
pods
deployments
statefulsets
daemonsets
jobs
cronjobs
```

Exact coverage depends on the policy manifests actually committed in GitOps.

Do not claim a resource type is protected until its policy path is confirmed.

---

# 18. Representative Binding

Policy logic does not enforce anything until a binding activates it.

Representative:

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionPolicyBinding
metadata:
  name: ai-platform-pod-images
spec:
  policyName: ai-platform-pod-images

  validationActions:
    - Deny

  matchResources:
    namespaceSelector:
      matchExpressions:
        - key: policy.sigstore.dev/include
          operator: In
          values:
            - "true"
```

This reuses the same protected namespace label used by Sigstore.

---

# 19. Why Reuse the Namespace Label

Using:

```text
policy.sigstore.dev/include=true
```

for both structural and provenance enforcement creates a single protected-namespace boundary.

That means:

```text
namespace opted into secure runtime
    |
    +--> native image policy applies
    +--> Sigstore applies
```

This reduces configuration drift.

If the actual native policy uses another selector, document the real selector instead.

---

# 20. Validation Actions

For enforcement:

```yaml
validationActions:
  - Deny
```

Do not leave production enforcement in:

```text
Audit
Warn
```

unless deliberately running a staged rollout.

---

# 21. Audit/Warning Rollout Pattern

A safe rollout can be:

```text
1. Audit
2. Warn
3. observe violations
4. correct workloads
5. Deny
```

However, the current project has already moved to actual denial behavior for protected workloads.

Do not weaken it back to warning-only without a reason.

---

# 22. Namespace Manifest Snippet

Protected namespace example:

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

# 23. GitOps Layout

Current policy resources belong under:

```text
platform/policies/base/
```

with environment composition under:

```text
platform/policies/overlays/dev/
```

Representative:

```text
platform/policies/
├── base/
│   ├── kustomization.yaml
│   ├── image-policy.yaml
│   └── image-policy-binding.yaml
└── overlays/
    └── dev/
        └── kustomization.yaml
```

The exact filenames must be taken from the actual repository.

---

# 24. Representative Kustomization

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - image-policy.yaml
  - image-policy-binding.yaml
```

If multiple policy resources exist, list each explicitly.

---

# 25. GitOps Application

Existing child Application:

```text
policies
```

should point at:

```text
platform/policies/overlays/dev
```

Representative:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: ai-platform-policies
  namespace: argocd
spec:
  project: ai-platform

  source:
    repoURL: https://github.com/anselem-okeke/ai-platform-gitops.git
    targetRevision: main
    path: platform/policies/overlays/dev

  destination:
    server: https://kubernetes.default.svc
```

Use the actual child Application name/path from GitOps.

---

# 26. AppProject Permissions

AppProject must allow:

```text
ValidatingAdmissionPolicy
ValidatingAdmissionPolicyBinding
```

Representative allowlist:

```yaml
clusterResourceWhitelist:
  - group: admissionregistration.k8s.io
    kind: ValidatingAdmissionPolicy

  - group: admissionregistration.k8s.io
    kind: ValidatingAdmissionPolicyBinding
```

Do not use wildcard cluster permissions if exact kinds are sufficient.

---

# 27. Bootstrap Apply AppProject

Because AppProject is bootstrap-managed:

```bash
cd /mnt/data/ai-platform-gitops

kubectl apply \
  --dry-run=server \
  -f argocd/projects/ai-platform.yaml
```

Then:

```bash
kubectl apply \
  -f argocd/projects/ai-platform.yaml
```

---

# 28. Render Policy Manifests

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/policies/overlays/dev \
  >/tmp/policies.yaml
```

Expected:

```text
successful render
```

---

# 29. Validate with kubeconform

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/policies.yaml
```

Depending on kubeconform schema availability for the exact Kubernetes version, admissionregistration v1 resources should validate.

---

# 30. Server-Side Dry Run

Because these are cluster-scoped API resources, validate against the real API server:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/policies.yaml
```

Expected:

```text
configured/created (server dry run)
```

---

# 31. Argo Validation

```bash
argocd app get \
  ai-platform-policies \
  --refresh
```

If the actual Application is named simply:

```text
policies
```

use that name.

Expected:

```text
Synced
Healthy
```

---

# 32. List Native Policies

```bash
kubectl get validatingadmissionpolicies
```

Then:

```bash
kubectl get validatingadmissionpolicybindings
```

Inspect:

```bash
kubectl get validatingadmissionpolicy \
  <POLICY_NAME> \
  -o yaml
```

---

# 33. Verify Binding

```bash
kubectl get validatingadmissionpolicybinding \
  <BINDING_NAME> \
  -o yaml
```

Confirm:

```text
policyName
validationActions
namespaceSelector
```

---

# 34. Positive Test — Trusted API Digest

Use a real approved digest:

```bash
kubectl run native-policy-positive \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:<REAL_DIGEST>' \
  --restart=Never \
  --dry-run=server \
  -o yaml
```

Expected from native policy:

```text
structurally allowed
```

The request must still pass Sigstore trust verification.

---

# 35. Negative Test — Mutable Tag

```bash
kubectl run native-policy-tag-negative \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api:latest' \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

Reason:

```text
no immutable @sha256 digest
```

---

# 36. Negative Test — Wrong Registry

```bash
kubectl run native-policy-registry-negative \
  -n ai-platform \
  --image='docker.io/library/nginx@sha256:<VALID_64_HEX_DIGEST>' \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

Reason:

```text
unapproved repository
```

Use a synthetic 64-hex string if only testing policy syntax.

---

# 37. Negative Test — Short Digest

```bash
kubectl run native-policy-short-digest \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:1234' \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
rejected
```

The image parser or policy may reject first.

---

# 38. Negative Test — Other GHCR Repository

If exact repository allowlisting is used:

```bash
kubectl run native-policy-other-ghcr \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/unapproved-service@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

If the actual policy intentionally allows the whole organization prefix, this expectation changes.

Verify the committed policy.

---

# 39. Init Container Negative Test

Create:

```bash
cat >/tmp/native-bad-init.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: native-bad-init
  namespace: ai-platform
spec:
  restartPolicy: Never

  initContainers:
    - name: bad-init
      image: nginx:latest
      command: ["sh", "-c", "echo init"]

  containers:
    - name: app
      image: ghcr.io/anselem-okeke/ai-platform-api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
EOF
```

Apply:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/native-bad-init.yaml
```

Expected:

```text
DENIED
```

Even though the main container has a digest-shaped reference, the untrusted init container must fail policy.

---

# 40. Why the Synthetic Main Digest Is Fine for This Negative Test

The purpose of the test is:

```text
prove init-container structural policy triggers
```

Sigstore may also reject the synthetic main digest.

If you need to isolate only the native init-container rule, use a real trusted main image digest.

---

# 41. Ephemeral Container Negative Test

Ephemeral containers are added through the Pod ephemeralcontainers subresource.

Conceptually:

```text
trusted Pod
   |
   +--> add ephemeral container:
          nginx:latest
   |
   v
DENIED
```

The actual test command depends on Kubernetes/kubectl support.

One approach is:

```bash
kubectl debug \
  -n ai-platform \
  <TRUSTED_POD> \
  --image=nginx:latest
```

Expected:

```text
DENIED
```

Perform only against a disposable test Pod.

---

# 42. Direct Pod Test

```bash
kubectl run native-direct-pod \
  -n ai-platform \
  --image=nginx:latest \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

---

# 43. Deployment Negative Test

Representative:

```bash
cat >/tmp/native-bad-deployment.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: native-bad-deployment
  namespace: ai-platform
spec:
  replicas: 1
  selector:
    matchLabels:
      app: native-bad-deployment
  template:
    metadata:
      labels:
        app: native-bad-deployment
    spec:
      containers:
        - name: app
          image: nginx:latest
EOF
```

Test:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/native-bad-deployment.yaml
```

Expected:

```text
DENIED
```

if Deployment template policies are implemented.

If only Pod admission is implemented, the dry-run behavior can differ because no Pod is actually created during Deployment dry-run.

This is why workload-template coverage should be verified explicitly.

---

# 44. CronJob Consideration

CronJob image path:

```text
object.spec.jobTemplate.spec.template.spec.containers
```

Representative policy logic must account for the deeper object structure.

Do not copy Deployment CEL directly to CronJob.

---

# 45. Job Consideration

Job image path:

```text
object.spec.template.spec.containers
```

Same general structure as Deployment Pod template.

---

# 46. StatefulSet and DaemonSet

Image path:

```text
object.spec.template.spec.containers
```

with equivalent init-container handling.

---

# 47. Policy Messages

Admission errors should be actionable.

Good:

```text
All containers must use an approved AI Platform GHCR image pinned to a full SHA-256 digest.
```

Bad:

```text
policy failed
```

Clear messages reduce troubleshooting time.

---

# 48. Policy Naming

Use stable names that describe intent.

Examples:

```text
ai-platform-pod-images
ai-platform-workload-images
require-approved-digest-images
```

Avoid names tied to temporary implementation details.

---

# 49. One Policy vs Multiple Policies

Two reasonable designs:

```text
single policy
  -> many resourceRules + validations

multiple policies
  -> Pod policy
  -> workload-template policy
```

Multiple policies can be easier to troubleshoot.

The actual platform structure should be documented from Git once inspected.

---

# 50. `matchConstraints`

`matchConstraints` determines which API resources the policy evaluates.

Representative Pod rule:

```yaml
matchConstraints:
  resourceRules:
    - apiGroups: [""]
      apiVersions: ["v1"]
      operations: ["CREATE", "UPDATE"]
      resources: ["pods"]
```

---

# 51. Why Include UPDATE

Image changes can occur during:

```text
workload update
Pod subresource operations
template updates
```

A CREATE-only policy may leave update paths unprotected.

Use:

```text
CREATE
UPDATE
```

where appropriate.

---

# 52. Namespace Selection

Use binding-level namespace selection rather than hardcoding namespace names inside CEL when practical.

Representative:

```yaml
matchResources:
  namespaceSelector:
    matchLabels:
      policy.sigstore.dev/include: "true"
```

This keeps:

```text
policy logic
```

separate from:

```text
where enforcement applies
```

---

# 53. Why Not Protect `kube-system` Immediately

System components often use:

```text
different registries
distribution-managed images
bootstrap images
```

Applying a strict first-party image policy globally could break the cluster.

Use deliberate namespace scope.

---

# 54. Adding a New Protected Namespace

GitOps namespace manifest:

```yaml
metadata:
  labels:
    policy.sigstore.dev/include: "true"
```

Before merge:

```text
inventory all workloads in namespace
verify their images satisfy policy
verify Sigstore trust
```

Then enable enforcement.

---

# 55. Adding a New First-Party Image Repository

Suppose Phase 8 adds:

```text
ghcr.io/anselem-okeke/fraud-model-runtime
```

If native policy uses exact repository allowlisting, update the CEL regex/prefix list.

Representative regex:

```text
^ghcr\.io/anselem-okeke/(ai-platform-api|ai-platform-operator|fraud-model-runtime)@sha256:[0-9a-f]{64}$
```

Then update Sigstore trust policy separately.

Both layers must change.

---

# 56. Native Policy Update Does Not Automatically Update Sigstore

This is important.

If native policy allows:

```text
fraud-model-runtime
```

but Sigstore trust policy does not, the image remains denied by the second layer.

That is correct.

---

# 57. Sigstore Update Does Not Automatically Update Native Policy

Likewise:

```text
Sigstore trusts image
```

does not mean native CEL policy will allow its repository/reference form.

Both controls must agree.

---

# 58. Failure Scenario — Policy Resource Rejected by API Server

Check Kubernetes version:

```bash
kubectl version
```

Validated cluster:

```text
Kubernetes v1.36.1
```

Ensure:

```text
admissionregistration.k8s.io/v1
ValidatingAdmissionPolicy
```

is supported.

---

# 59. Failure Scenario — CEL Compile Error

The API server may reject the policy with an expression compilation error.

Use:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/policies.yaml
```

Read the exact CEL error.

Common issues:

```text
wrong object path
optional field handling
unsupported CEL function
regex escaping
type mismatch
```

---

# 60. Failure Scenario — Policy Exists but Does Not Enforce

Check:

```text
binding exists
binding references correct policyName
validationActions contains Deny
namespace selector matches
resourceRules match requested resource
operation included
```

Inspect:

```bash
kubectl get validatingadmissionpolicybinding \
  <BINDING> \
  -o yaml
```

---

# 61. Failure Scenario — Policy Applies to Wrong Namespace

Check namespace labels:

```bash
kubectl get ns \
  --show-labels
```

Check binding selector.

Do not hardcode a broad selector accidentally.

---

# 62. Failure Scenario — Valid Image Is Denied

Check exact reference:

```text
registry path
repository name
@sha256 separator
64-character digest
lowercase/uppercase regex behavior
```

Then determine whether the denial came from:

```text
native ValidatingAdmissionPolicy
or
Sigstore Policy Controller
```

The error message usually identifies the source.

---

# 63. Failure Scenario — Invalid Image Is Allowed

Treat as a security incident/control failure.

Check:

```text
policy exists
binding exists
Deny action enabled
namespace matches
resource kind matches
container path covered
CEL expression correct
```

Add a regression test after fixing.

---

# 64. Failure Scenario — Init Container Bypass

If:

```text
main container compliant
init container untrusted
request allowed
```

the policy is incomplete.

Add:

```text
initContainers
```

coverage.

---

# 65. Failure Scenario — Ephemeral Container Bypass

If an untrusted debug image is allowed, ensure policy covers:

```text
spec.ephemeralContainers
```

and the relevant operation/subresource behavior.

---

# 66. Failure Scenario — Workload Template Allowed but Pod Later Denied

This can happen if only Pod-level policy is authoritative.

Result:

```text
Deployment created
but Pod creation denied
```

This is secure but operationally less friendly.

Add workload-template validation so the user receives failure earlier.

---

# 67. Failure Scenario — Workload Template Denied but Pod Policy Missing

This is also incomplete.

A direct Pod could bypass Deployment validation.

Keep Pod-level enforcement.

---

# 68. Failure Scenario — Regex Too Broad

Bad:

```text
^ghcr\.io/anselem-okeke/.+@
```

if the intent is only two trusted repositories.

This may allow unrelated organization images through the native layer.

Prefer exact repositories when the set is small.

---

# 69. Failure Scenario — Regex Too Narrow

If a valid repository path changes intentionally, the policy may deny it.

Make repository additions through reviewed GitOps changes.

Do not broaden temporarily with `.*` unless justified.

---

# 70. Failure Scenario — Digest Regex Accepts Wrong Length

Ensure:

```text
{64}
```

not:

```text
+
*
{1,64}
```

The SHA-256 hex digest length is exactly 64 characters.

---

# 71. Lowercase Hex

Registry digests are normally lowercase hex.

A strict regex can use:

```text
[0-9a-f]{64}
```

If policy intentionally accepts uppercase, use:

```text
[0-9a-fA-F]{64}
```

Match actual OCI digest normalization behavior.

---

# 72. GitOps Validation

The policy overlay is rendered in:

```text
.github/workflows/validate.yml
```

Current path:

```text
platform/policies/overlays/dev
```

This ensures admission policy syntax/layout is checked before merge.

---

# 73. Local Validation Workflow

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/policies/overlays/dev \
  >/tmp/policies.yaml

kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/policies.yaml

kubectl apply \
  --dry-run=server \
  -f /tmp/policies.yaml

git diff --check
```

---

# 74. Argo Sync

After merge:

```bash
argocd app get \
  ai-platform-policies \
  --refresh
```

or the actual Application name.

Wait:

```bash
argocd app wait \
  ai-platform-policies \
  --sync \
  --health \
  --timeout 300
```

---

# 75. Verify Live Policy After Argo Sync

```bash
kubectl get validatingadmissionpolicies
```

```bash
kubectl get validatingadmissionpolicybindings
```

Inspect generation/revision if needed.

---

# 76. Policy Rollback

If a new policy breaks legitimate workloads:

```text
do not manually delete policy as first response
```

Prefer:

```text
Git revert
```

then let Argo reconcile.

---

# 77. Emergency Policy Rollback

If policy causes a broad outage and Git recovery is too slow:

```text
temporary emergency action may be required
```

but document:

```text
exact resource changed
time
reason
authorized responder
Git correction
re-enable validation
```

---

# 78. Do Not Leave Policy Disabled

After emergency recovery:

```text
restore Deny enforcement
rerun positive test
rerun negative test
```

A forgotten disabled admission policy is a serious control gap.

---

# 79. Security Test Matrix

| Test | Native Policy Expected |
|---|---|
| Approved API digest | Allow structurally |
| Approved operator digest | Allow structurally |
| `nginx:latest` | Deny |
| Approved repo with `:latest` | Deny |
| Wrong registry with digest | Deny |
| Short digest | Deny/reject |
| Unapproved GHCR repo | Deny if exact allowlist |
| Bad init container | Deny |
| Bad ephemeral container | Deny |
| Direct Pod bad image | Deny |
| Deployment template bad image | Deny if workload-template policy exists |

---

# 80. Combined Admission Test Matrix

| Test | Native Policy | Sigstore | Final |
|---|---:|---:|---:|
| Trusted approved digest | Pass | Pass | Allow |
| Approved repo + fake valid digest | Pass structurally | Fail | Deny |
| Approved repo + mutable tag | Fail | Not relevant | Deny |
| Wrong repo + valid digest | Fail | Not relevant | Deny |
| Trusted main + bad init | Fail | Possibly pass main | Deny |
| Trusted Pod + bad ephemeral | Fail | Possibly pass main | Deny |

This table explains why both layers exist.

---

# 81. Operational Checklist

```text
[ ] ValidatingAdmissionPolicy exists
[ ] ValidatingAdmissionPolicyBinding exists
[ ] failurePolicy = Fail
[ ] validationActions includes Deny
[ ] namespace selector matches protected namespaces
[ ] Pod CREATE covered
[ ] Pod UPDATE covered where required
[ ] regular containers covered
[ ] initContainers covered
[ ] ephemeralContainers covered
[ ] workload templates covered as implemented
[ ] approved image repository rules correct
[ ] full sha256 digest required
[ ] negative tests deny
[ ] positive trusted digest passes structural policy
```

---

# 82. Security Review Checklist

```text
[ ] no broad registry wildcard
[ ] no mutable tags accepted
[ ] digest exactly 64 hex
[ ] fail-open not used
[ ] direct Pod bypass blocked
[ ] init-container bypass blocked
[ ] ephemeral-container bypass blocked
[ ] namespace scope intentional
[ ] AppProject least privilege
[ ] GitOps controls policy changes
[ ] Sigstore remains second trust layer
```

---

# 83. Rebuild from Zero

```text
[ ] verify Kubernetes supports ValidatingAdmissionPolicy
[ ] decide protected namespace selector
[ ] decide exact approved repositories
[ ] create Pod image policy
[ ] enforce regular containers
[ ] enforce init containers
[ ] enforce ephemeral containers
[ ] create workload-template policy if required
[ ] create binding
[ ] set validationActions: Deny
[ ] set failurePolicy: Fail
[ ] add resources to platform/policies/base
[ ] include in Kustomization
[ ] ensure AppProject allows policy kinds
[ ] render GitOps overlay
[ ] kubeconform validate
[ ] server dry-run policy manifests
[ ] merge GitOps PR
[ ] verify Argo sync
[ ] test approved API digest
[ ] test approved operator digest
[ ] deny nginx:latest
[ ] deny mutable first-party tag
[ ] deny wrong registry
[ ] deny short digest
[ ] deny bad init
[ ] deny bad ephemeral
[ ] deny direct Pod bypass
[ ] validate workload-template behavior
[ ] document exact policy names and CEL
```

---

# 84. Known Implementation Facts

Validated project facts:

```text
Native image validation:
implemented

Policy resource type:
Kubernetes admission policy resources

Protected image identity:
full sha256 digest

Approved first-party repositories:
ghcr.io/anselem-okeke/ai-platform-api
ghcr.io/anselem-okeke/ai-platform-operator

Container paths validated:
regular containers
init containers
ephemeral containers

Direct Pod test:
validated

Negative untrusted image:
validated

Fake valid digest:
native syntax can pass, Sigstore denies

Protected namespaces:
ai-platform
ai-platform-operator-system
```

---

# 85. What Must Be Verified from the Actual Repository

The current runtime environment used for this documentation repair does not contain the mounted GitOps repository, so the following must be read from the real GitOps repository before claiming exact manifest parity:

```text
exact policy resource names
exact binding names
exact CEL expressions
exact namespace selector
exact resourceRules
exact workload kinds covered
exact filenames
exact Kustomization layout
exact Argo Application name
```

Inspect:

```bash
cd /mnt/data/ai-platform-gitops

find platform/policies \
  -maxdepth 3 \
  -type f \
  -print \
  | sort

grep -RIn \
  'ValidatingAdmissionPolicy\|ValidatingAdmissionPolicyBinding\|validations:\|validationActions:\|sha256' \
  platform/policies
```

Then update this guide's representative snippets with the exact committed manifest if necessary.

---

# 86. Official References

Kubernetes ValidatingAdmissionPolicy:

```text
https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/
```

Kubernetes CEL:

```text
https://kubernetes.io/docs/reference/using-api/cel/
```

Kubernetes admission control:

```text
https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/
```

Kubernetes container images:

```text
https://kubernetes.io/docs/concepts/containers/images/
```

Argo CD:

```text
https://argo-cd.readthedocs.io/
```

Kustomize:

```text
https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/
```

---

# 87. Related AI Platform Documentation

```text
026-gitops-pr-validation.md
030-argocd-sync-selfheal-and-prune.md
031-sigstore-policy-controller.md
032-github-attestation-trust.md
034-admission-policy-testing.md
035-policy-controller-observability.md
036-policy-controller-alerting.md
039-software-supply-chain-security.md
040-end-to-end-delivery-workflow.md
041-validation-and-security-tests.md
043-troubleshooting-guide.md
045-command-reference.md
047-design-decisions.md
