# Sigstore Policy Controller

## Purpose

This document is the **reproducible installation, GitOps, admission-control, validation, observability, and recovery guide** for Sigstore Policy Controller in the AI Platform.

The purpose of Policy Controller is to ensure that Kubernetes workloads in protected namespaces only run images that satisfy the platform's trusted software-supply-chain requirements.

The validated architecture is:

```text
source commit
    |
    v
GitHub Actions release
    |
    +--> build image
    +--> scan image
    +--> push GHCR
    +--> provenance attestation
    +--> SBOM attestation
    |
    v
GHCR immutable digest
    |
    v
GitOps promotion PR
    |
    v
Argo CD
    |
    v
Kubernetes admission request
    |
    v
Sigstore Policy Controller
    |
    +--> TrustRoot
    +--> ClusterImagePolicy
    |
    +--> trusted digest/evidence -> ALLOW
    |
    +--> missing/untrusted evidence -> DENY
```

A new engineer should be able to:

```text
install Policy Controller
install GitHub attestation trust policy
manage both through Argo CD
enable enforcement by namespace
validate positive and negative admission behavior
troubleshoot webhook/admission failures
integrate metrics with Prometheus
recover from GitOps drift
upgrade safely
```

using this guide and the GitOps repository.

---

# 1. Validated Versions and Namespace

Validated Policy Controller Helm chart:

```text
0.10.6
```

Validated Policy Controller application version:

```text
0.13.1
```

Namespace:

```text
cosign-system
```

Current Helm release ownership:

```text
release name: policy-controller
release namespace: cosign-system
```

This namespace is important because the cluster already contains the Policy Controller CRD and release metadata owned by `cosign-system`.

Do not attempt to install another release into a different namespace without first understanding CRD ownership.

---

# 2. Previous Failed Installation and Why It Failed

A previous install attempt targeted:

```text
artifact-attestations
```

with Policy Controller chart:

```text
0.10.5
```

The installation failed because the CRD:

```text
clusterimagepolicies.policy.sigstore.dev
```

already existed and was annotated as owned by:

```text
release-name: policy-controller
release-namespace: cosign-system
```

Helm refused to import the CRD into another release namespace.

The lesson is:

```text
cluster-scoped CRDs can only have one Helm ownership context
```

Do not solve this by stripping ownership annotations casually.

The correct standardization for this platform is:

```text
namespace: cosign-system
release: policy-controller
chart: 0.10.6
```

---

# 3. Verify Existing Helm State

Run:

```bash
helm list -A
```

Expected relevant result:

```text
policy-controller   cosign-system   ...   deployed   policy-controller-0.10.6
```

Verify pods:

```bash
kubectl get pods \
  -n cosign-system
```

Expected:

```text
policy-controller-webhook-...   1/1   Running
```

---

# 4. Verify CRDs

List Sigstore policy CRDs:

```bash
kubectl get crd \
  | grep policy.sigstore.dev
```

Expected examples:

```text
clusterimagepolicies.policy.sigstore.dev
trustroots.policy.sigstore.dev
```

Inspect ownership annotation:

```bash
kubectl get crd \
  clusterimagepolicies.policy.sigstore.dev \
  -o jsonpath='{.metadata.annotations.meta\.helm\.sh/release-name}{"\n"}{.metadata.annotations.meta\.helm\.sh/release-namespace}{"\n"}'
```

Expected:

```text
policy-controller
cosign-system
```

---

# 5. GitOps Application for Policy Controller

The current architecture manages Policy Controller as an external Helm Application through Argo CD.

Recommended file location:

```text
clusters/dev/apps/policy-controller.yaml
```

Representative manifest snippet:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: policy-controller
  namespace: argocd
spec:
  project: ai-platform

  source:
    repoURL: ghcr.io/sigstore/helm-charts
    chart: policy-controller
    targetRevision: 0.10.6

  destination:
    server: https://kubernetes.default.svc
    namespace: cosign-system

  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

This snippet captures the architecture that matters:

```text
pinned chart version
dedicated namespace
AppProject-scoped deployment
automated child reconciliation
```

Use the actual committed Application manifest as the source of truth when rebuilding.

