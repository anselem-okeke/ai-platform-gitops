# Argo CD Sync, Self-Heal, Prune, and Drift Management

## Purpose

This document is the **reproducible implementation and operations guide** for Argo CD synchronization behavior in the AI Platform.

It explains how the platform uses Argo CD to:

```text
detect Git changes
reconcile desired state
self-heal live drift
prune resources removed from Git
report sync/health state
recover from reconciliation problems
```

It also documents an important architectural distinction:

```text
root Application
    = manually synchronized topology/bootstrap boundary

child Applications
    = automated sync + selfHeal + prune
```

A new engineer should be able to reconstruct, validate, troubleshoot, and safely operate Argo CD reconciliation using this guide and the GitOps repository.

---

# 1. Implementation Context

## Argo CD Version

Validated:

```text
v3.5.1
```

Namespace:

```text
argocd
```

## GitOps Repository

```text
/mnt/data/ai-platform-gitops
```

Remote:

```text
https://github.com/anselem-okeke/ai-platform-gitops.git
```

## Root Application

Expected file:

```text
clusters/dev/root-application.yaml
```

The root Application is intentionally:

```text
manual sync
```

## Child Applications

Defined under:

```text
clusters/dev/apps/
```

Typical current child Applications include:

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

These use:

```text
automated sync
selfHeal
prune
```

where validated.

---

# 2. Why Root and Child Applications Use Different Sync Policies

The root Application controls **platform topology**.

Changes to it may:

```text
add/remove child Applications
change repository locations
change target namespaces
change project references
change Helm repositories
change application structure
change cluster-scoped permissions
```

These are higher-risk than a normal desired-state update within an existing child.

Therefore:

```text
root:
manual synchronization

children:
automated reconciliation
```

This provides a deliberate privilege boundary.

---

# 3. Root Application Flow

```text
clusters/dev/root-application.yaml
        |
        v
Application ai-platform-root
        |
        v
clusters/dev/apps/
        |
        +--> operator
        +--> api
        +--> gateway
        +--> monitoring
        +--> modelservices
        +--> policies
        +--> namespaces
        +--> policy-controller
        +--> trust-policies
```

A new child Application should not silently appear in the cluster merely because a topology file changed in Git if the root remains manual.

---

# 4. Child Application Flow

For a normal existing child:

```text
GitOps main changes
      |
      v
Argo polls/webhook refresh
      |
      v
child Application becomes OutOfSync
      |
      v
automated sync
      |
      v
Kubernetes desired state changes
      |
      v
Health evaluated
```

If live drift occurs:

```text
manual cluster change
      |
      v
Argo detects drift
      |
      v
selfHeal
      |
      v
Git state restored
```

---

# 5. Inspect Current Root Application

From the GitOps repo:

```bash
cd /mnt/data/ai-platform-gitops

sed -n '1,260p' \
  clusters/dev/root-application.yaml
```

Look for:

```yaml
spec:
  syncPolicy:
```

The root should **not** be configured with the same automatic child behavior unless the architecture is intentionally changed.

---

# 6. Inspect Current Child Applications

Render all child Applications:

```bash
kubectl kustomize \
  clusters/dev/apps \
  >/tmp/dev-applications.yaml
```

Inspect sync policy:

```bash
grep -n -A12 -B4 \
  'syncPolicy:' \
  /tmp/dev-applications.yaml
```

Expected child pattern:

```yaml
syncPolicy:
  automated:
    prune: true
    selfHeal: true
```

Exact YAML structure should be taken from the repository.

---

# 7. Automated Sync

Automated sync means:

```text
Argo does not wait for a human to click Sync
```

when an existing child Application detects a Git change.

This is appropriate because promotion authorization already occurred at:

```text
GitOps PR merge
```

The deployment decision is therefore:

```text
Git merge
```

not:

```text
Argo UI click
```

---

# 8. Why Automated Child Sync Is Consistent with GitOps

The intended chain is:

```text
validated GitOps PR
      |
      v
human merge
      |
      v
Git desired state approved
      |
      v
Argo automatically reconciles
```

If every child required manual Argo sync after merge, Git would no longer be the complete deployment authorization boundary.

