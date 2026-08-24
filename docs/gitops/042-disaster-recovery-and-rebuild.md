# Disaster Recovery and Rebuild

## Purpose

This document is the **full disaster-recovery and rebuild runbook** for the AI Platform.

It is written to answer one operational question:

> **If the cluster or a critical platform component is lost, how do we rebuild the platform from known-good sources without bypassing the security model?**

The recovery model is:

```text
Git repositories
    |
    +--> source history
    +--> GitOps desired state
    |
    v
cluster/bootstrap
    |
    +--> namespaces
    +--> Argo CD
    +--> AppProject
    +--> root Application
    |
    v
child Applications
    |
    +--> operator
    +--> API
    +--> gateway
    +--> monitoring
    +--> policies
    +--> policy-controller
    +--> trust-policies
    |
    v
runtime secrets restored separately
    |
    v
admission controls restored
    |
    v
workloads reconciled
    |
    v
validation and negative tests
```

This runbook deliberately separates:

```text
declarative state recoverable from Git
```

from:

```text
secret material that must not be stored in Git
```

The target is not merely:

```text
cluster comes back
```

The target is:

```text
cluster returns to a known-good, Git-controlled, admission-enforced, observable state
```

---

# 1. Recovery Scope

This runbook covers recovery from:

```text
full kind cluster loss
Argo CD loss
Policy Controller loss
trust-policy loss
monitoring loss
application workload loss
Git drift
bad GitOps merge
bad image promotion
runtime Secret loss
GitHub App credential loss
```

It does not assume:

```text
External Secrets Operator
Vault CSI Driver
automatic cluster backup/restore
```

unless those are later implemented and verified.

---

# 2. Sources of Truth

Recovery depends on different systems for different state.

## Source repository

```text
/mnt/data/ai-platform-operator
```

Contains:

```text
application/operator source
CI workflows
release workflow
Dockerfiles
security pipeline
```

## GitOps repository

```text
/mnt/data/ai-platform-gitops
```

Contains:

```text
Argo Applications
Kustomize overlays
namespace definitions
policies
monitoring
digest-pinned desired state
```

## Vault

Endpoint:

```text
https://vault.platform.local:8200
```

Source of truth for runtime secret material.

## GitHub

Stores:

```text
repository history
rulesets
GitHub App configuration
GitHub Actions Secrets
workflow run history
GHCR images
artifact attestations
```

---

# 3. Recovery Principle

Do not recover the platform by manually recreating live resources from memory.

The preferred sequence is:

```text
bootstrap minimum control plane
    |
    v
restore GitOps control
    |
    v
restore declarative workloads
    |
    v
restore secrets outside Git
    |
    v
validate security controls
```

Manual `kubectl apply` is used only where bootstrap requires it.

---

# 4. What Git Can Rebuild

GitOps should be able to restore:

```text
namespaces
operator Deployment
API Deployment
Gateway configuration
monitoring resources
native admission policies
Policy Controller Argo Application
trust-policies Argo Application
ModelService examples
Argo child Applications
```

Git should not be expected to restore:

```text
real passwords
private keys
GitHub App private key
Vault tokens
runtime secret values
```

---

# 5. What Must Be Recovered Outside Git

External secure recovery is required for:

```text
Vault data
GitHub App private key
GitHub Actions Secrets
TLS private keys if not automatically reissued
runtime Kubernetes Secret values
Keycloak bootstrap/admin material if needed
future object-storage credentials
future database credentials
```

Do not put these into Git to simplify recovery.

---

# 6. Before Disaster — Record Recovery Inputs

Keep these values documented somewhere safe:

```text
source repository URL
GitOps repository URL
cluster name
Kubernetes version
Argo CD version
Policy Controller chart version
trust-policies chart version
required namespaces
Vault address
public platform domains
GitHub App name
GitHub App installation scope
```

Validated values:

```text
cluster:
ai-platform-policy

context:
kind-ai-platform-policy

Kubernetes:
v1.36.1

Argo CD:
v3.5.1

Policy Controller chart:
0.10.6

Policy Controller app:
0.13.1

Trust policies:
v0.7.0
```

---

# 7. Disaster Scenario A — Full Cluster Loss

Assumption:

```text
kind cluster no longer exists
```

Check:

```bash
kind get clusters
```