---

# 6. Why the Chart Version Is Pinned

Do not use:

```yaml
targetRevision: latest
```

or:

```yaml
targetRevision: HEAD
```

for this external dependency.

Use:

```yaml
targetRevision: 0.10.6
```

This makes the desired platform state reproducible and reviewable.

---

# 7. AppProject Permissions Required

The Argo CD AppProject must allow:

```text
source repository:
ghcr.io/sigstore/helm-charts

destination namespace:
cosign-system
```

It must also permit the cluster-scoped resources required by the chart and trust policies.

Representative AppProject snippets may include allowlists for:

```yaml
clusterResourceWhitelist:
  - group: policy.sigstore.dev
    kind: TrustRoot
  - group: policy.sigstore.dev
    kind: ClusterImagePolicy
```

and admission registration resources where required by the controller/chart:

```yaml
clusterResourceWhitelist:
  - group: admissionregistration.k8s.io
    kind: MutatingWebhookConfiguration
  - group: admissionregistration.k8s.io
    kind: ValidatingWebhookConfiguration
```

Do not replace precise allowlists with:

```yaml
group: "*"
kind: "*"
```

unless a deliberate privilege review authorizes it.

---

# 8. Apply AppProject Changes Before First Argo Sync

The platform's AppProject is bootstrap-managed.

Validate:

```bash
cd /mnt/data/ai-platform-gitops

kubectl apply \
  --dry-run=server \
  -f argocd/projects/ai-platform.yaml
```

Apply:

```bash
kubectl apply \
  -f argocd/projects/ai-platform.yaml
```

Then continue with the Argo child Application.

---

# 9. Add Policy Controller to the App-of-Apps

Ensure:

```text
clusters/dev/apps/kustomization.yaml
```

includes:

```yaml
resources:
  - policy-controller.yaml
```

Representative snippet:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - operator.yaml
  - api.yaml
  - gateway.yaml
  - monitoring.yaml
  - namespaces.yaml
  - policies.yaml
  - modelservices.yaml
  - policy-controller.yaml
  - trust-policies.yaml
```

Exact ordering is less important than reproducibility and dependency awareness.

---

# 10. Root Application Synchronization

Because the root App-of-Apps is intentionally manual, adding the new child Application requires:

```bash
argocd app get \
  ai-platform-root \
  --refresh
```

Review:

```bash
argocd app diff \
  ai-platform-root
```

Then sync:

```bash
argocd app sync \
  ai-platform-root
```

Wait:

```bash
argocd app wait \
  ai-platform-root \
  --sync \
  --health \
  --timeout 300
```

After the child exists, future Policy Controller changes are reconciled by the child Application automatically.

---

# 11. Verify Argo Application

```bash
argocd app get \
  policy-controller \
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
  policy-controller \
  -n argocd
```

---

# 12. Verify Policy Controller Workloads

```bash
kubectl get deploy \
  -n cosign-system
```

Expected controller/webhook Deployment.

Inspect pods:

```bash
kubectl get pods \
  -n cosign-system \
  -o wide
```

Expected:

```text
Running
Ready 1/1
```

---

# 13. Verify Webhook Configurations

List:

```bash
kubectl get mutatingwebhookconfiguration \
  | grep policy.sigstore.dev
```

```bash
kubectl get validatingwebhookconfiguration \
  | grep policy.sigstore.dev
```

Inspect:

```bash
kubectl get mutatingwebhookconfiguration \
  policy.sigstore.dev \
  -o yaml
```

and:

```bash
kubectl get validatingwebhookconfiguration \
  policy.sigstore.dev \
  -o yaml
```

---

# 14. Namespace Enforcement Model

Policy Controller uses namespace labels to determine where enforcement applies.

For this platform, enforcement is enabled on:

```text
ai-platform
ai-platform-operator-system
```

Representative namespace manifest:

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

These labels are GitOps-managed.

---

# 15. Why Namespace Opt-In Is Important

Without deliberate scope, a cluster-wide admission policy can unexpectedly block:

```text
system namespaces
third-party controllers
bootstrap infrastructure
CI test workloads
```

The platform therefore explicitly opts protected namespaces into enforcement.

This creates a manageable rollout boundary.

---

# 16. Verify Namespace Labels

```bash
kubectl get namespace \
  ai-platform \
  --show-labels