---

# 9. selfHeal

`selfHeal: true` means Argo attempts to restore Git state if a managed live resource drifts.

Example:

```text
Git:
replicas: 2

Live:
replicas: 5
```

Argo detects:

```text
OutOfSync
```

and reconciles back to:

```text
replicas: 2
```

subject to resource ownership, ignore rules, sync behavior, and controller interactions.

---

# 10. prune

`prune: true` allows Argo to remove managed resources that are no longer part of desired state.

Conceptually:

```text
Git contains Resource A
Argo manages A

Git removes A
      |
      v
Argo may delete A
```

This is powerful and potentially destructive.

---

# 11. Important Prune Limitation

The platform has validated normal reconciliation and drift self-heal.

Do **not** claim that destructive whole-resource prune has been exhaustively tested for every resource class.

Particularly sensitive examples:

```text
Namespace
PVC/PV-related resources
CRDs
cluster-scoped policy
identity infrastructure
stateful services
```

Before removing critical resources from Git, inspect:

```text
prune behavior
finalizers
retention expectations
data implications
```

---

# 12. Inspect an Application with Argo CLI

Example API:

```bash
argocd app get \
  ai-platform-api \
  --refresh
```

Expected important fields:

```text
Sync Status
Health Status
Revision
Sync Policy
```

---

# 13. Inspect Operator Application

```bash
argocd app get \
  ai-platform-operator \
  --refresh
```

---

# 14. List All Applications

```bash
argocd app list
```

or:

```bash
kubectl get applications \
  -n argocd
```

---

# 15. Inspect Application YAML from Cluster

```bash
kubectl get application \
  ai-platform-api \
  -n argocd \
  -o yaml
```

Search:

```bash
kubectl get application \
  ai-platform-api \
  -n argocd \
  -o jsonpath='{.spec.syncPolicy}{"\n"}'
```

---

# 16. Validate Child Automated Sync

For an existing child Application, make a controlled non-destructive GitOps change.

Example:

```text
change a harmless annotation
```

through a GitOps PR.

After merge:

```bash
argocd app get \
  ai-platform-api \
  --refresh
```

Expected sequence:

```text
OutOfSync
   ↓
Syncing
   ↓
Synced
```

No manual `argocd app sync` should be needed.

---

# 17. Validate selfHeal with a Safe Drift Test

Use a field that is:

```text
safe
non-destructive
not owned by another controller
```

For example, a temporary annotation on a directly managed Deployment can be used if it is part of Argo-managed desired state.

First inspect:

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o yaml
```

Then choose a safe, reversible field.

Do **not** use destructive fields for drift tests.

---

# 18. Example Drift Test

If the Git manifest contains a managed annotation:

```yaml
metadata:
  annotations:
    platform.anselem.dev/drift-test: "git"
```

temporarily patch live state:

```bash
kubectl patch deployment \
  ai-platform-api \
  -n ai-platform \
  --type merge \
  -p '{
    "metadata": {
      "annotations": {
        "platform.anselem.dev/drift-test": "manual"
      }
    }
  }'
```

Observe Argo.

Expected:

```text
OutOfSync
   ↓
selfHeal
   ↓
annotation restored to Git value
```

Only use this exact example if the field is actually managed in Git.

Otherwise select a safe existing field.

---

# 19. Observe Drift

```bash
argocd app get \
  ai-platform-api \
  --refresh
```

Inspect diff:

```bash
argocd app diff \
  ai-platform-api
```

---

# 20. Verify selfHeal Completes

```bash
argocd app wait \
  ai-platform-api \
  --sync \
  --health \
  --timeout 300