If `ai-platform-policy` is absent, perform full rebuild.

---

# 8. Step 1 — Recreate kind Cluster

Use the project-standard kind configuration.

If the exact config file is stored in the repository, use it.

Example discovery:

```bash
cd /mnt/data/ai-platform-operator

find . \
  -maxdepth 4 \
  -type f \
  \( -iname '*kind*.yaml' -o -iname '*kind*.yml' \) \
  -print
```

Also inspect GitOps if needed:

```bash
cd /mnt/data/ai-platform-gitops

find . \
  -maxdepth 4 \
  -type f \
  \( -iname '*kind*.yaml' -o -iname '*kind*.yml' \) \
  -print
```

Do not invent the cluster networking config.

Create using the actual file:

```bash
kind create cluster \
  --name ai-platform-policy \
  --config <ACTUAL_KIND_CONFIG>
```

Expected:

```text
cluster created
```

---

# 9. Step 2 — Verify Cluster Context

```bash
kubectl config current-context
```

Expected:

```text
kind-ai-platform-policy
```

Verify version:

```bash
kubectl version
```

Expected:

```text
v1.36.1
```

If version differs, validate compatibility before continuing.

---

# 10. Step 3 — Restore Core Namespaces

If namespace manifests are in GitOps, render them.

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/namespaces/overlays/dev \
  >/tmp/rebuild-namespaces.yaml
```

Inspect:

```bash
cat /tmp/rebuild-namespaces.yaml
```

Apply:

```bash
kubectl apply \
  -f /tmp/rebuild-namespaces.yaml
```

Expected namespaces include:

```text
ai-platform
ai-platform-operator-system
argocd
cosign-system
monitoring
gateway-system
envoy-gateway-system
keycloak
```

Some may be created by component installers instead.

---

# 11. Step 4 — Restore Argo CD

Validated version:

```text
v3.5.1
```

Use the exact installation method documented in the Argo bootstrap guide.

After install:

```bash
kubectl get pods \
  -n argocd
```

Expected:

```text
all core Argo CD components Ready
```

Verify server remains:

```text
ClusterIP
```

Do not expose it publicly as part of recovery unless the architecture explicitly requires it.

---

# 12. Step 5 — Restore Argo CLI Access

Use the bootstrap access method:

```bash
kubectl port-forward \
  -n argocd \
  svc/argocd-server \
  8080:443
```

Then authenticate using the approved bootstrap/break-glass flow.

Long-term target remains:

```text
OIDC with Keycloak
local admin disabled for routine use
```

Do not leave bootstrap admin credentials active permanently.

---

# 13. Step 6 — Restore AppProject

The AppProject is bootstrap-managed.

File:

```text
argocd/projects/ai-platform.yaml
```

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

Expected:

```text
AppProject ai-platform created/configured
```

---

# 14. Step 7 — Verify AppProject Permissions

Inspect:

```bash
kubectl get appproject \
  ai-platform \
  -n argocd \
  -o yaml
```

Confirm it allows only the intended:

```text
GitOps repository
Helm OCI repositories
destination namespaces
cluster resource kinds
```

Relevant cluster-scoped security resources include:

```text
TrustRoot
ClusterImagePolicy
ValidatingAdmissionPolicy
ValidatingAdmissionPolicyBinding
admission webhook configurations
```

Avoid wildcard permissions if exact kinds are sufficient.

---

# 15. Step 8 — Restore Root Application

Root Application file:

```text
clusters/dev/root-application.yaml
```

Apply:

```bash
kubectl apply \
  --dry-run=server \
  -f clusters/dev/root-application.yaml
```

Then:

```bash
kubectl apply \
  -f clusters/dev/root-application.yaml
```

Expected root:

```text
ai-platform-root
```

---

# 16. Step 9 — Keep Root Sync Manual

The root Application is intentionally manual.

Reason:

```text
it controls topology
repositories
namespaces
Helm sources
permissions
```

Do not enable automatic sync on the root during emergency rebuild just for convenience.

---

# 17. Step 10 — Inspect Child Applications

```bash
argocd app list
```

Expected children:

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

If missing, inspect:

```text
clusters/dev/apps/
```

---

# 18. Step 11 — Validate App-of-Apps Render

```bash
kubectl kustomize \
  clusters/dev/apps \
  >/tmp/rebuild-apps.yaml