```

Expected:

```text
policy.sigstore.dev/include=true
```

Operator namespace:

```bash
kubectl get namespace \
  ai-platform-operator-system \
  --show-labels
```

---

# 17. GitHub Attestation Trust Policy

The platform uses the GitHub Artifact Attestations trust-policy Helm chart.

Validated chart:

```text
trust-policies
```

Validated version:

```text
v0.7.0
```

Repository:

```text
ghcr.io/github/artifact-attestations-helm-charts
```

---

# 18. Trust Policy Helm Values

Validated values:

```yaml
policy:
  enabled: true
  organization: anselem-okeke
  images:
    - "ghcr.io/anselem-okeke/ai-platform-operator**"
    - "ghcr.io/anselem-okeke/ai-platform-api**"
```

This is one of the most important configuration snippets in the platform.

It establishes:

```text
trusted GitHub organization:
anselem-okeke

trusted image scopes:
ai-platform-operator
ai-platform-api
```

---

# 19. Manual Helm Command Used During Validation

The validated installation command was:

```bash
helm upgrade trust-policies --install \
  --rollback-on-failure \
  --namespace cosign-system \
  oci://ghcr.io/github/artifact-attestations-helm-charts/trust-policies \
  --version v0.7.0 \
  -f /tmp/github-attestation-policy-values.yaml
```

For final platform operation, this trust policy is managed through Argo CD rather than repeated manual installation.

The manual command remains valuable for:

```text
rebuild validation
troubleshooting
emergency reproduction
```

---

# 20. GitOps Application for Trust Policies

Representative Argo Application:

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

Use the repository's actual manifest if its structure differs.

---

# 21. TrustRoot

After installation:

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

This TrustRoot contains the trust material/configuration used by the GitHub attestation integration.

---

# 22. ClusterImagePolicy

List:

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

The exact generated policy structure comes from the trust-policies chart.

---

# 23. Why the Platform Uses Generated Trust Policy

Instead of manually handcrafting a complex attestation verification policy, the GitHub trust-policy chart creates the Sigstore trust resources that correspond to GitHub Artifact Attestations.

This reduces custom cryptographic policy logic while keeping:

```text
organization scope
image scope
runtime admission
```

explicit.

---

# 24. Positive Admission Test — Trusted API Image

Use a real API digest produced by the trusted release pipeline.

Server-side dry run:

```bash
kubectl run trusted-api-test \
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

The exact digest must exist and carry valid trusted attestation evidence.

---

# 25. Positive Admission Test — Trusted Operator Image

```bash
kubectl run trusted-operator-test \
  -n ai-platform-operator-system \
  --image='ghcr.io/anselem-okeke/ai-platform-operator@sha256:<REAL_TRUSTED_DIGEST>' \
  --restart=Never \
  --dry-run=server \
  -o yaml
```

Expected:

```text
request allowed
```

---

# 26. Negative Admission Test — Untrusted Mutable Image

Use:

```bash
kubectl run sigstore-negative-nginx \
  -n ai-platform \
  --image=nginx:latest \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

This proves that a random image cannot run in a protected namespace.

---

# 27. Negative Test — Bad Init Container

Representative Pod:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: bad-init-test
  namespace: ai-platform
spec:
  restartPolicy: Never

  initContainers:
    - name: bad-init
      image: nginx:latest
      command: ["sh", "-c", "echo test"]

  containers:
    - name: app
      image: ghcr.io/anselem-okeke/ai-platform-api@sha256:<TRUSTED_DIGEST>
```

Apply as server dry-run:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/bad-init-test.yaml
```

Expected:

```text
DENIED
```

This validates init-container coverage.

---

# 28. Negative Test — Ephemeral Container

Admission policy coverage also includes ephemeral containers.

A test using an untrusted ephemeral image should be denied.

Representative concept:

```text
existing trusted Pod
    +
ephemeral container image = nginx:latest
    |
    v