```

Then inspect live field.

---

# 21. Why Manual `kubectl` Drift Is Not a Durable Fix

With self-heal enabled:

```text
kubectl edit
kubectl patch
kubectl scale
```

may be reverted by Argo if those fields are Git-managed.

Therefore durable changes must go through:

```text
GitOps PR
```

---

# 22. Manual Emergency Changes

Emergency changes can still be necessary.

If used:

```text
1. record exact action
2. understand self-heal may revert it
3. create matching Git correction immediately
4. restore Git/live consistency
```

Do not treat live manual changes as normal platform operation.

---

# 23. Scaling and selfHeal

If replicas are managed in Git:

```text
kubectl scale
```

may be reverted.

If another controller such as HPA owns replicas, Argo configuration must avoid fighting that controller.

The ownership model must be explicit.

---

# 24. Controller Ownership Conflicts

A common GitOps problem is:

```text
Argo owns field
Controller B owns same field
```

Result:

```text
permanent drift
repeated sync
reconciliation fight
```

Examples can include:

```text
HPA replicas
webhook-injected fields
cert-manager-managed data
controller-generated selectors
status fields
```

Use narrow `ignoreDifferences` only when ownership is well understood.

---

# 25. ignoreDifferences

Argo supports ignoring selected diffs.

This should be used only for:

```text
known controller-owned fields
known server-normalized fields
known unavoidable mutations
```

Never use broad ignore rules to make:

```text
OutOfSync disappear
```

without understanding the cause.

---

# 26. Validated Narrow Ignore Rule

The platform encountered a real Policy Controller drift issue.

The live webhook configuration gained the Knative selector:

```yaml
- key: webhooks.knative.dev/exclude
  operator: DoesNotExist
```

This selector was controller-generated.

The fix was a **narrow ignore rule** only for that exact selector on the Policy Controller webhook configuration.

---

# 27. Why Broad Webhook Ignore Is Dangerous

Bad:

```yaml
ignoreDifferences:
  - group: admissionregistration.k8s.io
    kind: MutatingWebhookConfiguration
```

with a broad pointer covering large portions of webhook config.

This can hide:

```text
wrong service reference
wrong CA bundle
wrong failurePolicy
wrong namespace selector
wrong rules
security drift
```

Only ignore the exact known controller-owned difference.

---

# 28. RespectIgnoreDifferences

For the validated Policy Controller case:

```text
RespectIgnoreDifferences=true
```

is required so synchronization respects the declared ignored field.

Without it, Argo may still attempt to write ignored fields during sync depending on configuration.

---

# 29. Inspect ignoreDifferences in Git

Search:

```bash
cd /mnt/data/ai-platform-gitops

grep -RIn \
  'ignoreDifferences\|RespectIgnoreDifferences' \
  clusters \
  platform \
  argocd
```

Inspect the exact Application definition before changing it.

---

# 30. Verify No Overbroad Ignore Rules

Review every ignore rule.

Ask:

```text
Which controller owns this field?
Why does Git differ from live?
Why is this exact path safe to ignore?
Could security-sensitive drift be hidden?
```

If these questions cannot be answered, the ignore rule is not ready.

---

# 31. Manual Root Sync

Because the root Application is intentionally manual, topology changes require an explicit synchronization step.

After an approved GitOps merge that changes:

```text
clusters/dev/apps/
```

or root topology, inspect:

```bash
argocd app get \
  ai-platform-root \
  --refresh
```

Expected:

```text
OutOfSync
```

until manually synchronized.

---

# 32. Synchronize Root Deliberately

Only after reviewing the topology diff:

```bash
argocd app diff \
  ai-platform-root
```

Then:

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

---

# 33. Why Root Sync Is Privileged

A root sync can:

```text
create new child Application
delete child Application
change repository/chart source
change destination namespace
change AppProject
alter platform topology
```

Therefore do not automate root sync merely for convenience.

---

# 34. Adding a New Child Application

Example future Phase 8 child:

```text
kserve
```

Likely GitOps additions:

```text
platform/kserve/...
clusters/dev/apps/kserve.yaml
clusters/dev/apps/kustomization.yaml
```

Flow:

```text
PR
  |
  v
merge
  |
  v
root becomes OutOfSync
  |
  v
review root diff
  |
  v
manual root sync
  |
  v
child Application created
  |
  v
child automated reconciliation begins
```

---

# 35. Existing Child Updates Do Not Need Root Sync

If only this changes:

```text
platform/api/overlays/dev/kustomization.yaml
```

the existing `ai-platform-api` child Application sees the Git change itself.

Do not sync root unnecessarily.

---

# 36. App-of-Apps Source Path

The root consumes:

```text
clusters/dev/apps/
```

This path contains the child Application definitions.

Validate:

```bash
kubectl kustomize \
  clusters/dev/apps \
  >/tmp/apps.yaml
