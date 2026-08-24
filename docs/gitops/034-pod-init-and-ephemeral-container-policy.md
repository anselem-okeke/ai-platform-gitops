# Pod, Init Container, and Ephemeral Container Policy

## Purpose

This document is the **reproducible implementation guide** for closing container-image admission bypass paths in the AI Platform.

A policy that validates only:

```text
spec.containers[]
```

is incomplete.

Kubernetes Pods can also execute images through:

```text
spec.initContainers[]
spec.ephemeralContainers[]
```

and higher-level workload controllers can carry images inside Pod templates.

This guide explains how the platform protects:

```text
regular containers
init containers
ephemeral containers
direct Pods
Deployment Pod templates
StatefulSet Pod templates
DaemonSet Pod templates
Job Pod templates
CronJob Pod templates
```

and how those structural controls work together with Sigstore provenance verification.

The security model is:

```text
Kubernetes request
      |
      v
Native admission policy
      |
      +--> spec.containers[]
      +--> spec.initContainers[]
      +--> spec.ephemeralContainers[]
      +--> workload Pod templates
      |
      +--> wrong repo/tag/digest -> DENY
      |
      v
Sigstore Policy Controller
      |
      +--> exact digest has trusted evidence?
      |
      +--> NO -> DENY
      |
      v
ALLOW
```

---

# 1. Why This Document Exists Separately from 033

`033-image-admission-policies.md` defines the overall image-admission architecture.

This document goes deeper into the specific bypass surfaces around Pod container types.

The split is:

```text
033
  -> policy architecture
  -> approved repository
  -> digest pinning
  -> ValidatingAdmissionPolicy / Binding
  -> namespace scope

034
  -> regular container path
  -> init-container path
  -> ephemeral-container path
  -> direct Pod bypass
  -> workload-template paths
  -> kubectl debug behavior
  -> focused positive/negative tests
```

---

# 2. Container Execution Paths in a Pod

A Pod can contain:

```yaml
spec:
  containers: []
  initContainers: []
  ephemeralContainers: []
```

Each of these can cause an image to execute in the protected namespace.

Therefore every path must be validated.

---

# 3. Regular Containers

Regular containers live at:

```text
object.spec.containers
```

Representative Pod:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: example
spec:
  containers:
    - name: app
      image: ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>
```

---

# 4. Init Containers

Init containers live at:

```text
object.spec.initContainers
```

Representative:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: example
spec:
  initContainers:
    - name: setup
      image: ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>

  containers:
    - name: app
      image: ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>
```

Init containers run before normal containers.

They can:

```text
write files
download payloads
modify shared volumes
prepare credentials
alter startup state
```

An untrusted init image can compromise a trusted main container.

---

# 5. Ephemeral Containers

Ephemeral containers live at:

```text
object.spec.ephemeralContainers
```

They are commonly added for debugging.

Example conceptual Pod state:

```yaml
spec:
  containers:
    - name: app
      image: ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>

  ephemeralContainers:
    - name: debugger
      image: nginx:latest
```

If ephemeral containers are not validated, a user can introduce an untrusted image into an otherwise protected Pod.

---

# 6. Why `kubectl debug` Matters

A common command:

```bash
kubectl debug \
  -n ai-platform \
  <POD> \
  --image=nginx:latest
```

attempts to add an ephemeral container.

If policy validates only normal containers, this becomes an admission bypass.

The platform therefore treats debug containers as part of the supply-chain boundary.

---

# 7. Direct Pod Creation

A user may attempt:

```bash
kubectl run ...
```

instead of creating a Deployment.

Therefore Pod-level enforcement is mandatory.

Without it:

```text
Deployment policy = strong
direct Pod = bypass
```

---

# 8. Higher-Level Workload Templates

Images also appear in Pod templates under:

```text
Deployment
StatefulSet
DaemonSet
Job
CronJob
```

For these resources, the regular container path is generally:

```text
object.spec.template.spec.containers
```

CronJob is deeper:

```text
object.spec.jobTemplate.spec.template.spec.containers
```

---

# 9. Defense-in-Depth Strategy

Strongest design:

```text
validate workload templates
        +
validate resulting Pods
```

Why both?