DENIED
```

This prevents bypassing runtime image policy through debug containers.

---

# 29. Negative Test — Valid-Looking Fake Digest

Use a syntactically valid SHA-256 digest that does not correspond to trusted attested content.

Example shape:

```text
sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
```

The Kubernetes image parser may accept the format, but Sigstore should reject the trust verification.

Observed failure:

```text
no valid bundles exist in registry
```

This is a critical validation result.

It proves:

```text
correct digest syntax
```

is not the same as:

```text
trusted artifact
```

---

# 30. Malformed Digest Test

A malformed digest should be rejected before Sigstore trust verification.

Example invalid:

```text
sha256:1234
```

This may fail at Kubernetes/container image parsing.

This test validates a different layer than the fake-valid-digest test.

---

# 31. Direct Pod Coverage

The platform tests direct Pod admission because Deployment admission alone is insufficient.

Example:

```bash
kubectl run direct-untrusted \
  -n ai-platform \
  --image=nginx:latest \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

This demonstrates that a user cannot bypass higher-level workload checks by creating a Pod directly.

---

# 32. Why Regular, Init, and Ephemeral Containers Matter

A robust image policy must cover:

```text
spec.containers[]
spec.initContainers[]
spec.ephemeralContainers[]
```

Otherwise an attacker/operator could place an untrusted image in a secondary container path.

The platform has validated these coverage paths.

---

# 33. Native Admission Policies Complement Sigstore

The platform also uses native Kubernetes validation policies.

The two layers serve different purposes:

```text
Native policy
  -> image reference structure / repository / digest rules

Sigstore
  -> trusted attestation evidence for the exact digest
```

This gives:

```text
syntax + provenance
```

rather than only one or the other.

---

# 34. Why Both Layers Are Useful

A native policy can require:

```text
@sha256:<64hex>
```

but cannot by itself prove:

```text
who built it
which workflow produced it
whether trusted attestation exists
```

Sigstore provides that trust verification.

---

# 35. Verify Admission Webhook Service

List service:

```bash
kubectl get svc \
  -n cosign-system
```

Expected metrics/webhook services include the Policy Controller service.

Inspect:

```bash
kubectl describe svc \
  -n cosign-system \
  policy-controller-webhook
```

Use the actual service name from the cluster if it differs.

---

# 36. Metrics Service

Validated metrics service:

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

# 37. Verify Metrics Endpoint

Port-forward:

```bash
kubectl port-forward \
  -n cosign-system \
  svc/policy-controller-webhook-metrics \
  9090:9090
```

Then:

```bash
curl -s \
  http://127.0.0.1:9090/metrics \
  | grep '^policy_controller_' \
  | head -n 40
```

Expected metric families include:

```text
policy_controller_client_latency
policy_controller_client_results
policy_controller_reconcile_count
policy_controller_reconcile_latency
policy_controller_request_count
policy_controller_request_latencies
```

---

# 38. Reconcile Metric Labels

Validated `policy_controller_reconcile_count` labels include:

```text
namespace_name
reconciler
success
```

This allows queries such as:

```promql
sum(
  increase(
    policy_controller_reconcile_count{
      success="false"
    }[10m]
  )
)
```

---

# 39. ServiceMonitor

The platform includes:

```text
platform/monitoring/base/policy-controller-servicemonitor.yaml
```

Representative snippet:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: policy-controller
  namespace: monitoring
  labels:
    release: kps
spec:
  namespaceSelector:
    matchNames:
      - cosign-system

  selector:
    matchLabels:
      app.kubernetes.io/name: policy-controller

  endpoints:
    - port: metrics
      interval: 30s
      scrapeTimeout: 10s
```

The exact selector must match the live metrics service labels.

---

# 40. Verify Service Labels Before Writing ServiceMonitor

Run:

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system \
  --show-labels
```

Use the exact labels in:

```yaml
spec.selector.matchLabels
```

Do not guess service labels.

---

# 41. Prometheus Namespace/ServiceMonitor Selection

Validated Prometheus configuration accepts ServiceMonitors broadly:

```yaml
serviceMonitorNamespaceSelector: {}
serviceMonitorSelector: {}
```