```

before root sync.

---

# 37. Sync Waves

If sync waves are introduced, they can order resources.

Example:

```text
Namespace
   ↓
CRD/controller
   ↓
custom resources
```

The current guide does not claim sync waves are used everywhere.

Verify repository annotations before relying on them.

---

# 38. Sync Options

Common Argo sync options include:

```text
CreateNamespace=true
ServerSideApply=true
RespectIgnoreDifferences=true
PruneLast=true
```

Do not add them globally without a concrete requirement.

Each changes reconciliation behavior.

---

# 39. `CreateNamespace=true`

This lets Argo create the destination namespace automatically.

However, the platform already has a dedicated:

```text
namespaces
```

GitOps component.

Avoid mixing namespace ownership unless intentionally designed.

---

# 40. `ServerSideApply=true`

Server-side apply can help with:

```text
large resources
field ownership
some CRD/resource cases
```

but changes field-management semantics.

Do not enable broadly as a generic fix.

---

# 41. `PruneLast=true`

This delays pruning until after other sync operations.

It can reduce some ordering risks.

Still does not make destructive prune universally safe.

---

# 42. Application Health vs Sync

These are different.

```text
Synced
```

means:

```text
live desired state matches Git according to Argo
```

```text
Healthy
```

means:

```text
Argo health assessment considers the resource operational
```

Possible states:

```text
Synced + Degraded
OutOfSync + Healthy
Synced + Progressing
```

Always inspect both.

---

# 43. Example Health Check

```bash
argocd app get \
  ai-platform-api
```

Look for:

```text
Sync Status: Synced
Health Status: Healthy
```

---

# 44. `argocd app wait`

Use:

```bash
argocd app wait \
  ai-platform-api \
  --sync \
  --health \
  --timeout 300
```

This is useful after promotion/rollback.

---

# 45. Argo Refresh

Normal:

```bash
argocd app get \
  ai-platform-api \
  --refresh
```

For harder cache/debug cases:

```bash
argocd app get \
  ai-platform-api \
  --hard-refresh
```

Use hard refresh when repository/manifest cache is suspected.

---

# 46. Troubleshooting: App Stays OutOfSync

Inspect:

```bash
argocd app diff \
  <APP>
```

Then inspect:

```text
field-level diff
resource ownership
defaulted fields
controller mutation
missing ignore rule
bad Git desired state
```

Do not repeatedly press Sync without understanding the diff.

---

# 47. Troubleshooting: App Repeatedly Syncs

Possible causes:

```text
mutating webhook changes field
controller owns field
non-deterministic rendering
server defaulting
timestamp/hash generation
incorrect ignoreDifferences
```

Use:

```bash
argocd app diff <APP>
```

and compare the same field across sync cycles.

---

# 48. Troubleshooting: App Is Synced but Deployment Is Failing

Inspect:

```bash
argocd app get <APP>
```

Then Kubernetes:

```bash
kubectl get pods -n <namespace>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

`Synced` does not guarantee runtime success.

---

# 49. Troubleshooting: App Is Healthy but Wrong Version Runs

Compare:

```text
Git digest
Argo revision
rendered manifest
live Deployment image
```

Git render:

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  | grep 'image:'
```

Live:

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o jsonpath='{.spec.template.spec.containers[*].image}{"\n"}'
```

---

# 50. Troubleshooting: Automated Sync Does Not Trigger

Check Application:

```bash
kubectl get application \
  <APP> \
  -n argocd \
  -o yaml
```

Verify:

```yaml
spec:
  syncPolicy:
    automated:
```

Also inspect:

```text
repo connectivity
revision/path
AppProject permission
refresh state
sync window
application conditions
```

---

# 51. Troubleshooting: selfHeal Does Not Restore Drift

Check:

```text
selfHeal enabled?
field ignored?
resource actually tracked?
another controller immediately rewrites field?
Argo app in error?
sync window?
```

Inspect:

```bash
argocd app diff <APP>
```

---

# 52. Troubleshooting: selfHeal Fights Another Controller