```

Validate:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/rebuild-apps.yaml
```

Expected:

```text
render succeeds
```

---

# 19. Step 12 — Restore Child Applications

If root Application is already present, sync the root manually when ready.

Example:

```bash
argocd app sync \
  ai-platform-root
```

Then:

```bash
argocd app wait \
  ai-platform-root \
  --timeout 300
```

Do not assume child workloads will all become healthy immediately if secrets are still missing.

---

# 20. Step 13 — Restore Policy Controller Early

Policy Controller is part of the runtime security boundary.

Validate its child Application:

```bash
argocd app get \
  policy-controller \
  --refresh
```

Expected chart:

```text
0.10.6
```

Namespace:

```text
cosign-system
```

Wait:

```bash
argocd app wait \
  policy-controller \
  --sync \
  --health \
  --timeout 300
```

---

# 21. Step 14 — Restore GitHub Trust Policies

Inspect:

```bash
argocd app get \
  trust-policies \
  --refresh
```

Expected chart:

```text
v0.7.0
```

Wait:

```bash
argocd app wait \
  trust-policies \
  --sync \
  --health \
  --timeout 300
```

---

# 22. Step 15 — Verify TrustRoot

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

# 23. Step 16 — Verify ClusterImagePolicy

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

Expected image scope includes:

```text
ghcr.io/anselem-okeke/ai-platform-operator
ghcr.io/anselem-okeke/ai-platform-api
```

---

# 24. Step 17 — Verify Protected Namespace Labels

```bash
kubectl get ns \
  ai-platform \
  ai-platform-operator-system \
  --show-labels
```

Expected:

```text
policy.sigstore.dev/include=true
```

Do not continue assuming admission trust is active if these labels are missing.

---

# 25. Step 18 — Restore Native Admission Policies

Render:

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/policies/overlays/dev \
  >/tmp/rebuild-policies.yaml
```

Validate:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/rebuild-policies.yaml
```

Server dry-run:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/rebuild-policies.yaml
```

---

# 26. Step 19 — Verify Native Policies Live

```bash
kubectl get validatingadmissionpolicies
```

Then:

```bash
kubectl get validatingadmissionpolicybindings
```

Verify relevant policies use:

```yaml
failurePolicy: Fail
```

and bindings use:

```yaml
validationActions:
  - Deny
```

Use exact names from the repository.

---

# 27. Step 20 — Restore Monitoring

Sync monitoring child Application:

```bash
argocd app get \
  ai-platform-monitoring \
  --refresh
```

Use exact current name if different.

Wait:

```bash
argocd app wait \
  ai-platform-monitoring \
  --sync \
  --health \
  --timeout 300
```

---

# 28. Step 21 — Verify Prometheus

```bash
kubectl get pods \
  -n monitoring
```

Expected:

```text
Prometheus stack healthy
```

Validated Prometheus version:

```text
v3.13.2-distroless
```

---

# 29. Step 22 — Verify Policy Controller ServiceMonitor

```bash
kubectl get servicemonitor \
  policy-controller \
  -n monitoring \
  -o yaml
```

Expected:

```text
namespaceSelector includes cosign-system
selector matches metrics service
```

---

# 30. Step 23 — Verify PrometheusRule

```bash
kubectl get prometheusrule \
  policy-controller \
  -n monitoring \
  -o yaml
```

Expected label:

```text
release: kps
```

Expected alerts:

```text
PolicyControllerTargetDown
PolicyControllerReconcileFailures
PolicyControllerWebhookCertificateFailures
```

---

# 31. Step 24 — Restore Runtime Secrets

At this stage, workloads may still fail because Git does not contain secret values.

Use Vault:

```text
https://vault.platform.local:8200
```

as the source of truth.

The exact secret paths and auth mechanism must come from the actual environment documentation.

Do not invent them.

---

# 32. Step 25 — Identify Missing Kubernetes Secrets

Inspect workload events:

```bash
kubectl get events \
  -A \
  --sort-by=.lastTimestamp
```

Look for:

```text
Secret not found
secret key not found
volume mount failure
```

Then inspect workload references.

Example:

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o yaml \
  | grep -A6 -B3 \
    'secretKeyRef\|secretName'
```

Do not print Secret values.

---

# 33. Step 26 — Recreate Runtime Secrets Securely

Representative pattern:

```bash
kubectl create secret generic <SECRET_NAME> \
  -n <NAMESPACE> \
  --from-literal=<KEY1>="$VALUE1" \
  --from-literal=<KEY2>="$VALUE2" \
  --dry-run=client \
  -o yaml \
  | kubectl apply -f -
```

The values should come from Vault or another approved secure source.

Do not write real secret YAML to the GitOps repository.

---

# 34. Step 27 — Verify Secret Exists Without Printing Values

```bash
kubectl get secret \
  <SECRET_NAME> \
  -n <NAMESPACE>
```

List keys only:

```bash
kubectl get secret \
  <SECRET_NAME> \
  -n <NAMESPACE> \
  -o json \
  | jq -r '.data | keys[]'
```

Do not use:

```bash
kubectl get secret -o yaml
```

in shared logs.

---

# 35. Step 28 — Restore GitHub Actions Secrets

If the GitHub App private key or other CI secrets were lost, restore them in GitHub:

```text
Repository
-> Settings
-> Secrets and variables
-> Actions
```

Read the actual secret names from:

```text
.github/workflows/release-images.yml
```

Do not invent secret names.

---

# 36. Step 29 — Restore GitHub App Private Key

If no valid App private key remains:

```text
1. open GitHub App settings
2. generate a new private key
3. store it in the exact Actions Secret referenced by workflow
4. validate token creation
5. revoke old/unknown key if needed
```

Do not copy the key into Git.

---

# 37. Step 30 — Verify GitHub App Installation

App:

```text
ai-platform-gitops-bot
```

Expected installation scope:

```text
ai-platform-gitops repository only
```

Permissions:

```text
Contents: Read & write
Pull requests: Read & write
Metadata: Read
```

---

# 38. Step 31 — Validate Token Minting

Use a normal release workflow or a controlled token-validation run.

Expected:

```text
installation token created
GitOps repo accessible
```

Do not print the token.

---

# 39. Step 32 — Restore Keycloak if Required

If identity infrastructure is part of the lost cluster, restore Keycloak according to the identity runbook.

Validated version:

```text
26.7.0
```

Required realm resources include:

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

---

# 40. Step 33 — Reapply Keycloak OIDC Configuration

The existing automation previously created:

```text
groups
user memberships
OIDC clients
groups scope
group membership mapper
PKCE settings
redirect URIs
```

Use the actual scripts from the repository.

Do not recreate these manually from memory if automation exists.

---

# 41. Step 34 — Restore Argo OIDC

Argo should authenticate through:

```text
https://auth.ai-platform.local
```

Verify Argo URL:

```text
https://argocd.ai-platform.local
```

Test login through Keycloak.

Confirm group-to-role mapping works.

---

# 42. Step 35 — Disable Routine Local Admin

Once OIDC is working:

```text
rotate/remove bootstrap credentials
disable routine local admin usage
keep break-glass procedure documented
```

Do not leave bootstrap mode as the permanent recovery state.

---

# 43. Step 36 — Verify API and Operator Applications

API:

```bash
argocd app get \
  ai-platform-api \
  --refresh
```

Operator:

```bash
argocd app get \
  ai-platform-operator \
  --refresh
```

Expected:

```text
Synced
Healthy
```

after secrets and admission dependencies are restored.

---

# 44. Step 37 — Verify Live Image Digests

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
  -n ai-platform-operator-system
```

Then:

```bash
kubectl get deployment \
  <OPERATOR_DEPLOYMENT> \
  -n ai-platform-operator-system \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

Expected:

```text
digest-pinned GHCR images
```

---

# 45. Step 38 — Compare Live Digests to Git

Render:

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/recovery-api.yaml

kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/recovery-operator.yaml
```

Inspect:

```bash
grep -n 'image:' \
  /tmp/recovery-api.yaml \
  /tmp/recovery-operator.yaml
```

These must match live Deployment images.

---

# 46. Step 39 — Verify Positive Admission

Use the live trusted API digest:

```bash
API_IMAGE="$(kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[0].image}')"

echo "${API_IMAGE}"
```

Dry-run:

```bash
kubectl run recovery-positive \
  -n ai-platform \
  --image="${API_IMAGE}" \
  --restart=Never \
  --dry-run=server \
  -o yaml