This allows the monitoring namespace ServiceMonitor to select the Policy Controller service in `cosign-system`.

---

# 42. Verify Prometheus Target

Port-forward Prometheus or use the existing access method.

Query:

```promql
up{
  namespace="cosign-system",
  service="policy-controller-webhook-metrics"
}
```

Expected:

```text
1
```

This was empirically validated.

---

# 43. PrometheusRule

The platform includes:

```text
platform/monitoring/base/policy-controller-prometheusrule.yaml
```

Validated alerts:

```text
PolicyControllerTargetDown
PolicyControllerReconcileFailures
PolicyControllerWebhookCertificateFailures
```

---

# 44. Target Down Alert

Representative manifest snippet:

```yaml
- alert: PolicyControllerTargetDown
  expr: |
    up{
      namespace="cosign-system",
      service="policy-controller-webhook-metrics"
    } == 0
  for: 5m
  labels:
    severity: critical
```

---

# 45. Reconcile Failures Alert

Representative snippet:

```yaml
- alert: PolicyControllerReconcileFailures
  expr: |
    sum(
      increase(
        policy_controller_reconcile_count{
          success="false"
        }[10m]
      )
    ) > 5
  for: 5m
  labels:
    severity: warning
```

Use `increase()` for historical counters rather than checking a raw cumulative total.

---

# 46. Webhook Certificate Failure Alert

Representative snippet:

```yaml
- alert: PolicyControllerWebhookCertificateFailures
  expr: |
    increase(
      policy_controller_reconcile_count{
        reconciler="WebhookCertificates",
        success="false"
      }[10m]
    ) > 0
  for: 5m
  labels:
    severity: critical
```

---

# 47. PrometheusRule Label

The kube-prometheus-stack setup required:

```yaml
metadata:
  labels:
    release: kps
```

Without that label, Prometheus may not select the rule depending on its rule selector.

This label fix was part of the validated configuration.

---

# 48. Do Not Claim Alert Firing Was Tested Unless It Was

The platform validated:

```text
Prometheus target = 1
metrics present
rule loaded/selector corrected
```

Do not claim:

```text
each alert was intentionally forced into Firing state
```

unless that test is explicitly performed.

---

# 49. Real Argo Drift Case — Knative Webhook Selector

The live Policy Controller webhook configuration gained:

```yaml
namespaceSelector:
  matchExpressions:
    - key: webhooks.knative.dev/exclude
      operator: DoesNotExist
```

This controller-generated mutation caused Argo drift.

---

# 50. Narrow Argo ignoreDifferences Fix

The correct architecture was to ignore only the exact known controller-managed selector.

Representative pattern:

```yaml
ignoreDifferences:
  - group: admissionregistration.k8s.io
    kind: MutatingWebhookConfiguration
    name: policy.sigstore.dev
    jqPathExpressions:
      - |
        .webhooks[].namespaceSelector.matchExpressions[]
        | select(
            .key == "webhooks.knative.dev/exclude"
            and
            .operator == "DoesNotExist"
          )
```

A corresponding narrow rule may be required for:

```text
ValidatingWebhookConfiguration/policy.sigstore.dev
```

depending on the actual diff.

The exact committed expression must be inspected from the repository.

---

# 51. RespectIgnoreDifferences Sync Option

Representative:

```yaml
syncPolicy:
  syncOptions:
    - RespectIgnoreDifferences=true
```

This ensures Argo sync honors the declared ignored field.

Do not add this option unless there is an intentional `ignoreDifferences` rule.

---

# 52. Why Broad Ignore Is Not Acceptable

Do not use:

```yaml
ignoreDifferences:
  - group: admissionregistration.k8s.io
    kind: MutatingWebhookConfiguration
    jsonPointers:
      - /webhooks
```

This would hide security-sensitive drift such as:

```text
wrong service
wrong CA bundle
wrong rules
wrong namespaceSelector
wrong failurePolicy
```

The rule must remain narrow.

---

# 53. Verify Argo Drift Is Resolved

After applying the narrow ignore:

```bash
argocd app get \
  policy-controller \
  --refresh
```