Symptom:

```text
continuous OutOfSync/sync loop
```

Identify field manager:

```bash
kubectl get <resource> \
  -n <namespace> \
  -o yaml
```

Inspect:

```text
managedFields
```

If another legitimate controller owns the field, consider a narrow ignore rule.

---

# 53. Troubleshooting: Prune Wants to Delete Unexpected Resource

Stop before sync if possible.

Inspect:

```bash
argocd app diff <APP>
```

Look for deletion marker.

Confirm:

```text
resource was intentionally removed from Git
resource belongs to this Application
resource is safe to delete
data retention is understood
```

Do not approve destructive prune reflexively.

---

# 54. Prune and Stateful Resources

For resources containing persistent data:

```text
PVC
stateful storage
database
object storage
```

resource deletion may have data impact depending on:

```text
reclaimPolicy
finalizers
StatefulSet PVC retention
operator behavior
```

Add component-specific deletion procedures before relying on prune.

---

# 55. Namespace Prune Risk

Deleting a Namespace can cascade-delete namespaced resources.

Therefore:

```text
Namespace removal from Git
```

is not a routine cleanup.

Require explicit review.

---

# 56. CRD Prune Risk

Deleting a CRD can delete or orphan associated custom resources depending on Kubernetes behavior and finalizers.

Treat CRD lifecycle as privileged.

---

# 57. Policy Prune Risk

Removing admission policies can change cluster trust boundaries.

Treat deletion of:

```text
ClusterImagePolicy
ValidatingAdmissionPolicy
Binding
webhook configuration
```

as a security change, not a routine prune.

---

# 58. Application Deletion Risk

Deleting a child Argo Application can interact with:

```text
finalizers
cascade deletion
prune behavior
orphaning
```

Review Application finalizers before removal.

---

# 59. Root Application Deletion Must Not Be Used as Cleanup

The root Application is the topology controller.

Deleting it is not a safe way to:

```text
reset
reinstall
clean up
```

Use documented rebuild/recovery procedures.

---

# 60. Argo Application Finalizer

Applications may include:

```text
resources-finalizer.argocd.argoproj.io
```

This can cause managed resources to be deleted when the Application is deleted.

Inspect before deleting:

```bash
kubectl get application \
  <APP> \
  -n argocd \
  -o jsonpath='{.metadata.finalizers}{"\n"}'
```

---

# 61. Safe Application Removal Procedure

Before removing a child Application:

```text
1. identify managed resources
2. identify stateful data
3. decide delete vs preserve
4. review finalizer
5. review prune setting
6. prepare rollback
7. merge Git change
8. manually sync root
9. observe result
```

Do not remove blindly.

---

# 62. Sync History

Inspect:

```bash
argocd app history \
  ai-platform-api
```

This gives deployment revision history useful for:

```text
audit
rollback target identification
incident investigation
```

---

# 63. Git Remains Authoritative for Rollback

Even though Argo has rollback commands, preferred durable rollback is:

```text
Git revert
```

See:

```text
029-rollback-strategy.md
```

---

# 64. Argo Rollback as Emergency Tool

Argo rollback may be used as an emergency mitigation.

However:

```text
if Git still contains the bad revision
```

automated reconciliation may reapply it.

Therefore follow with a Git correction immediately.

---

# 65. Sync Windows

Argo supports sync windows.

If introduced later, they can:

```text
allow
deny
manual-only
```

sync during defined periods.

The current project does not rely on sync windows for normal dev deployment unless verified in the repo.

---

# 66. Troubleshooting: Sync Blocked by Window

Inspect project/application policy.

Do not disable a production sync window without authorization.

---

# 67. AppProject Role

AppProject constrains:

```text
source repositories
destination clusters/namespaces
resource kinds
```

A sync can fail even with valid manifests if AppProject does not allow the resource.

Inspect:

```bash
kubectl get appproject \
  ai-platform \
  -n argocd \
  -o yaml
```

---

# 68. Common AppProject Sync Failure

Example:

```text
new cluster-scoped resource added
AppProject does not allow kind
```

Correct response:

```text
review whether resource is required
update AppProject deliberately
apply AppProject bootstrap change
```