```

Expected:

```text
allowed
```

---

# 47. Step 40 — Verify Mutable Tag Denial

```bash
kubectl run recovery-bad-tag \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api:latest' \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

---

# 48. Step 41 — Verify Public Image Denial

```bash
kubectl run recovery-nginx \
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

# 49. Step 42 — Verify Fake Digest Denial

```bash
kubectl run recovery-fake-digest \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' \
  --restart=Never \
  --dry-run=server
```

Expected:

```text
DENIED
```

Validated Sigstore error:

```text
no valid bundles exist in registry
```

---

# 50. Step 43 — Verify Bad Init Denial

Create:

```bash
cat >/tmp/recovery-bad-init.yaml <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: recovery-bad-init
  namespace: ai-platform
spec:
  restartPolicy: Never

  initContainers:
    - name: bad-init
      image: nginx:latest

  containers:
    - name: app
      image: ${API_IMAGE}
EOF
```

Test:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/recovery-bad-init.yaml
```

Expected:

```text
DENIED
```

---

# 51. Step 44 — Verify Ephemeral Denial

Create disposable trusted Pod:

```bash
kubectl run recovery-debug-base \
  -n ai-platform \
  --image="${API_IMAGE}" \
  --restart=Never
```

Attempt:

```bash
kubectl debug \
  -n ai-platform \
  recovery-debug-base \
  --image=nginx:latest
```

Expected:

```text
DENIED
```

Cleanup:

```bash
kubectl delete pod \
  recovery-debug-base \
  -n ai-platform
```

---

# 52. Step 45 — Verify Policy Controller Metrics

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system
```

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
  | grep '^policy_controller_reconcile_count' \
  | head
```

Expected:

```text
non-empty
```

---

# 53. Step 46 — Verify Prometheus Target

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

This proves monitoring recovery is complete enough to observe Policy Controller.

---

# 54. Step 47 — Verify PrometheusRule Selection

```bash
kubectl get prometheusrule \
  policy-controller \
  -n monitoring \
  -o jsonpath='{.metadata.labels}{"\n"}'
```

Expected:

```text
release:kps
```

If missing, the rules may exist but not be loaded.

---

# 55. Step 48 — Verify Argo Drift Is Clean

API:

```bash
argocd app diff \
  ai-platform-api
```

Operator:

```bash
argocd app diff \
  ai-platform-operator
```

Policy Controller:

```bash
argocd app diff \
  policy-controller
```

Expected:

```text
no unintended drift
```

---

# 56. Step 49 — Verify Known Narrow Webhook Ignore

The Policy Controller webhook may contain the controller-added selector:

```yaml
- key: webhooks.knative.dev/exclude
  operator: DoesNotExist
```

Argo should ignore only this exact controller-managed field.

Do not use a broad ignore after rebuild.

---

# 57. Recovery Scenario B — Argo CD Lost, Cluster Still Exists

If workloads are still running but Argo is gone:

```text
do not reapply every workload manually
```

Recover only the GitOps control plane first.

Sequence:

```text
1. reinstall Argo CD
2. restore AppProject
3. restore root Application
4. verify child Applications
5. compare live state against Git
6. allow Argo to reconcile
```

---

# 58. Argo Recovery — Reinstall

Use version:

```text
v3.5.1
```

After install:

```bash
kubectl get pods \
  -n argocd
```

Then apply:

```bash
kubectl apply \
  -f /mnt/data/ai-platform-gitops/argocd/projects/ai-platform.yaml
```

Then:

```bash
kubectl apply \
  -f /mnt/data/ai-platform-gitops/clusters/dev/root-application.yaml
```

---

# 59. Argo Recovery — Inspect Before Sync

Before syncing, inspect:

```bash
argocd app list
```

Then:

```bash
argocd app diff \
  ai-platform-api
```

If live state already differs from Git due to emergency manual changes, decide deliberately whether:

```text
Git should win
```

or:

```text
Git must first be updated
```

Do not let Argo overwrite a known emergency fix until that decision is made.

---

# 60. Recovery Scenario C — Policy Controller Lost

If `cosign-system` workload is missing:

```bash
kubectl get pods \
  -n cosign-system
```

Check Argo:

```bash
argocd app get \
  policy-controller \
  --refresh
```

If Application exists, allow Argo self-heal.

If Application is missing, restore from:

```text
clusters/dev/apps/
```