Expected:

```text
Synced
Healthy
```

Check:

```bash
argocd app diff \
  policy-controller
```

Expected:

```text
no unintended diff
```

---

# 54. Admission Failure Troubleshooting

If a trusted image is unexpectedly denied, inspect:

```text
image digest
GitHub attestation existence
TrustRoot
ClusterImagePolicy
namespace label
Policy Controller webhook
controller logs
registry access
```

Do not immediately weaken policy.

---

# 55. Policy Controller Logs

Discover pod:

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

If the workload name differs, discover:

```bash
kubectl get deploy \
  -n cosign-system
```

---

# 56. Inspect Admission Error from Server Dry Run

Use:

```bash
kubectl apply \
  --dry-run=server \
  -f <manifest>
```

This is one of the safest ways to test admission because the object is not persisted.

Capture the complete error.

---

# 57. Troubleshooting: `no valid bundles exist in registry`

Meaning:

```text
the image reference may be syntactically valid
but trusted GitHub attestation evidence was not found/accepted
```

Check:

```text
digest exists
image was produced by trusted release
attestation step succeeded
organization matches policy
image repository matches policy
```

---

# 58. Troubleshooting: Random Public Image Allowed

This is a serious enforcement failure.

Check namespace:

```bash
kubectl get ns \
  ai-platform \
  --show-labels
```

Expected:

```text
policy.sigstore.dev/include=true
```

Then inspect:

```text
ClusterImagePolicy
webhook configuration
controller readiness
```

---

# 59. Troubleshooting: Protected Namespace Missing Label

Fix in GitOps namespace manifest.

Do not manually label only the live namespace and leave Git wrong.

Representative patch in Git:

```yaml
metadata:
  labels:
    policy.sigstore.dev/include: "true"
```

Then let Argo reconcile.

---

# 60. Troubleshooting: Policy Controller Pod Not Ready

Inspect:

```bash
kubectl describe pod \
  -n cosign-system \
  <POD>
```

Logs:

```bash
kubectl logs \
  -n cosign-system \
  <POD> \
  --all-containers \
  --tail=300
```

Look for:

```text
certificate problem
webhook registration
RBAC
CRD mismatch
chart upgrade problem
API incompatibility
```

---

# 61. Troubleshooting: Webhook Certificate Failure

Inspect webhook configuration:

```bash
kubectl get validatingwebhookconfiguration \
  policy.sigstore.dev \
  -o yaml
```

Check:

```text
caBundle
service namespace
service name
service port
```

Inspect controller metrics:

```promql
increase(
  policy_controller_reconcile_count{
    reconciler="WebhookCertificates",
    success="false"
  }[10m]
)
```

---

# 62. Troubleshooting: Webhook Service Has No Endpoints

```bash
kubectl get endpoints \
  -n cosign-system \
  policy-controller-webhook
```

If empty:

```text
Pod not Ready
selector mismatch
Deployment unavailable
```

Inspect Service selector and Pod labels.

---

# 63. Troubleshooting: Helm Ownership Conflict

Symptom:

```text
existing CRD cannot be imported into current release
invalid ownership metadata
```

Inspect CRD annotations:

```bash
kubectl get crd \
  clusterimagepolicies.policy.sigstore.dev \
  -o yaml \
  | grep -A8 -B2 'meta.helm.sh'
```

If owned by:

```text
policy-controller / cosign-system
```

then reinstall/upgrade in the same standardized release/namespace.

Do not move the release across namespaces casually.

---

# 64. Troubleshooting: Argo Cannot Install Cluster-Scoped Resource

Likely AppProject issue.

Inspect:

```bash
kubectl get appproject \
  ai-platform \
  -n argocd \
  -o yaml
```

Add only the required group/kind.

Then bootstrap-apply AppProject.

---

# 65. Troubleshooting: Trust Policy Application OutOfSync

Check:

```bash
argocd app diff \
  trust-policies
```

Possible causes:

```text
chart-generated fields
controller mutations
Helm values drift
targetRevision mismatch
AppProject permissions
```

Do not broad-ignore generated policy resources without understanding the exact diff.

---