Do not add wildcard permissions.

---

# 69. AppProject Is Bootstrap-Managed

The platform's `AppProject/ai-platform` is managed as a bootstrap resource.

Apply manually:

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

This is intentionally separate from normal child automated sync.

---

# 70. Repository Connectivity

If Argo cannot fetch Git:

```text
Application may show Unknown / ComparisonError
```

Inspect:

```bash
argocd app get <APP>
```

and Argo repo/server logs.

---

# 71. Argo Logs

List pods:

```bash
kubectl get pods \
  -n argocd
```

Controller logs:

```bash
kubectl logs \
  -n argocd \
  deployment/argocd-application-controller \
  --tail=200
```

Depending on installation, the controller may be a StatefulSet instead of Deployment.

Discover first:

```bash
kubectl get deploy,statefulset \
  -n argocd
```

---

# 72. Repo Server Logs

```bash
kubectl logs \
  -n argocd \
  deployment/argocd-repo-server \
  --tail=200
```

Useful for:

```text
Git fetch
Kustomize render
Helm fetch
manifest generation
```

---

# 73. Server Logs

```bash
kubectl logs \
  -n argocd \
  deployment/argocd-server \
  --tail=200
```

Useful for API/UI/authentication issues.

---

# 74. Application Controller Logs

Discover workload name first:

```bash
kubectl get deploy,statefulset \
  -n argocd \
  | grep application-controller
```

Then inspect logs.

---

# 75. Health Customization

Argo may not understand health for every CRD.

If a custom health script is introduced, document:

```text
resource kind
reason
Lua/health logic
upgrade implications
```

Do not mark everything Healthy by default.

---

# 76. Third-Party Helm Applications

Current external Argo Applications include:

```text
policy-controller
trust-policies
```

They use pinned chart versions.

Argo manages:

```text
Application definition
Helm chart source/version
values
resulting resources
```

Review drift carefully because Helm/controller-generated fields can differ.

---

# 77. Policy Controller Drift Case

The real drift case involved webhook mutation.

The correct response was:

```text
narrow ignore
```

not:

```text
disable selfHeal
disable sync
ignore all webhook changes
```

This should be the model for future drift handling.

---

# 78. Root Sync Checklist

Before root sync:

```text
[ ] GitOps PR merged
[ ] clusters/dev/apps renders
[ ] root diff reviewed
[ ] new source repositories allowed by AppProject
[ ] destination namespaces allowed
[ ] cluster-scoped resource permissions reviewed
[ ] Helm chart versions pinned
[ ] deletion impact understood
```

Then:

```bash
argocd app sync \
  ai-platform-root
```

---

# 79. Child Sync Checklist

For normal child changes:

```text
[ ] GitOps PR merged
[ ] child source path valid
[ ] validation workflow passed
[ ] Argo detects revision
[ ] automated sync starts
[ ] Synced
[ ] Healthy
[ ] live state verified
```

---

# 80. Drift-Test Checklist

```text
[ ] choose non-destructive managed field
[ ] capture original value
[ ] manually change live field
[ ] observe OutOfSync
[ ] observe selfHeal
[ ] confirm Git value restored
[ ] confirm app Synced/Healthy
[ ] confirm no unexpected side effects
```

---

# 81. Prune-Test Checklist

Because destructive whole-resource prune is not fully validated, prefer a disposable test resource.

Use only a resource with:

```text
no persistent data
no security-critical role
no cross-component dependency
```

Process:

```text
1. add disposable resource through Git
2. merge
3. verify Argo creates it
4. remove from Git
5. review diff
6. verify prune behavior
7. confirm no collateral deletion
```

Do not generalize this result to stateful/critical resources.

---

# 82. Do Not Use Production-Like Stateful Resources for First Prune Test

Avoid:

```text
Namespace
PVC
database
Vault
Keycloak
Prometheus storage
object storage
```

for a basic prune validation.

---

# 83. Automated Sync Failure Recovery

If automated sync enters repeated failure:

```text
1. inspect diff
2. inspect sync result
3. inspect events/logs
4. identify Git vs runtime cause
5. correct Git
6. allow Argo to reconcile
```