```text
template validation
    -> early feedback

Pod validation
    -> final runtime enforcement
```

---

# 10. Native Policy Layer

The platform uses:

```text
ValidatingAdmissionPolicy
ValidatingAdmissionPolicyBinding
```

with CEL expressions.

Representative base:

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingAdmissionPolicy
metadata:
  name: ai-platform-pod-images
spec:
  failurePolicy: Fail
```

---

# 11. Protected Image Pattern

Representative exact pattern:

```text
^ghcr\.io/anselem-okeke/(ai-platform-api|ai-platform-operator)@sha256:[0-9a-f]{64}$
```

This enforces:

```text
GHCR
approved owner
approved repository
immutable digest
SHA-256
exactly 64 hex chars
```

The exact production expression must be verified from the committed GitOps manifest.

---

# 12. Regular Container CEL

Representative:

```yaml
validations:
  - expression: >-
      object.spec.containers.all(c,
        c.image.matches(
          '^ghcr\.io/anselem-okeke/(ai-platform-api|ai-platform-operator)@sha256:[0-9a-f]{64}$'
        )
      )
    message: >-
      All regular containers must use an approved AI Platform image
      pinned to a full SHA-256 digest.
```

---

# 13. Init Container CEL

Init containers are optional.

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
    All init containers must use an approved AI Platform image
    pinned to a full SHA-256 digest.
```

---

# 14. Why `has(object.spec.initContainers)` Is Needed

The field may be absent.

A safe policy says:

```text
field absent
    -> no init containers to validate

field present
    -> validate all entries
```

This avoids expression errors and makes policy intent explicit.

---

# 15. Ephemeral Container CEL

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
    All ephemeral containers must use an approved AI Platform image
    pinned to a full SHA-256 digest.
```

---

# 16. Pod Policy Resource Rules

Representative:

```yaml
matchConstraints:
  resourceRules:
    - apiGroups: [""]
      apiVersions: ["v1"]
      operations:
        - CREATE
        - UPDATE
      resources:
        - pods
```

This protects direct Pod creation and Pod updates.

---

# 17. Ephemeral Container Subresource

Ephemeral containers are updated through a Pod subresource.

A robust policy may need to include:

```text
pods/ephemeralcontainers
```

depending on the exact Kubernetes admission matching behavior and policy design.

Representative resource rule:

```yaml
- apiGroups: [""]
  apiVersions: ["v1"]
  operations:
    - UPDATE
  resources:
    - pods/ephemeralcontainers
```

Verify the actual committed policy and cluster behavior before claiming exact parity.

---

# 18. Why Subresource Matching Matters

A policy matching only:

```text
pods
```

may not automatically cover every subresource mutation in the same way.

Ephemeral-container admission must be tested empirically.

The platform already validated that untrusted ephemeral images are denied.

---

# 19. Binding

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
      matchLabels:
        policy.sigstore.dev/include: "true"
```

---

# 20. Protected Namespace Label

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

# 21. Regular Container Positive Test

Use a real trusted API digest:

```bash
kubectl run pod-regular-positive \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:<REAL_TRUSTED_DIGEST>' \
  --restart=Never \
  --dry-run=server \
  -o yaml
```

Expected:

```text
native structural policy passes
Sigstore trust passes
request allowed
```

---

# 22. Regular Container Negative Test

```bash
kubectl run pod-regular-negative \
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

# 23. Init Container Negative Test with Real Trusted Main Image

Create:

```bash
cat >/tmp/bad-init-real-main.yaml <<'EOF'
apiVersion: v1
kind: Pod
metadata:
  name: bad-init-real-main
  namespace: ai-platform
spec:
  restartPolicy: Never

  initContainers:
    - name: untrusted-init
      image: nginx:latest
      command:
        - sh
        - -c
        - echo init

  containers:
    - name: api
      image: ghcr.io/anselem-okeke/ai-platform-api@sha256:<REAL_TRUSTED_DIGEST>
EOF
```

Replace the digest before applying.

Then:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/bad-init-real-main.yaml
```

Expected:

```text
DENIED
```

This isolates the init-container rule because the main image is legitimate.

---

# 24. Init Container Positive Test

Representative:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: good-init
  namespace: ai-platform