# 66. Troubleshooting: GitHub Organization Scope Wrong

Trust values must contain:

```yaml
organization: anselem-okeke
```

If the release originates from another GitHub owner/org, attestation verification may fail.

Keep the organization scope narrow.

---

# 67. Troubleshooting: Image Pattern Too Broad

Avoid:

```yaml
images:
  - "ghcr.io/**"
```

The validated scope is:

```yaml
images:
  - "ghcr.io/anselem-okeke/ai-platform-operator**"
  - "ghcr.io/anselem-okeke/ai-platform-api**"
```

This prevents unrelated GHCR images from being automatically trusted by this policy.

---

# 68. Upgrade Procedure

Before upgrading Policy Controller:

```text
1. review upstream release notes
2. verify Kubernetes compatibility
3. verify CRD changes
4. verify Helm chart changes
5. verify GitHub trust-policy compatibility
6. update targetRevision in GitOps PR
7. run GitOps validation
8. merge
9. monitor Argo sync
10. verify webhook readiness
11. rerun positive admission test
12. rerun negative admission test
13. verify Prometheus target
14. verify no new Argo drift
```

Do not upgrade the chart and trust-policy chart independently without compatibility review.

---

# 69. CRD Upgrade Caution

CRDs are cluster-scoped and may outlive Helm release changes.

Before downgrade or namespace migration:

```text
inspect CRD schema/version
inspect Helm ownership
inspect existing custom resources
```

Do not delete CRDs merely to make Helm install succeed.

---

# 70. Uninstall Procedure

Uninstalling admission control is security-sensitive.

Before:

```bash
helm uninstall policy-controller \
  -n cosign-system
```

or removing the Argo Application:

```text
understand protected namespace behavior
understand webhook removal
understand trust-resource ownership
have rollback/reinstall plan
```

For normal GitOps operation, remove/change through Git, not direct Helm.

---

# 71. Emergency Disablement

Do not disable Sigstore enforcement just because a deployment fails.

Use emergency disablement only if:

```text
admission infrastructure itself is causing broad cluster outage
authorized responder approves
change is documented
re-enable plan exists
```

Prefer:

```text
rollback workload to known-good trusted digest
```

---

# 72. Recovery After Accidental Removal

If Policy Controller Application is removed unintentionally:

```text
1. restore Git
2. sync root if child Application topology changed
3. wait for policy-controller child sync
4. verify CRDs
5. verify Deployment
6. verify webhook configurations
7. verify TrustRoot
8. verify ClusterImagePolicy
9. verify namespace labels
10. run positive test
11. run negative test
12. verify metrics
```

---

# 73. Positive Security Test Matrix

| Test | Expected |
|---|---|
| Trusted API digest | Allowed |
| Trusted operator digest | Allowed |
| Existing signed/attested rollout | Healthy |
| Protected namespace | Enforcement active |

---

# 74. Negative Security Test Matrix

| Test | Expected |
|---|---|
| `nginx:latest` Pod | Denied |
| untrusted init container | Denied |
| untrusted ephemeral container | Denied |
| malformed digest | Rejected |
| syntactically valid fake digest | Denied by trust verification |
| random direct Pod | Denied |

---

# 75. Operational Validation Checklist

```text
[ ] Helm release exists in cosign-system
[ ] chart version = 0.10.6
[ ] Policy Controller pod Ready
[ ] CRDs installed
[ ] mutating webhook exists
[ ] validating webhook exists
[ ] TrustRoot github exists
[ ] ClusterImagePolicy github-policy exists
[ ] ai-platform namespace opted in
[ ] operator namespace opted in
[ ] trusted digest allowed
[ ] nginx:latest denied
[ ] bad init denied
[ ] bad ephemeral container denied
[ ] fake digest denied
[ ] metrics endpoint responds
[ ] Prometheus target = 1
[ ] Argo Applications Synced/Healthy
[ ] no broad ignoreDifferences
```

---

# 76. Security Review Checklist