Avoid repeatedly retrying without changing the cause.

---

# 84. Temporarily Disabling Auto-Sync

This is an operationally significant action.

Do not do it casually.

If required during an incident:

```text
record reason
record application
record start time
restore after incident
reconcile Git afterward
```

Prefer fixing Git instead.

---

# 85. Temporarily Disabling selfHeal

Same caution.

Turning off self-heal can allow live drift to persist unnoticed.

Only use if:

```text
controller fight or emergency operation requires it
```

and restore it promptly.

---

# 86. Temporarily Disabling prune

This can be safer during migration if deletion behavior is uncertain.

However, leaving prune disabled changes lifecycle semantics.

Document any intentional exception.

---

# 87. Re-enable Verification

After any temporary sync-policy modification, verify:

```bash
kubectl get application \
  <APP> \
  -n argocd \
  -o jsonpath='{.spec.syncPolicy}{"\n"}'
```

Confirm desired policy restored.

---

# 88. Manual Sync of a Child

Manual child sync can be useful for troubleshooting:

```bash
argocd app sync \
  ai-platform-api
```

But if automation is working, normal deployment should not require this.

Frequent need for manual sync indicates a problem.

---

# 89. Selective Resource Sync

Argo supports selective sync.

Use cautiously because partial sync can create dependency mismatches.

The platform's normal operation should reconcile the full child Application.

---

# 90. Hard Refresh Before Escalating

If Git has changed but Argo seems stale:

```bash
argocd app get \
  <APP> \
  --hard-refresh
```

Then re-check diff/status.

---

# 91. Verify Git Revision

```bash
argocd app get \
  <APP> \
  -o json
```

Use `jq` to inspect current source/operation revision if needed.

Exact fields vary by Argo version/status state.

---

# 92. Verify GitOps Main

```bash
cd /mnt/data/ai-platform-gitops

git switch main
git pull --ff-only

git rev-parse HEAD
```

Compare to Argo's reported revision.

---

# 93. Application Manifest Source

Inspect:

```bash
kubectl get application \
  <APP> \
  -n argocd \
  -o jsonpath='{.spec.source.repoURL}{"\n"}{.spec.source.path}{"\n"}{.spec.source.targetRevision}{"\n"}'
```

Verify expected repository/path/revision.

---

# 94. Helm Application Source

For external Helm apps, inspect:

```bash
kubectl get application \
  <APP> \
  -n argocd \
  -o yaml
```

Confirm:

```text
repoURL
chart
targetRevision
values
```

---

# 95. Sync Status Unknown

Possible causes:

```text
repo unavailable
manifest generation failed
authentication failure
invalid Kustomize
invalid Helm values
```

Inspect Application conditions:

```bash
kubectl get application \
  <APP> \
  -n argocd \
  -o jsonpath='{.status.conditions}{"\n"}'
```

---

# 96. ComparisonError

A `ComparisonError` often means Argo cannot generate desired manifests.

Check:

```text
repo server logs
Kustomize path
Helm source
repository credentials
missing file
invalid syntax
```

---

# 97. Degraded Health

`Degraded` is usually a runtime condition.

Inspect resource tree:

```bash
argocd app get \
  <APP>
```

Then Kubernetes:

```bash
kubectl get all \
  -n <namespace>
```

and events.

---

# 98. Progressing Too Long

Check:

```text
readiness
image pull
admission
scheduling
PVC
startup
```

Argo itself may be working correctly while the workload is unhealthy.

---

# 99. OutOfSync Because of Status Fields

Argo normally ignores status appropriately for many resources.

Do not add ignore rules for status unless a real diff proves it is needed.

---

# 100. OutOfSync Because of List Ordering

Some APIs/controllers normalize list ordering.

First confirm:

```text
semantic content is same
controller/API server owns order
```

Then use the narrowest normalization/ignore approach available.

---

# 101. OutOfSync Because of Default Values

Kubernetes may default fields live that are absent in Git.

Prefer:

```text
make desired state explicit
```

when reasonable.

Use ignore only when the default is stable and controller-owned.

---

# 102. Rebuild Child Sync Policy from Zero

For a typical child Application, conceptually:

```yaml
spec:
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

Additional options should be added only when needed.

Validate against the actual current Application manifests before copying.

---

# 103. Rebuild Root Manual Policy from Zero

Root Application should omit automated sync or otherwise remain intentionally manual.

The key invariant:

```text
topology change requires explicit root sync
```

---

# 104. Full Rebuild Procedure

```text
[ ] install Argo CD v3.5.1
[ ] create AppProject
[ ] create root Application
[ ] keep root manual
[ ] define clusters/dev/apps
[ ] create child Applications
[ ] configure child automated sync
[ ] configure selfHeal
[ ] configure prune
[ ] validate app list
[ ] test normal child Git change
[ ] verify auto-sync
[ ] perform safe drift test
[ ] verify self-heal
[ ] inspect ignoreDifferences
[ ] confirm only narrow exceptions exist
[ ] test root topology change
[ ] verify root stays OutOfSync until manual sync
[ ] manually sync root
[ ] verify child creation
[ ] perform disposable prune test if needed
[ ] document destructive-prune limitations
```

---

# 105. Security Checklist

```text
[ ] root Application remains manual
[ ] child auto-sync only after Git merge
[ ] selfHeal enabled where expected
[ ] prune enabled only with understood lifecycle
[ ] no broad ignoreDifferences
[ ] RespectIgnoreDifferences used only where needed
[ ] AppProject least privilege maintained
[ ] no wildcard source/destination/resource expansion without review
[ ] manual live drift not normalized
[ ] emergency sync-policy changes audited
```

---

# 106. Operational Checklist

```text
[ ] `argocd app list` works
[ ] root status understood
[ ] child sync status understood
[ ] child health status understood
[ ] app diff reviewed when unexpected
[ ] repo revision matches expected Git state
[ ] rollout verified after sync
[ ] events checked on degradation
[ ] self-heal behavior validated
[ ] ignore rules reviewed periodically
```

---

# 107. Known Implementation Facts

Validated project facts:

```text
Argo CD:
v3.5.1

Root:
ai-platform-root
manual sync

Child Applications:
automated sync
selfHeal
prune

Git reconciliation:
validated

Drift self-heal:
validated

Rollback through Git:
validated

Whole-resource destructive prune:
not exhaustively validated

Known narrow ignore:
Policy Controller webhook
webhooks.knative.dev/exclude
operator: DoesNotExist

RespectIgnoreDifferences:
enabled for that narrow case
```

---

# 108. What Must Be Verified from the Actual Repository

Do not invent:

```text
exact syncOptions list
exact ignoreDifferences JSON pointers/JQ expressions
exact Application resource names if changed
exact current root syncPolicy YAML
exact current child Application names
exact AppProject allowlist after future additions
```

Inspect:

```text
clusters/dev/root-application.yaml
clusters/dev/apps/*
argocd/projects/ai-platform.yaml
```

and live Argo state.

---

# 109. Official References

Argo CD automated sync:

```text
https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/
```

Argo sync options:

```text
https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
```

Argo diff customization:

```text
https://argo-cd.readthedocs.io/en/stable/user-guide/diffing/
```

Argo prune behavior:

```text
https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/#automatic-pruning
```

Argo App-of-Apps:

```text
https://argo-cd.readthedocs.io/
```

Kubernetes declarative management:

```text
https://kubernetes.io/docs/tasks/manage-kubernetes-objects/declarative-config/
```

OpenGitOps:

```text
https://opengitops.dev/
```

---

# 110. Related AI Platform Documentation

```text
010-argocd-appproject.md
011-app-of-apps-bootstrap.md
012-kustomize-layout-and-overlays.md
024-github-app-gitops-automation.md
025-image-digest-update-workflow.md
026-gitops-pr-validation.md
027-branch-protection-and-rulesets.md
028-promotion-workflow.md
029-rollback-strategy.md
031-sigstore-policy-controller.md
039-software-supply-chain-security.md
040-end-to-end-delivery-workflow.md
041-validation-and-security-tests.md
042-rebuild-and-disaster-recovery.md
043-troubleshooting-guide.md
044-operations-runbook.md
045-command-reference.md
047-design-decisions.md