spec:
  restartPolicy: Never

  initContainers:
    - name: setup
      image: ghcr.io/anselem-okeke/ai-platform-api@sha256:<TRUSTED_DIGEST>
      command:
        - sh
        - -c
        - echo setup

  containers:
    - name: app
      image: ghcr.io/anselem-okeke/ai-platform-api@sha256:<TRUSTED_DIGEST>
```

Expected:

```text
allowed
```

assuming both references satisfy native and Sigstore policy.

---

# 25. Why Init Containers Need the Same Trust Standard

An init container may write into a shared volume:

```text
init container
    |
    v
/shared
    |
    v
main application
```

Therefore:

```text
trusted main container
+
untrusted init container
```

is not a secure workload.

---

# 26. Ephemeral Container Negative Test

Start with a disposable trusted Pod.

Example:

```bash
kubectl run ephemeral-test-base \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:<REAL_TRUSTED_DIGEST>' \
  --restart=Never
```

Wait:

```bash
kubectl get pod \
  ephemeral-test-base \
  -n ai-platform
```

Then attempt:

```bash
kubectl debug \
  -n ai-platform \
  ephemeral-test-base \
  --image=nginx:latest
```

Expected:

```text
DENIED
```

Use a disposable Pod because `kubectl debug` modifies Pod state.

---

# 27. Cleanup Ephemeral Test Pod

```bash
kubectl delete pod \
  ephemeral-test-base \
  -n ai-platform
```

---

# 28. Ephemeral Container Positive Test

If debugging with a trusted first-party image is operationally valid, use:

```bash
kubectl debug \
  -n ai-platform \
  ephemeral-test-base \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:<TRUSTED_DIGEST>'
```

Expected:

```text
structural policy passes
Sigstore trust passes
```

Whether using the API image as a debugger is useful is separate from whether policy allows it.

---

# 29. Why Debug Images May Need a Separate Approved Runtime

In a mature platform, using the application image for debugging is not ideal.

A future architecture may define:

```text
approved-debug-runtime
```

with:

```text
trusted build
digest pinning
attestation
limited tooling
```

Then native and Sigstore policies can explicitly allow that image.

---

# 30. Do Not Allow Arbitrary Debug Images

Avoid:

```text
busybox:latest
ubuntu:latest
alpine:latest
```

inside protected namespaces unless those images are intentionally mirrored, pinned, attested, and approved.

---

# 31. Deployment Template Regular Container Path

For a Deployment:

```text
object.spec.template.spec.containers
```

Representative CEL:

```yaml
- expression: >-
    object.spec.template.spec.containers.all(c,
      c.image.matches(
        '^ghcr\.io/anselem-okeke/(ai-platform-api|ai-platform-operator)@sha256:[0-9a-f]{64}$'
      )
    )
```

---

# 32. Deployment Init Container Path

Representative:

```yaml
- expression: >-
    !has(object.spec.template.spec.initContainers) ||
    object.spec.template.spec.initContainers.all(c,
      c.image.matches(
        '^ghcr\.io/anselem-okeke/(ai-platform-api|ai-platform-operator)@sha256:[0-9a-f]{64}$'
      )
    )
```

---

# 33. StatefulSet Paths

Regular:

```text
object.spec.template.spec.containers
```

Init:

```text
object.spec.template.spec.initContainers
```

Same Pod-template shape as Deployment.

---

# 34. DaemonSet Paths

Regular:

```text
object.spec.template.spec.containers
```

Init:

```text
object.spec.template.spec.initContainers
```

---

# 35. Job Paths

Regular:

```text
object.spec.template.spec.containers
```

Init:

```text
object.spec.template.spec.initContainers
```

---

# 36. CronJob Paths

Regular:

```text
object.spec.jobTemplate.spec.template.spec.containers
```

Init:

```text
object.spec.jobTemplate.spec.template.spec.initContainers
```

CronJob requires separate expressions because of the extra `jobTemplate` level.

---

# 37. Why Workload Template Validation Helps

Without Deployment validation:

```text
Deployment CREATE
    -> accepted

ReplicaSet creates Pod
    -> Pod denied

User sees workload failure later
```

With template validation:

```text
Deployment CREATE
    -> denied immediately