Do not manually install a second Helm release in another namespace.

---

# 61. Policy Controller Recovery — Avoid CRD Ownership Conflict

A real previous failure occurred when attempting a second Policy Controller release in another namespace while CRDs were already owned by:

```text
release-name:
policy-controller

release-namespace:
cosign-system
```

Correct model:

```text
one standardized Policy Controller release
namespace = cosign-system
```

Do not install a competing release in:

```text
artifact-attestations
```

---

# 62. Recovery Scenario D — Trust Policies Lost

Check:

```bash
kubectl get trustroots.policy.sigstore.dev
kubectl get clusterimagepolicies.policy.sigstore.dev
```

If missing:

```bash
argocd app sync \
  trust-policies
```

Expected:

```text
TrustRoot github restored
ClusterImagePolicy github-policy restored
```

Then re-run positive/fake-digest admission tests.

---

# 63. Recovery Scenario E — Monitoring Lost

Sync:

```bash
argocd app sync \
  ai-platform-monitoring
```

Verify:

```bash
kubectl get servicemonitor \
  policy-controller \
  -n monitoring
```

```bash
kubectl get prometheusrule \
  policy-controller \
  -n monitoring
```

Then verify Prometheus target `up == 1`.

---

# 64. Recovery Scenario F — Bad GitOps Merge

If a bad desired-state commit is already on `main`:

```text
do not patch the cluster first
```

Identify commit:

```bash
cd /mnt/data/ai-platform-gitops

git log --oneline -20
```

Create rollback branch:

```bash
git switch -c rollback/<DESCRIPTION>
```

Revert:

```bash
git revert <BAD_COMMIT>
```

Render affected overlays.

Run GitOps validation.

Push and open PR.

---

# 65. Bad GitOps Merge — Validate Rollback

For image rollback:

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/rollback-api.yaml

kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/rollback-operator.yaml
```

Then:

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/rollback-api.yaml \
  /tmp/rollback-operator.yaml
```

Run:

```bash
git diff --check
```

Merge only after validation.

---

# 66. Recovery Scenario G — Bad Image Promotion

If new images are unhealthy but the supply-chain controls are functioning:

```text
revert GitOps digest promotion
```

Do not:

```text
rebuild old source
use old mutable tag
kubectl set image
```

Use previous known-good digest.

---

# 67. Identify Previous Known-Good Digest

```bash
git log \
  -p \
  -- platform/api/overlays/dev/kustomization.yaml \
     platform/operator/overlays/dev/kustomization.yaml
```

Select prior promotion.

Validate that digest still has:

```text
trusted attestation
previous successful runtime history
```

Then revert through Git.

---

# 68. Recovery Scenario H — Runtime Secret Lost

Symptom:

```text
Pod fails because Secret is missing
```

Check events:

```bash
kubectl get events \
  -n <NAMESPACE> \
  --sort-by=.lastTimestamp
```

Check reference:

```bash
kubectl get deployment \
  <DEPLOYMENT> \
  -n <NAMESPACE> \
  -o yaml \
  | grep -A6 -B3 \
    'secretKeyRef\|secretName'
```

Recover the secret from Vault.

Do not add the value to Git.

---

# 69. Runtime Secret Recovery — Verify Key Names

After recreating Secret:

```bash
kubectl get secret \
  <SECRET_NAME> \
  -n <NAMESPACE> \
  -o json \
  | jq -r '.data | keys[]'
```

Compare to:

```text
secretKeyRef.key
```

If application reads secrets only at startup, restart safely:

```bash
kubectl rollout restart \
  deployment/<DEPLOYMENT> \
  -n <NAMESPACE>
```

---

# 70. Recovery Scenario I — GitHub App Key Lost

Generate a new App private key.

Store in GitHub Actions Secret referenced by:

```text
release-images.yml
```

Run a controlled release.

Expected:

```text
token creation succeeds
GitOps branch created
GitOps PR created
```

Revoke unknown/old keys.

---

# 71. Recovery Scenario J — Repository History Lost Locally

If local clone is corrupted:

```text
delete only local clone
reclone from GitHub
```

Source:

```bash
git clone \
  git@github.com:anselem-okeke/ai-platform-operator.git \
  /mnt/data/ai-platform-operator
```

GitOps:

```bash
git clone \
  https://github.com/anselem-okeke/ai-platform-gitops.git \
  /mnt/data/ai-platform-gitops
```

Then verify branch/ruleset state in GitHub.

---

# 72. Recovery Scenario K — GHCR Image Missing

If the digest referenced by GitOps no longer exists in GHCR:

```text
do not silently rebuild with the same tag
```

The digest is content identity.

Options:

```text
restore registry artifact from backup if available
rebuild from exact source commit to a new digest
create new attestation
promote new digest through GitOps
```

A rebuild is a new artifact identity even from the same source.

---

# 73. Rebuild from Exact Source Commit

Find source SHA from GitOps commit message:

```text
chore(dev): deploy images from <source-sha>
```

Checkout source:

```bash
cd /mnt/data/ai-platform-operator

git fetch --all --prune

git switch --detach <SOURCE_SHA>
```

Run the normal release pipeline.

Do not manually push an unaudited image.

---

# 74. Recovery Scenario L — Attestation Missing

If image exists but Sigstore denies because trusted evidence is missing:

```text
do not disable admission
```

Determine whether:

```text
attestation was never created
attestation was deleted
wrong digest promoted
trust policy changed
```

Preferred recovery:

```text
produce a new properly attested release
promote through GitOps
```

Do not forge/handcraft attestation outside the normal workflow.

---

# 75. Recovery Scenario M — Native Admission Policy Missing

Check:

```bash
kubectl get validatingadmissionpolicies
kubectl get validatingadmissionpolicybindings
```

If missing:

```bash
argocd app sync \
  ai-platform-policies
```

Use actual Application name.

Then re-run:

```text
mutable tag denial
public image denial
bad init denial
fake digest denial
```

---

# 76. Recovery Scenario N — Protected Namespace Label Missing

Check:

```bash
kubectl get ns \
  ai-platform \
  ai-platform-operator-system \
  --show-labels
```

Restore through GitOps namespace manifests.

Do not manually label only one live namespace and leave Git unchanged.

---

# 77. Recovery Scenario O — AppProject Missing

If child Applications fail with permission errors:

```bash
kubectl get appproject \
  ai-platform \
  -n argocd
```

If absent:

```bash
cd /mnt/data/ai-platform-gitops

kubectl apply \
  -f argocd/projects/ai-platform.yaml
```

Then refresh Applications.

---

# 78. Recovery Scenario P — Root Application Missing

Apply:

```bash
kubectl apply \
  -f /mnt/data/ai-platform-gitops/clusters/dev/root-application.yaml
```

Keep sync manual.

Inspect before syncing.

---

# 79. Recovery Scenario Q — One Child Application Missing

Inspect:

```text
clusters/dev/apps/
```

Render:

```bash
kubectl kustomize \
  clusters/dev/apps \
  >/tmp/apps.yaml
```

Apply root or let root reconcile.

Do not create an ad hoc standalone Application outside Git.

---

# 80. Recovery Scenario R — Argo Self-Heal Not Working

Check child Application:

```bash
argocd app get \
  <APP> \
  -o yaml
```

Verify automated sync settings.

Look for:

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

Use actual manifest.

If missing from Git, fix Git.

---

# 81. Recovery Scenario S — Argo Prune Risk

Do not test destructive whole-resource prune casually during recovery.

The project has validated:

```text
drift self-heal
Git revert rollback
```

but not exhaustive whole-resource destructive prune scenarios.

Do not claim otherwise.

---

# 82. Recovery Scenario T — Webhook Drift After Rebuild

If Policy Controller remains OutOfSync due to:

```text
webhooks.knative.dev/exclude
```

verify the narrow `ignoreDifferences` is present.

Do not broad-ignore:

```text
entire MutatingWebhookConfiguration
entire ValidatingWebhookConfiguration
```

---

# 83. Recovery Validation — Source CI

After rebuild, validate source branch still enforces:

```text
Gitleaks
Lint
E2E
Tests
govulncheck
CodeQL
```

Inspect PR checks:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-operator
```

---

# 84. Recovery Validation — Source Ruleset

```bash
gh api \
  repos/anselem-okeke/ai-platform-operator/rulesets/21120105