```text
[ ] AppProject uses least privilege
[ ] chart versions pinned
[ ] trust organization scoped
[ ] image patterns narrow
[ ] namespace enforcement explicit
[ ] mutable/untrusted images denied
[ ] fake digest denied
[ ] init/ephemeral/direct Pod paths covered
[ ] Policy Controller metrics monitored
[ ] webhook certificate failures alerted
[ ] broad webhook diff ignores prohibited
[ ] emergency disablement not used as normal recovery
```

---

# 77. Rebuild Procedure from Zero

```text
[ ] verify Kubernetes cluster
[ ] verify Argo CD
[ ] verify AppProject
[ ] add ghcr.io/sigstore/helm-charts source permission
[ ] add cosign-system destination
[ ] add required clusterResourceWhitelist entries
[ ] bootstrap-apply AppProject
[ ] create policy-controller Application
[ ] pin chart 0.10.6
[ ] target cosign-system
[ ] add to clusters/dev/apps
[ ] merge GitOps PR
[ ] manual root sync
[ ] wait for child Healthy
[ ] verify CRDs
[ ] verify webhook configurations
[ ] create trust-policies Application
[ ] pin trust-policies v0.7.0
[ ] configure organization anselem-okeke
[ ] configure operator/API image patterns
[ ] verify TrustRoot github
[ ] verify ClusterImagePolicy github-policy
[ ] label protected namespaces
[ ] validate trusted API digest
[ ] validate trusted operator digest
[ ] deny nginx:latest
[ ] deny bad init container
[ ] deny fake digest
[ ] validate ephemeral-container denial
[ ] add ServiceMonitor
[ ] add PrometheusRule
[ ] verify target = 1
[ ] inspect Argo drift
[ ] apply only narrow Knative selector ignore if required
[ ] document final state
```

---

# 78. Known Implementation Facts

Validated facts:

```text
Policy Controller chart:
0.10.6

Policy Controller app version:
0.13.1

Namespace:
cosign-system

Trust policy chart:
v0.7.0

GitHub organization:
anselem-okeke

Trusted image patterns:
ghcr.io/anselem-okeke/ai-platform-operator**
ghcr.io/anselem-okeke/ai-platform-api**

TrustRoot:
github

ClusterImagePolicy:
github-policy

Namespace opt-in label:
policy.sigstore.dev/include=true

Protected namespaces:
ai-platform
ai-platform-operator-system

Metrics service:
policy-controller-webhook-metrics

Metrics port:
9090

Prometheus target:
validated as up = 1

Empirical negative tests:
nginx latest denied
bad init denied
fake digest denied
ephemeral untrusted denied

Observed fake digest error:
no valid bundles exist in registry
```

---

# 79. What Must Be Verified from Actual Repository/Cluster

Do not invent:

```text
exact current Argo Application YAML
exact current Service labels
exact current webhook Deployment/Service names
exact current ignoreDifferences expression
exact trusted image digest
exact current chart-generated TrustRoot content
exact current ClusterImagePolicy internals
```

Inspect:

```text
clusters/dev/apps/
platform/monitoring/base/
platform/namespaces/
argocd/projects/ai-platform.yaml
live Kubernetes resources
```

---

# 80. Official References

Sigstore Policy Controller:

```text
https://docs.sigstore.dev/policy-controller/overview/
```

Sigstore Policy Controller repository:

```text
https://github.com/sigstore/policy-controller
```

Sigstore Helm charts:

```text
https://github.com/sigstore/helm-charts
```

GitHub Artifact Attestations:

```text
https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations
```

GitHub Artifact Attestations trust policy chart:

```text
https://github.com/github/artifact-attestations-helm-charts
```

Kubernetes admission webhooks:

```text
https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/
```

Argo CD diff customization:

```text
https://argo-cd.readthedocs.io/en/stable/user-guide/diffing/
```

Prometheus Operator ServiceMonitor:

```text
https://prometheus-operator.dev/docs/api-reference/api/
```

---

# 81. Related AI Platform Documentation

```text
022-sbom-and-provenance.md
023-github-container-registry.md
025-image-digest-update-workflow.md
026-gitops-pr-validation.md
028-promotion-workflow.md
029-rollback-strategy.md
030-argocd-sync-selfheal-and-prune.md
032-github-attestation-trust.md
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