```

This improves user feedback and reduces broken desired state.

---

# 38. Why Pod Validation Is Still Mandatory

Even with workload-template policies:

```text
direct Pod
kubectl run
custom controller-created Pod
ephemeral update
```

still require Pod-level enforcement.

---

# 39. Deployment Negative Test

```bash
cat >/tmp/bad-deployment-image.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bad-deployment-image
  namespace: ai-platform
spec:
  replicas: 1
  selector:
    matchLabels:
      app: bad-deployment-image

  template:
    metadata:
      labels:
        app: bad-deployment-image

    spec:
      containers:
        - name: app
          image: nginx:latest
EOF
```

Server dry run:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/bad-deployment-image.yaml
```

Expected:

```text
DENIED
```

if Deployment-template policy is implemented.

---

# 40. Deployment Bad Init Test

```bash
cat >/tmp/bad-deployment-init.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bad-deployment-init
  namespace: ai-platform
spec:
  replicas: 1
  selector:
    matchLabels:
      app: bad-deployment-init

  template:
    metadata:
      labels:
        app: bad-deployment-init

    spec:
      initContainers:
        - name: init
          image: nginx:latest

      containers:
        - name: app
          image: ghcr.io/anselem-okeke/ai-platform-api@sha256:<REAL_TRUSTED_DIGEST>
EOF
```

Expected:

```text
DENIED
```

---

# 41. Job Negative Test

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: bad-job-image
  namespace: ai-platform
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: job
          image: nginx:latest
```

Server dry-run should fail if Job templates are covered.

---

# 42. CronJob Negative Test

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: bad-cronjob-image
  namespace: ai-platform
spec:
  schedule: "*/30 * * * *"

  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: Never
          containers:
            - name: job
              image: nginx:latest
```

Expected:

```text
DENIED
```

if CronJob policy coverage exists.

---

# 43. Multi-Container Pod

Every container must pass.

Example:

```yaml
containers:
  - name: api
    image: <trusted>

  - name: sidecar
    image: nginx:latest
```

Expected:

```text
DENIED
```

because `.all(...)` requires all entries to comply.

---

# 44. Why `.all(...)` Is Important

Bad logic:

```text
at least one container is trusted
```

Good logic:

```text
every container is trusted
```

CEL `.all(...)` expresses the latter.

---

# 45. Sidecar Security

A sidecar shares:

```text
Pod network namespace
volumes
service account
process environment boundaries
```

An untrusted sidecar can undermine a trusted main container.

Therefore sidecars follow the same policy.

---

# 46. Empty Container Arrays

Pods require at least one regular container under normal API validation.

The policy does not need to compensate for invalid Pod structure.

Kubernetes API validation handles structural requirements.

---

# 47. Image Pull Policy Is Not the Trust Boundary

Fields such as:

```yaml
imagePullPolicy: IfNotPresent
```

do not replace digest pinning.

Digest identity remains the security control.

---

# 48. Registry Authentication Does Not Equal Trust

Being able to pull an image from GHCR only proves authorization to fetch it.

Admission trust still evaluates:

```text
repository
digest
attestation
```

---

# 49. Native Policy vs Sigstore on Fake Digest

Example:

```text
ghcr.io/anselem-okeke/ai-platform-api@sha256:aaaaaaaa...64
```

Native policy:

```text
may pass structurally
```

Sigstore:

```text
DENY
no valid bundles exist in registry
```

This is expected and desirable.

---

# 50. Init Container Fake Digest

An init container using a fake but structurally valid digest may pass native structural validation.

Sigstore must still verify that exact digest.

Therefore the trust chain protects init containers too.

---

# 51. Ephemeral Fake Digest

Same principle:

```text
structurally valid digest
    +
missing trusted attestation
    =
DENY
```

---

# 52. Policy Error Messages

Use path-specific messages.

Good:

```text
Init containers must use approved digest-pinned images.
```

Good:

```text
Ephemeral containers must use approved digest-pinned images.
```

This makes admission failures much easier to diagnose.

---

# 53. Avoid One Generic Message for Everything

Bad:

```text
image policy failed
```

An engineer should know immediately whether the problem is:

```text
regular container
init container
ephemeral container
registry
digest
```

---

# 54. Namespace Binding

The policy should apply only where intended.

Representative:

```yaml
matchResources:
  namespaceSelector:
    matchLabels:
      policy.sigstore.dev/include: "true"
```

---

# 55. Why Namespace-Level Rollout Is Safer

Before enabling a new namespace:

```text
inventory workloads
validate image sources
validate digests
validate attestations
test native policy
```

Then add the label.

---

# 56. Adding a New Protected Namespace

GitOps manifest:

```yaml
metadata:
  labels:
    policy.sigstore.dev/include: "true"
```

After merge:

```bash
kubectl get ns \
  <namespace> \
  --show-labels
```

Then test:

```bash
kubectl run test \
  -n <namespace> \
  --image=nginx:latest \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

---

# 57. Policy GitOps Location

Policy manifests belong under:

```text
platform/policies/
```

A representative structure:

```text
platform/policies/
├── base/
│   ├── kustomization.yaml
│   ├── pod-image-policy.yaml
│   ├── pod-image-policy-binding.yaml
│   ├── workload-image-policy.yaml
│   └── workload-image-policy-binding.yaml
└── overlays/
    └── dev/
        └── kustomization.yaml
```

Use the actual repository structure when available.

---

# 58. Representative Kustomization

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - pod-image-policy.yaml
  - pod-image-policy-binding.yaml
  - workload-image-policy.yaml
  - workload-image-policy-binding.yaml
```

---

# 59. Render Policy Overlay

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/policies/overlays/dev \
  >/tmp/policies.yaml
```

---

# 60. Validate Policy Manifest

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/policies.yaml
```

Then:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/policies.yaml
```

---

# 61. Verify Policies Exist

```bash
kubectl get validatingadmissionpolicies
```

Bindings:

```bash
kubectl get validatingadmissionpolicybindings
```

---

# 62. Inspect Policy CEL

```bash
kubectl get validatingadmissionpolicy \
  <POLICY> \
  -o yaml
```

Verify expressions include:

```text
containers
initContainers
ephemeralContainers
```

where expected.

---

# 63. Inspect Binding Scope

```bash
kubectl get validatingadmissionpolicybinding \
  <BINDING> \
  -o yaml
```

Check:

```text
policyName
validationActions
namespaceSelector
```

---

# 64. Failure Scenario — Init Container Allowed

If this is allowed:

```yaml
initContainers:
  - image: nginx:latest
```

then investigate:

```text
policy missing initContainers expression
binding not applied
namespace not selected
wrong resource rule
CEL optional-field expression incorrect
```

---

# 65. Failure Scenario — Ephemeral Container Allowed

Investigate:

```text
pods/ephemeralcontainers subresource not matched
UPDATE operation absent
ephemeralContainers field not checked
binding scope wrong
```

Add regression test after fixing.

---

# 66. Failure Scenario — Direct Pod Allowed but Deployment Denied

This indicates:

```text
workload policy exists
Pod policy missing/inactive
```

Fix Pod-level enforcement.

---

# 67. Failure Scenario — Deployment Allowed but Pod Later Denied

This means:

```text
Pod enforcement works
workload-template policy missing
```

Security is still enforced at Pod creation, but developer feedback is late.

Add template validation.

---

# 68. Failure Scenario — Trusted Init Container Denied

Check:

```text
exact repository
digest separator
digest length
trust-policy image scope
attestation existence
```

Determine whether denial came from native or Sigstore layer.

---

# 69. Failure Scenario — CEL Optional Field Error

If a policy errors when no init containers exist, the expression likely assumes the field always exists.

Use:

```text
!has(...) || ...
```

or the exact safe CEL idiom supported by the cluster.

---

# 70. Failure Scenario — Regex Rejects Valid Image

Inspect:

```text
repository name
case
slash placement
@sha256:
64-char digest
```

Test expression against a known-good live image.

---

# 71. Failure Scenario — Regex Allows Too Much

If the policy allows:

```text
ghcr.io/anselem-okeke/random-image@sha256:...
```

but only API/operator should be accepted, tighten repository scope.

---

# 72. Failure Scenario — Debugging Becomes Impossible

Do not disable ephemeral-container policy.

Instead create an approved debug image.

The correct pattern is:

```text
approved debug image
digest pinned
attested
explicitly allowed
```

---

# 73. Future Approved Debug Runtime

Possible future repository:

```text
ghcr.io/anselem-okeke/ai-platform-debug-runtime
```

Then update both:

```text
native image allowlist
Sigstore trust-policy image patterns
```

and validate positive/negative behavior.

---

# 74. Failure Scenario — Policy Breaks Kubernetes System Components

Likely scope is too broad.

Check namespace selector.

Protected AI Platform policy should not accidentally target:

```text
kube-system
argocd
monitoring
cosign-system
```

unless intentionally designed.

---

# 75. Emergency Recovery

If policy causes a broad outage:

```text
1. identify exact failing rule
2. prefer Git revert
3. avoid deleting all admission controls
4. restore only the broken policy logic
5. rerun tests
6. confirm Deny enforcement restored
```

---

# 76. Policy Rollback

Preferred:

```bash
cd /mnt/data/ai-platform-gitops