```

Expected:

```text
Source Main Protection
active
no bypass
```

Branch-protection state is not restored by Kubernetes GitOps.

It must still exist in GitHub.

---

# 85. Recovery Validation — GitHub App

Run a normal release after rebuild.

Expected:

```text
short-lived token
automation/image-<source-sha>
bot commit
GitOps PR
```

This proves cross-repository automation is restored.

---

# 86. Recovery Validation — GitOps CI

Open a harmless GitOps PR.

Expected required check:

```text
Validate GitOps Manifests
```

Also perform a disposable malformed-image negative test if needed.

Expected:

```text
merge blocked
```

---

# 87. Recovery Validation — End-to-End Delivery

After recovery, run one normal source change through:

```text
source PR
source CI
merge
release
GHCR
attestation
GitOps PR
human merge
Argo
admission
runtime
```

Do not consider a rebuild complete only because pods are green.

The delivery path itself must work again.

---

# 88. Recovery Validation — Git Rollback

Perform a controlled rollback exercise using a recent known-good promotion.

Expected:

```text
Git revert
PR validation
human merge
Argo reconciliation
previous digest restored
```

This proves recovery remains reversible.

---

# 89. Recovery Validation — Secret Scanning

Source:

```bash
cd /mnt/data/ai-platform-operator

gitleaks git \
  --redact
```

GitOps:

```bash
cd /mnt/data/ai-platform-gitops

gitleaks git \
  --redact
```

Expected:

```text
clean
```

Do not restore secrets by committing temporary values during disaster recovery.

---

# 90. Recovery Validation — No Manual Drift

Run:

```bash
argocd app list
```

Then inspect important children:

```bash
argocd app diff ai-platform-api
argocd app diff ai-platform-operator
argocd app diff policy-controller
```

Expected:

```text
no unintended drift
```

---

# 91. Recovery Validation — Monitoring

Verify:

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

Query:

```promql
policy_controller_reconcile_count
```

Expected:

```text
non-empty
```

---

# 92. Recovery Validation — Alerts Loaded

Verify:

```bash
kubectl get prometheusrule \
  policy-controller \
  -n monitoring \
  -o yaml
```

Expected alerts:

```text
PolicyControllerTargetDown
PolicyControllerReconcileFailures
PolicyControllerWebhookCertificateFailures
```

Do not claim notification routing is restored unless Alertmanager routing is also explicitly validated.

---

# 93. Recovery Evidence

For a full rebuild, record:

```text
cluster creation time
Kubernetes version
Argo version
GitOps commit used for rebuild
Policy Controller version
trust-policy version
source main SHA
GitOps main SHA
API live digest
operator live digest
positive admission result
negative admission results
Prometheus target result
```

Do not store:

```text
tokens
passwords
private keys
```

in the recovery record.

---

# 94. Minimal Rebuild Record Example

```text
Cluster:
ai-platform-policy

Kubernetes:
v1.36.1

Argo CD:
v3.5.1

GitOps SHA:
<GITOPS_SHA>

Policy Controller:
0.10.6

Trust Policies:
v0.7.0

API Image:
ghcr.io/anselem-okeke/ai-platform-api@sha256:<64hex>

Operator Image:
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<64hex>

Admission Positive:
PASS

Mutable Tag Negative:
PASS

Fake Digest Negative:
PASS

Prometheus Target:
1
```

---

# 95. What Must Be Verified from the Actual Repositories

Do not invent:

```text
kind config filename
exact Argo install manifest command
exact current child Application names
exact native policy names
exact CEL expressions
exact runtime Secret names
exact Vault secret paths
exact GitHub Actions secret names
exact Keycloak bootstrap script paths
exact Gateway recovery order
```

Inspect source:

```bash
cd /mnt/data/ai-platform-operator

find . \
  -maxdepth 4 \
  -type f \
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
```

Inspect critical bootstrap files:

```bash
sed -n '1,360p' \
  argocd/projects/ai-platform.yaml

sed -n '1,320p' \
  clusters/dev/root-application.yaml
```

Use the committed repository as the exact rebuild source of truth.

---

# 96. References

Argo CD disaster recovery / operations documentation:

```text
https://argo-cd.readthedocs.io/
```

Kubernetes cluster administration:

```text
https://kubernetes.io/docs/tasks/administer-cluster/
```

Sigstore Policy Controller:

```text
https://docs.sigstore.dev/policy-controller/overview/
```

HashiCorp Vault:

```text
https://developer.hashicorp.com/vault/docs
```