git log --oneline -- \
  platform/policies

git revert <BAD_POLICY_COMMIT>
```

Then GitOps PR → validation → merge → Argo reconciliation.

---

# 77. Do Not Manually Delete Binding as Normal Fix

Deleting the binding makes the policy inert.

That is a security bypass.

Use only as a documented emergency action if the policy itself causes a cluster-impacting incident.

---

# 78. Post-Recovery Validation

After any policy fix:

```text
trusted API digest -> allow
trusted operator digest -> allow
nginx:latest -> deny
bad init -> deny
bad ephemeral -> deny
direct Pod bad image -> deny
```

---

# 79. Positive/Negative Test Matrix

| Test | Expected |
|---|---|
| Trusted regular container | Allow |
| Trusted regular + trusted init | Allow |
| Trusted regular + untrusted init | Deny |
| Trusted regular + untrusted ephemeral | Deny |
| Untrusted regular | Deny |
| Mixed multi-container Pod | Deny |
| Direct Pod untrusted | Deny |
| Deployment untrusted | Deny if template policy enabled |
| Fake valid digest | Native may pass, Sigstore denies |

---

# 80. Regression Test Suite

A future automated admission test script should include:

```text
01 trusted Pod
02 untrusted Pod
03 mutable first-party tag
04 wrong registry
05 short digest
06 trusted main + bad init
07 trusted main + bad ephemeral
08 multi-container one bad sidecar
09 bad Deployment
10 bad Job
11 bad CronJob
12 fake valid digest
```

---

# 81. Why Server Dry Run Is Preferred

Use:

```text
--dry-run=server
```

because it:

```text
executes real admission
does not persist most test objects
is repeatable
reduces cleanup
```

Ephemeral-container testing is an exception because the subresource update typically requires a real Pod.

---

# 82. Test Naming

Use clear test object names:

```text
policy-good-pod
policy-bad-init
policy-bad-ephemeral
policy-bad-sidecar
policy-bad-deployment
```

This helps logs and audit trails.

---

# 83. Cleanup Test Objects

List:

```bash
kubectl get pods \
  -n ai-platform \
  | grep policy-
```

Delete:

```bash
kubectl delete pod \
  -n ai-platform \
  <TEST_POD>
```

Use server dry-run whenever possible to avoid cleanup.

---

# 84. Observe Admission Errors in Events

For persisted controller workloads:

```bash
kubectl get events \
  -n ai-platform \
  --sort-by=.lastTimestamp
```

Look for:

```text
FailedCreate
admission denied
image policy message
Sigstore error
```

---

# 85. Observe Policy Controller Logs

```bash
kubectl get pods \
  -n cosign-system
```

Then:

```bash
kubectl logs \
  -n cosign-system \
  deployment/policy-controller-webhook \
  --tail=300
```

Use actual workload name if different.

---

# 86. Distinguish Native vs Sigstore Failure

Native failure usually references:

```text
ValidatingAdmissionPolicy
CEL validation message
```

Sigstore failure usually references:

```text
Policy Controller
ClusterImagePolicy
attestation/bundle verification
```

This distinction speeds troubleshooting.

---

# 87. Security Review Checklist

```text
[ ] regular containers validated
[ ] init containers validated
[ ] ephemeral containers validated
[ ] direct Pods validated
[ ] workload templates validated where implemented
[ ] CREATE covered
[ ] UPDATE covered
[ ] ephemeral subresource tested
[ ] all containers use `.all(...)`
[ ] namespace scoping correct
[ ] failurePolicy = Fail
[ ] validationActions = Deny
[ ] exact digest required
[ ] exact repository allowlist reviewed
[ ] Sigstore second layer remains active
```

---

# 88. Operational Checklist

```text
[ ] policy resources Synced
[ ] bindings active
[ ] protected namespace labels present
[ ] trusted Pod accepted
[ ] untrusted Pod denied
[ ] bad init denied
[ ] bad ephemeral denied
[ ] bad sidecar denied
[ ] workload-template behavior verified
[ ] no unexpected system namespace impact
```

---

# 89. Rebuild from Zero

```text
[ ] verify Kubernetes supports ValidatingAdmissionPolicy
[ ] create Pod policy
[ ] cover containers
[ ] cover initContainers
[ ] cover ephemeralContainers
[ ] include CREATE
[ ] include UPDATE
[ ] verify ephemeral subresource coverage
[ ] create binding
[ ] set Deny
[ ] set namespace selector
[ ] create workload-template policy
[ ] cover Deployment
[ ] cover StatefulSet
[ ] cover DaemonSet
[ ] cover Job
[ ] cover CronJob
[ ] add to GitOps Kustomization
[ ] ensure AppProject permits policy kinds
[ ] render
[ ] kubeconform
[ ] server dry-run policy resources
[ ] merge
[ ] verify Argo
[ ] trusted Pod test
[ ] bad Pod test
[ ] bad init test
[ ] bad ephemeral test
[ ] bad sidecar test
[ ] workload-template tests
[ ] fake-digest trust test
[ ] document exact CEL
```

---

# 90. Known Implementation Facts

Validated project facts:

```text
regular container policy:
implemented

init-container coverage:
validated

ephemeral-container coverage:
validated

direct Pod coverage:
validated

protected namespaces:
ai-platform
ai-platform-operator-system

image identity:
approved GHCR + full sha256 digest

Sigstore:
second trust layer

fake valid digest:
denied by Sigstore
```

---

# 91. What Must Be Verified from the Actual GitOps Repository

Before claiming exact manifest parity, inspect:

```text
exact policy names
exact binding names
exact resourceRules
whether pods/ephemeralcontainers is explicitly listed
exact CEL expressions
exact workload kinds covered
exact repository regex
exact namespace selector
exact filenames
```

Commands:

```bash
cd /mnt/data/ai-platform-gitops

grep -RIn \
  'ValidatingAdmissionPolicy\|ValidatingAdmissionPolicyBinding\|initContainers\|ephemeralContainers\|pods/ephemeralcontainers' \
  platform/policies
```

Then:

```bash
kubectl kustomize \
  platform/policies/overlays/dev \
  >/tmp/policies.yaml

grep -nE \
  'containers|initContainers|ephemeralContainers|resources:' \
  /tmp/policies.yaml
```

---

# 92. Official References

Kubernetes ValidatingAdmissionPolicy:

```text
https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/
```

Kubernetes CEL:

```text
https://kubernetes.io/docs/reference/using-api/cel/
```

Ephemeral containers:

```text
https://kubernetes.io/docs/concepts/workloads/pods/ephemeral-containers/
```

Debugging running Pods:

```text
https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/
```

Init containers:

```text
https://kubernetes.io/docs/concepts/workloads/pods/init-containers/
```

Pod lifecycle:

```text
https://kubernetes.io/docs/concepts/workloads/pods/
```

---

# 93. Related AI Platform Documentation

```text
031-sigstore-policy-controller.md
032-github-attestation-trust.md
033-image-admission-policies.md
035-policy-controller-observability.md
036-policy-controller-alerting.md
039-software-supply-chain-security.md
040-end-to-end-delivery-workflow.md
041-validation-and-security-tests.md
043-troubleshooting-guide.md
045-command-reference.md
047-design-decisions.md
