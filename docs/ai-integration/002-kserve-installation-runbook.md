# KServe Installation Runbook

## Purpose

This runbook documents the KServe work completed for Phase 8 of the AI Platform. It is intended to let an engineer who did not participate in the original implementation understand **what KServe is, why it is used, how it was installed through GitOps, how to validate it, how to troubleshoot it, and how to reproduce the installation**.



---

# 1. What KServe Is

KServe is a Kubernetes-native model-serving platform.

It gives Kubernetes a higher-level API for serving machine-learning models. The main resource used in this platform is:

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
```

Instead of manually building a serving platform from Deployments, Services, model-server conventions, storage initializers, readiness logic, routing, and runtime selection, KServe provides a controller and CRDs that reconcile those concerns.

In simplified form:

```text
InferenceService
      |
      v
KServe Controller
      |
      v
Deployment / Service / runtime
      |
      v
Prediction endpoint
```

---

# 2. What Problem KServe Solves Here

Before Phase 8, the platform control path was:

```text
REST API
   |
   v
ModelService CR
   |
   v
Go Operator
   |
   v
Kubernetes workload
```

The platform now needs a real model-serving abstraction.

The selected architecture is:

```text
User / CLI
    |
    v
AI Platform REST API
    |
    v
ModelService
platform.anselem.dev/v1alpha1
    |
    v
AI Platform Operator
    |
    v
KServe InferenceService
serving.kserve.io/v1beta1
    |
    v
CPU model runtime
    |
    v
Prediction endpoint
```

KServe solves the serving problem while the AI Platform keeps ownership of the platform-facing contract.

The user should eventually interact with:

```text
REST API
```

not directly with KServe.

---

# 3. Responsibility Boundaries

## AI Platform REST API

Owns higher-level deployment intent.

Future responsibilities:

```text
resolve approved model/version
create ModelService
read ModelService status
update ModelService
delete ModelService
```

## ModelService

Remains the platform-facing Kubernetes abstraction.

```text
platform.anselem.dev/v1alpha1
Kind: ModelService
```

## AI Platform Operator

Owns Kubernetes reconciliation.

Target:

```text
ModelService
   |
   v
InferenceService
```

## KServe

Owns model-serving reconciliation.

## Kubernetes

Runs the actual serving workload.

---

# 4. Small Architecture

![img](/img/ai-platform-model-serving-architecture.png)

```text
                 AI PLATFORM CONTROL PLANE

 User / CLI
     |
     v
 AI Platform API
     |
     v
 ModelService CR
     |
     v
 Go Operator
     |
     v
 KServe InferenceService
     |
     +--------------------------+
     |                          |
     v                          v
 CPU Serving Runtime      Model Artifact Storage
                           S3-compatible later
     |
     v
 Kubernetes Service
     |
     v
 Existing Envoy Gateway
 gateway-system/shared-gateway
     |
     v
 HTTPS prediction endpoint
```

Existing delivery/security controls stay in place:

```text
Source
  |
  v
CI / Security
  |
  v
GHCR
  |
  v
GitOps
  |
  v
Argo CD
  |
  v
Admission
  |
  v
Sigstore
  |
  v
Runtime
```

---

# 5. Selected KServe Version

Pinned:

```text
KServe v0.19.0
```

Do not use a floating version such as:

```text
latest
HEAD
master
```

The GitOps Applications explicitly use:

```yaml
targetRevision: v0.19.0
```

---

# 6. Selected Mode

Selected:

```text
Standard mode
```

Deferred:

```text
Knative mode
```

Standard mode uses normal Kubernetes primitives such as:

```text
Deployment
Service
Gateway API / Ingress
HorizontalPodAutoscaler
```

This is a better fit for the current platform because Envoy Gateway, Gateway API, cert-manager, Prometheus, Argo CD, and admission controls already exist.

---

# 7. Why CPU First

Phase 8 first proves:

```text
model deployment
artifact loading
prediction
status
routing
monitoring
rollback
```

GPU-specific infrastructure is future scope.

Not required now:

```text
NVIDIA GPU Operator
CUDA
GPU node pools
GPU scheduling
GPU autoscaling
```

---

# 8. Gateway Decision

KServe is configured to use Gateway API.

Existing Gateway:

```text
Namespace: gateway-system
Name: shared-gateway
GatewayClass: envoy
Address: 172.19.255.200
Programmed: True
```

The target is to reuse this Gateway rather than create another external ingress architecture.

---

# 9. GitOps Installation Model

KServe is installed through the existing App-of-Apps model.

```text
clusters/dev/root-application.yaml
        |
        v
ai-platform-root
        |
        v
clusters/dev/apps/
        |
        +--> kserve-crd
        |
        +--> kserve
```

The root Application remains manual.

The child Applications use automated reconciliation.

---

# 10. Why Installation Was Split

KServe was installed in two stages:

```text
Stage 1:
KServe CRDs

Stage 2:
KServe controller/resources
```

Reason:

```text
CRDs must be established before KServe custom resources are created.
```

This also gives a clean rollback and troubleshooting boundary.

---

# 11. Environment

GitOps repository:

```text
/mnt/data/ai-platform-gitops
```

Cluster context:

```text
kind-ai-platform-policy
```

Observed Kubernetes:

```text
Client: v1.36.2
Server: v1.36.1
```

KServe namespace:

```text
kserve
```

Argo project:

```text
ai-platform
```

---

# 12. Validate Prerequisites

Run from the GitOps repo:

```bash
cd /mnt/data/ai-platform-gitops

echo "===== CONTEXT ====="
kubectl config current-context

echo
echo "===== KUBERNETES ====="
kubectl version

echo
echo "===== GATEWAY CLASSES ====="
kubectl get gatewayclass

echo
echo "===== GATEWAYS ====="
kubectl get gateway -A

echo
echo "===== GATEWAY / ENVOY PODS ====="
kubectl get pods -A | grep -Ei 'envoy|gateway' || true

echo
echo "===== CERT-MANAGER CRDS ====="
kubectl get crd   certificates.cert-manager.io   issuers.cert-manager.io   clusterissuers.cert-manager.io   2>&1

echo
echo "===== CERT-MANAGER PODS ====="
kubectl get pods -A | grep -i cert-manager || true

echo
echo "===== GATEWAY API CRDS ====="
kubectl get crd | grep gateway.networking.k8s.io || true

echo
echo "===== HELM RELEASES ====="
helm list -A

echo
echo "===== ARGO APPLICATIONS ====="
argocd app list

echo
echo "===== ALL PODS ====="
kubectl get pods -A
```

---

# 13. Expected Prerequisite State

Expected:

```text
context:
kind-ai-platform-policy

Kubernetes server:
v1.36.1

GatewayClass:
envoy
Accepted=True

Gateway:
gateway-system/shared-gateway
172.19.255.200
Programmed=True

cert-manager:
Running

cert-manager version:
v1.21.0
```

Gateway API CRDs must be present.

---

# 14. Why cert-manager Is Needed

KServe installs admission webhooks.

Those webhooks require TLS.

The KServe resources chart creates:

```text
Issuer
Certificate
```

in namespace:

```text
kserve
```

cert-manager issues the serving certificate and creates the webhook certificate Secret.

---

# 15. Inspect Existing GitOps State

Before editing anything:

```bash
cd /mnt/data/ai-platform-gitops

sed -n '1,360p'   argocd/projects/ai-platform.yaml

cat   clusters/dev/apps/kustomization.yaml

for f in clusters/dev/apps/*.yaml; do
  echo
  echo "===== ${f} ====="
  sed -n '1,260p' "${f}"
done

find platform/namespaces   -maxdepth 3   -type f   -print   -exec sh -c 'echo "---"; sed -n "1,220p" "$1"' _ {} \;

git status --short
```

This prevents guessing AppProject permissions or repository conventions.

---

# 16. Render KServe Before Installing

Create a temporary inspection directory:

```bash
mkdir -p /tmp/kserve-v0.19.0
```

Render CRDs:

```bash
helm template kserve-crd   oci://ghcr.io/kserve/charts/kserve-crd   --version v0.19.0   --namespace kserve   > /tmp/kserve-v0.19.0/kserve-crd.yaml
```

Render resources:

```bash
helm template kserve   oci://ghcr.io/kserve/charts/kserve-resources   --version v0.19.0   --namespace kserve   --set kserve.controller.deploymentMode=Standard   --set kserve.controller.gateway.ingressGateway.enableGatewayApi=true   --set kserve.controller.gateway.ingressGateway.kserveGateway=gateway-system/shared-gateway   > /tmp/kserve-v0.19.0/kserve-resources.yaml
```

---

# 17. Inspect Rendered Resource Types

```bash
grep '^kind:'   /tmp/kserve-v0.19.0/kserve-crd.yaml   /tmp/kserve-v0.19.0/kserve-resources.yaml   | sort -u
```

Observed:

```text
CustomResourceDefinition
Certificate
ClusterRole
ClusterRoleBinding
ClusterStorageContainer
ConfigMap
Deployment
Issuer
MutatingWebhookConfiguration
Role
RoleBinding
Secret
Service
ServiceAccount
ValidatingWebhookConfiguration
```

---

# 18. Inspect API Versions

```bash
grep '^apiVersion:'   /tmp/kserve-v0.19.0/kserve-crd.yaml   /tmp/kserve-v0.19.0/kserve-resources.yaml   | sort -u
```

Observed:

```text
apiextensions.k8s.io/v1
admissionregistration.k8s.io/v1
apps/v1
cert-manager.io/v1
rbac.authorization.k8s.io/v1
serving.kserve.io/v1alpha1
v1
```

---

# 19. Inspect Images

```bash
grep -E '^[[:space:]]*image:'   /tmp/kserve-v0.19.0/kserve-resources.yaml   | sort -u
```

Observed:

```text
kserve/kserve-controller:v0.19.0
kserve/storage-initializer:v0.19.0
quay.io/brancz/kube-rbac-proxy:v0.18.0
```

These are upstream images, which matters for existing Sigstore policy.

---

# 20. Inspect Gateway Values

```bash
grep -nEi   'gateway|httproute|enableGatewayApi|kserveGateway'   /tmp/kserve-v0.19.0/kserve-resources.yaml   | head -n 120
```

Observed effective configuration:

```text
enableGatewayApi: true
kserveIngressGateway: gateway-system/shared-gateway
```

This confirmed that the Helm values were being interpreted correctly.

---

# 21. Required AppProject Changes

File:

```text
argocd/projects/ai-platform.yaml
```

Add KServe Helm source:

```yaml
spec:
  sourceRepos:
    - https://github.com/anselem-okeke/ai-platform-gitops.git
    - ghcr.io/sigstore/helm-charts
    - ghcr.io/github/artifact-attestations-helm-charts
    - ghcr.io/kserve/charts
```

Add destination:

```yaml
    - namespace: kserve
      server: https://kubernetes.default.svc
```

Add cluster resource:

```yaml
    - group: serving.kserve.io
      kind: ClusterStorageContainer
```

Add namespaced cert-manager resources:

```yaml
    - group: cert-manager.io
      kind: Certificate

    - group: cert-manager.io
      kind: Issuer
```

Do not add wildcard permissions.

---

# 22. Validate AppProject

```bash
kubectl apply   --dry-run=server   -f argocd/projects/ai-platform.yaml
```

Expected:

```text
appproject.argoproj.io/ai-platform configured (server dry run)
```

---

# 23. Create KServe Namespace

File:

```text
platform/namespaces/base/kserve.yaml
```

Content:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: kserve
  labels:
    app.kubernetes.io/part-of: ai-platform
```

---

# 24. Why the KServe Namespace Is Not Sigstore-Labeled Yet

Do not initially add:

```yaml
policy.sigstore.dev/include: "true"
```

Reason:

```text
KServe control-plane images are upstream third-party images.
```

The existing GitHub trust policy targets the first-party AI Platform operator and API images.

Protecting the KServe control-plane namespace with that same trust policy would likely block the KServe controller.

This does **not** mean KServe model workloads are exempt from security policy.

The data-plane trust decision is handled separately.

---

# 25. Update Namespace Kustomization

File:

```text
platform/namespaces/base/kustomization.yaml
```

Content:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ai-platform.yaml
  - kserve.yaml
```

---

# 26. Stage 1 — Create KServe CRD Application

File:

```text
clusters/dev/apps/kserve-crd.yaml
```

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: kserve-crd
  namespace: argocd

  finalizers:
    - resources-finalizer.argocd.argoproj.io

spec:
  project: ai-platform

  source:
    repoURL: ghcr.io/kserve/charts
    chart: kserve-crd
    targetRevision: v0.19.0

    helm:
      releaseName: kserve-crd

  destination:
    server: https://kubernetes.default.svc
    namespace: kserve

  syncPolicy:
    automated:
      prune: true
      selfHeal: true

    syncOptions:
      - CreateNamespace=false
      - ServerSideApply=true
```

---

# 27. Why ServerSideApply Is Used

The rendered CRD chart was more than 32,000 lines.

KServe's InferenceService CRD is large.

Using:

```yaml
ServerSideApply=true
```

avoids problems with an oversized client-side `last-applied-configuration` annotation.

---

# 28. Add CRD App to App-of-Apps

During Stage 1:

```yaml
resources:
  - kserve-crd.yaml
  - operator.yaml
  - api.yaml
  - gateway.yaml
  - monitoring.yaml
  - modelservices.yaml
  - policies.yaml
  - policy-controller.yaml
  - trust-policies.yaml
  - namespaces.yaml
```

Do not add the controller Application until CRDs are proven healthy.

---

# 29. Render and Dry-Run Stage 1

```bash
kubectl kustomize   clusters/dev/apps   > /tmp/phase8-apps.yaml
```

```bash
kubectl apply   --dry-run=server   -f /tmp/phase8-apps.yaml
```

Expected:

```text
application.argoproj.io/kserve-crd created (server dry run)
```

Render namespaces:

```bash
kubectl kustomize   platform/namespaces/overlays/dev   > /tmp/phase8-namespaces.yaml
```

---

# 30. Stage Only KServe Files

If unrelated untracked files exist, do not use:

```bash
git add .
```

Use:

```bash
git add   argocd/projects/ai-platform.yaml   platform/namespaces/base/kserve.yaml   platform/namespaces/base/kustomization.yaml   clusters/dev/apps/kserve-crd.yaml   clusters/dev/apps/kustomization.yaml
```

Validate:

```bash
git diff --cached
git diff --check
```

---

# 31. Stage 1 Branch and Commit

```bash
git switch -c feat/kserve-crds
```

```bash
git commit   -m "feat(kserve): add CRD bootstrap"
```

```bash
git push   -u origin   feat/kserve-crds
```

Open a PR and wait for GitOps validation before merge.

---



# 31A. Complete Stage 1 Git / PR Workflow

After the Stage 1 files are validated and staged, use this full Git workflow.

Confirm the current branch:

```bash
git branch --show-current
```

Expected:

```text
feat/kserve-crds
```

Commit:

```bash
git commit \
  -m "feat(kserve): add CRD bootstrap"
```

Push:

```bash
git push \
  -u origin \
  feat/kserve-crds
```

Create the GitHub Pull Request:

```bash
gh pr create \
  --repo anselem-okeke/ai-platform-gitops \
  --base main \
  --head feat/kserve-crds \
  --title "feat(kserve): add CRD bootstrap" \
  --body "Adds the Phase 8 KServe v0.19.0 CRD bootstrap through GitOps.

Changes:
- allow the official KServe OCI Helm repository
- allow the kserve destination namespace
- allow required KServe/cert-manager resource types
- add the kserve namespace
- add the kserve-crd Argo CD Application
- pin KServe CRDs to v0.19.0
- enable server-side apply for the large CRDs

This stage intentionally installs only the KServe CRDs. The KServe controller/resources Application will be added separately after CRD health is validated."
```

List the PR to get its number:

```bash
gh pr list \
  --repo anselem-okeke/ai-platform-gitops \
  --head feat/kserve-crds
```

Watch required checks:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops \
  --watch
```

Expected outcome:

```text
Validate GitOps Manifests
PASS
```

Review the exact PR diff before merge:

```bash
gh pr diff <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

The Stage 1 PR should contain only:

```text
argocd/projects/ai-platform.yaml
clusters/dev/apps/kserve-crd.yaml
clusters/dev/apps/kustomization.yaml
platform/namespaces/base/kserve.yaml
platform/namespaces/base/kustomization.yaml
```

Merge only after checks pass:

```bash
gh pr merge <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops \
  --merge
```

Update local `main`:

```bash
git switch main

git pull --ff-only origin main
```

Verify the merge landed:

```bash
git log -1 --oneline
```

Then continue with the manual AppProject apply and root sync described below.

---

# 42A. Complete Stage 2 Git / PR Workflow

After creating and validating:

```text
clusters/dev/apps/kserve.yaml
clusters/dev/apps/kustomization.yaml
```

confirm the working branch:

```bash
git branch --show-current
```

Expected:

```text
feat/kserve-controller
```

Run whitespace validation:

```bash
git diff --check
```

Stage only the two Stage 2 files:

```bash
git add \
  clusters/dev/apps/kserve.yaml \
  clusters/dev/apps/kustomization.yaml
```

Review:

```bash
git diff --cached
```

Commit:

```bash
git commit \
  -m "feat(kserve): install controller in standard mode"
```

Push:

```bash
git push \
  -u origin \
  feat/kserve-controller
```

Create the Stage 2 GitHub Pull Request:

```bash
gh pr create \
  --repo anselem-okeke/ai-platform-gitops \
  --base main \
  --head feat/kserve-controller \
  --title "feat(kserve): install controller in standard mode" \
  --body "Installs KServe v0.19.0 resources through Argo CD.

Configuration:
- KServe resources chart v0.19.0
- Standard deployment mode
- Gateway API enabled
- existing gateway-system/shared-gateway selected
- automated child Application reconciliation
- no namespace creation from the Helm Application

KServe CRDs were installed and validated separately before this stage."
```

List the PR:

```bash
gh pr list \
  --repo anselem-okeke/ai-platform-gitops \
  --head feat/kserve-controller
```

Watch checks:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops \
  --watch
```

Expected:

```text
Validate GitOps Manifests
PASS
```

Review the exact PR diff:

```bash
gh pr diff <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

The Stage 2 PR should contain only:

```text
clusters/dev/apps/kserve.yaml
clusters/dev/apps/kustomization.yaml
```

Merge:

```bash
gh pr merge <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops \
  --merge
```

Update local `main`:

```bash
git switch main

git pull --ff-only origin main
```

Verify:

```bash
git log -1 --oneline
```

Then refresh the root Application:

```bash
argocd app get \
  ai-platform-root \
  --refresh
```

Inspect the root diff:

```bash
argocd app diff \
  ai-platform-root
```

Expected new child:

```text
Application/kserve
```

Sync the manual root:

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

Then validate the `kserve` Application and controller health.

---

# 32. Apply Bootstrap AppProject After Merge

Because the AppProject is bootstrap-managed:

```bash
git switch main
git pull --ff-only origin main
```

Then:

```bash
kubectl apply   --dry-run=server   -f argocd/projects/ai-platform.yaml
```

Then:

```bash
kubectl apply   -f argocd/projects/ai-platform.yaml
```

This must occur before the new child Application needs the new repository/destination permissions.

---

# 33. Wait for KServe Namespace

```bash
argocd app get   ai-platform-namespaces   --refresh
```

```bash
argocd app wait   ai-platform-namespaces   --sync   --health   --timeout 300
```

```bash
kubectl get ns   kserve   --show-labels
```

Expected:

```text
kserve Active
app.kubernetes.io/part-of=ai-platform
```

---

# 34. Sync Manual Root

```bash
argocd app get   ai-platform-root   --refresh
```

```bash
argocd app diff   ai-platform-root
```

Review the new:

```text
Application/kserve-crd
```

Then:

```bash
argocd app sync   ai-platform-root
```

---

# 35. Validate KServe CRD App

```bash
argocd app get   kserve-crd   --refresh
```

Observed:

```text
Synced to v0.19.0
Healthy
```

---

# 36. Validate Installed CRDs

```bash
kubectl get crd   -o custom-columns='NAME:.metadata.name'   | grep 'kserve.io'   | sort
```

Observed:

```text
clusterservingruntimes.serving.kserve.io
clusterstoragecontainers.serving.kserve.io
inferencegraphs.serving.kserve.io
inferenceservices.serving.kserve.io
servingruntimes.serving.kserve.io
trainedmodels.serving.kserve.io
```

---

# 37. Validate KServe API Resources

```bash
kubectl api-resources   | grep -i   'kserve\|InferenceService\|ServingRuntime'
```

Observed:

```text
ClusterServingRuntime
ClusterStorageContainer
InferenceGraph
InferenceService
ServingRuntime
TrainedModel
```

InferenceService API:

```text
serving.kserve.io/v1beta1
```

---

# 38. Validate CRD Conditions

```bash
for crd in   inferenceservices.serving.kserve.io   servingruntimes.serving.kserve.io   clusterservingruntimes.serving.kserve.io   clusterstoragecontainers.serving.kserve.io
do
  echo "===== ${crd} ====="

  kubectl get crd "${crd}"     -o jsonpath='{range .status.conditions[*]}{.type}{"="}{.status}{" reason="}{.reason}{"\n"}{end}'

  echo
done
```

Observed for all critical CRDs:

```text
NamesAccepted=True
Established=True
```

Stage 1 was therefore complete.

---

# 39. Stage 2 — Create KServe Controller Application

File:

```text
clusters/dev/apps/kserve.yaml
```

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: kserve
  namespace: argocd

  finalizers:
    - resources-finalizer.argocd.argoproj.io

spec:
  project: ai-platform

  source:
    repoURL: ghcr.io/kserve/charts
    chart: kserve-resources
    targetRevision: v0.19.0

    helm:
      releaseName: kserve

      valuesObject:
        kserve:
          controller:
            deploymentMode: Standard

            gateway:
              ingressGateway:
                enableGatewayApi: true
                kserveGateway: gateway-system/shared-gateway

  destination:
    server: https://kubernetes.default.svc
    namespace: kserve

  syncPolicy:
    automated:
      prune: true
      selfHeal: true

    syncOptions:
      - CreateNamespace=false
```

---

# 40. Add Stage 2 to App-of-Apps

```yaml
resources:
  - kserve-crd.yaml
  - kserve.yaml
  - operator.yaml
  - api.yaml
  - gateway.yaml
  - monitoring.yaml
  - modelservices.yaml
  - policies.yaml
  - policy-controller.yaml
  - trust-policies.yaml
  - namespaces.yaml
```

Keep `kserve-crd.yaml` before `kserve.yaml`.

---

# 41. Render and Validate Stage 2

```bash
kubectl kustomize   clusters/dev/apps   > /tmp/phase8-kserve-apps.yaml
```

```bash
kubectl apply   --dry-run=server   -f /tmp/phase8-kserve-apps.yaml
```

Expected:

```text
application.argoproj.io/kserve created (server dry run)
```

---

# 42. Stage 2 Git Workflow

```bash
git add   clusters/dev/apps/kserve.yaml   clusters/dev/apps/kustomization.yaml
```

```bash
git diff --cached
git diff --check
```

Recommended branch:

```text
feat/kserve-controller
```

Commit:

```bash
git commit   -m "feat(kserve): install controller in standard mode"
```

Push, open PR, wait for GitOps validation, review diff, then merge.

---

# 43. Sync Root for Stage 2

After merge:

```bash
git switch main
git pull --ff-only origin main
```

```bash
argocd app get   ai-platform-root   --refresh
```

```bash
argocd app diff   ai-platform-root
```

Review:

```text
Application/kserve
```

Then:

```bash
argocd app sync   ai-platform-root
```

---

# 44. Validate KServe Application

```bash
argocd app get   kserve   --refresh
```

Observed:

```text
Repo:
ghcr.io/kserve/charts

Target:
v0.19.0

Sync Status:
Synced to v0.19.0

Health Status:
Healthy
```

Result:

```text
PASS
```

---

# 45. Validate KServe Controller

```bash
kubectl get all   -n kserve
```

Observed:

```text
pod/kserve-controller-manager-...
2/2 Running
```

Deployment:

```text
kserve-controller-manager
READY 1/1
AVAILABLE 1
```

Result:

```text
PASS
```

---

# 46. Validate Services

Observed:

```text
kserve-controller-manager-metrics-service
kserve-controller-manager-service
kserve-webhook-server-service
```

The webhook Service listens on:

```text
443/TCP
```

---

# 47. Validate cert-manager Objects

```bash
kubectl get certificate,issuer   -n kserve
```

Observed:

```text
certificate/serving-cert
READY=True

issuer/selfsigned-issuer
READY=True
```

Result:

```text
PASS
```

---

# 48. Validate KServe Webhooks

```bash
kubectl get   mutatingwebhookconfiguration,validatingwebhookconfiguration   | grep -i kserve
```

Observed:

```text
Mutating:
inferenceservice.serving.kserve.io

Validating:
clusterservingruntime.serving.kserve.io
inferencegraph.serving.kserve.io
inferenceservice.serving.kserve.io
servingruntime.serving.kserve.io
trainedmodel.serving.kserve.io
```

Result:

```text
PASS
```

---

# 49. Validate ClusterStorageContainer

```bash
kubectl get   clusterstoragecontainers.serving.kserve.io
```

Observed:

```text
default
```

Result:

```text
PASS
```

---

# 50. Validate Existing Gateway

```bash
kubectl get gateway   -A
```

Observed:

```text
gateway-system/shared-gateway
envoy
172.19.255.200
Programmed=True
```

Result:

```text
PASS
```

The existing Gateway was preserved.

---

# 51. Review Events

```bash
kubectl get events   -n kserve   --sort-by=.lastTimestamp
```

A transient startup warning occurred:

```text
FailedMount:
secret "kserve-webhook-server-cert" not found
```

The subsequent sequence was:

```text
cert-manager approved request
certificate issued
Secret created
KServe controller image pulled
controller started
kube-rbac-proxy pulled
proxy started
leader election succeeded
```

Final state was healthy.

---

# 52. Why the FailedMount Was Acceptable

The warning represented an ordering race.

The certificate Secret did not exist at the exact moment the Pod first tried to mount it.

It was not an ongoing failure because final state showed:

```text
Certificate Ready=True
Issuer Ready=True
Pod 2/2 Running
Deployment Available
Argo Healthy
```

If the certificate remained unready or the Pod stayed Pending, treat it as a real fault.

---

# 53. Controller Images Observed

Events confirmed:

```text
kserve/kserve-controller:v0.19.0
quay.io/brancz/kube-rbac-proxy:v0.18.0
```

were pulled and started.

The rendered configuration also referenced:

```text
kserve/storage-initializer:v0.19.0
```

for storage initialization.

---

# 54. Argo Reconciliation Warnings

Argo reported missing `kubectl.kubernetes.io/last-applied-configuration` annotations on some RBAC objects and reconciled missing RBAC rules/subjects.

These warnings did not prevent convergence.

Final state:

```text
Synced
Healthy
```

Do not classify them as installation failure unless reconciliation remains stuck.

---

# 55. Health Acceptance Criteria

KServe installation is healthy when:

```text
kserve-crd Application = Synced / Healthy
kserve Application = Synced / Healthy

KServe CRDs = Established
InferenceService API = discoverable

controller Pod = Running / Ready
controller Deployment = Available

Issuer = Ready
Certificate = Ready

mutating webhook = present
validating webhooks = present

ClusterStorageContainer/default = present

existing shared Gateway = Programmed
```

All were satisfied.

---

# 56. Files Added or Changed

The installation uses:

```text
argocd/projects/ai-platform.yaml

platform/namespaces/base/kserve.yaml
platform/namespaces/base/kustomization.yaml

clusters/dev/apps/kserve-crd.yaml
clusters/dev/apps/kserve.yaml
clusters/dev/apps/kustomization.yaml
```

These files are sufficient to locate the current GitOps implementation.

---

# 57. Operational Quick Check

```bash
argocd app get   kserve-crd   --refresh
```

```bash
argocd app get   kserve   --refresh
```

```bash
kubectl get pods   -n kserve
```

```bash
kubectl get certificate,issuer   -n kserve
```

```bash
kubectl get gateway   -A
```

---

# 58. Deeper Health Check

```bash
kubectl logs   -n kserve   deployment/kserve-controller-manager   --tail=300
```

```bash
kubectl get events   -n kserve   --sort-by=.lastTimestamp
```

```bash
kubectl get   clusterstoragecontainers.serving.kserve.io
```

```bash
kubectl api-resources   | grep -i   'kserve\|InferenceService\|ServingRuntime'
```

---

# 59. Troubleshooting — AppProject Denial

Symptom:

```text
application/resource is not permitted in project ai-platform
```

Check:

```bash
kubectl get appproject   ai-platform   -n argocd   -o yaml
```

Verify:

```text
ghcr.io/kserve/charts
destination kserve
ClusterStorageContainer
Certificate
Issuer
```

Fix the exact missing permission.

Do not introduce wildcards.

---

# 60. Troubleshooting — Large CRD Apply Failure

Possible symptom:

```text
metadata.annotations too long
```

or client-side apply problems.

Use:

```yaml
syncOptions:
  - ServerSideApply=true
```

on the KServe CRD Application.

---

# 61. Troubleshooting — Controller Pending

Check:

```bash
kubectl get pods   -n kserve
```

```bash
kubectl describe pod   -n kserve   <POD>
```

```bash
kubectl get events   -n kserve   --sort-by=.lastTimestamp
```

If the issue references the serving certificate Secret, inspect cert-manager.

---

# 62. Troubleshooting — Certificate Not Ready

```bash
kubectl get certificate,issuer   -n kserve
```

```bash
kubectl describe certificate   serving-cert   -n kserve
```

```bash
kubectl get certificaterequest   -n kserve
```

Check cert-manager logs if necessary.

---

# 63. Troubleshooting — Webhook Failure

Check:

```bash
kubectl get svc   -n kserve
```

```bash
kubectl get endpoints   -n kserve
```

```bash
kubectl get   mutatingwebhookconfiguration,validatingwebhookconfiguration   | grep -i kserve
```

Inspect `caBundle` and webhook Service references.

---

# 64. Troubleshooting — InferenceService API Missing

```bash
kubectl get crd   inferenceservices.serving.kserve.io
```

```bash
kubectl api-resources   | grep -i InferenceService
```

```bash
argocd app get   kserve-crd   --refresh
```

The CRD layer must be healthy before model-serving resources are used.

---

# 65. Troubleshooting — Argo OutOfSync

```bash
argocd app get   kserve   --refresh
```

```bash
argocd app diff   kserve
```

Fix desired state in Git.

Do not normalize direct live-cluster editing.

---

# 66. Troubleshooting — Gateway Changed or Missing

```bash
kubectl get gateway   -A
```

Expected:

```text
gateway-system/shared-gateway
172.19.255.200
Programmed=True
```

If missing, troubleshoot the existing Gateway separately rather than creating another public Gateway as a shortcut.

---

# 67. Recovery Sequence

Assuming Argo and the cluster exist:

```text
apply AppProject
    |
    v
restore/reconcile kserve Namespace
    |
    v
sync root
    |
    v
restore kserve-crd Application
    |
    v
wait for CRDs Established
    |
    v
restore kserve Application
    |
    v
validate controller/webhooks/certificate
```

---

# 68. Recovery Commands

```bash
kubectl apply   -f argocd/projects/ai-platform.yaml
```

```bash
argocd app get   ai-platform-namespaces   --refresh
```

```bash
argocd app get   ai-platform-root   --refresh
```

```bash
argocd app sync   ai-platform-root
```

```bash
argocd app get   kserve-crd   --refresh
```

```bash
argocd app get   kserve   --refresh
```

---

# 69. Rollback Considerations

Normal rollback is Git-driven.

For the controller Application, revert the Git commit that introduced:

```text
clusters/dev/apps/kserve.yaml
```

and its Kustomization entry.

Review the root diff before syncing.

CRD rollback is more dangerous.

Before removing KServe CRDs, inspect:

```bash
kubectl get   inferenceservices.serving.kserve.io   -A
```

```bash
kubectl get   servingruntimes.serving.kserve.io   -A
```

```bash
kubectl get   clusterservingruntimes.serving.kserve.io
```

```bash
kubectl get   clusterstoragecontainers.serving.kserve.io
```

Do not delete CRDs while live custom resources depend on them.

---

# 70. Security Properties Preserved

The installation preserved:

```text
GitOps deployment
version pinning
manual root topology control
narrow AppProject permissions
existing Envoy Gateway
existing admission architecture
no plaintext secrets in Git
separate control-plane namespace
```

---

# 71. Security Work Still Pending

KServe installation alone does not complete the model-serving security story.

Still pending:

```text
serving runtime image trust
runtime digest pinning strategy
model artifact integrity
object storage credentials
model artifact provenance
InferenceService positive test
untrusted runtime negative test
fake digest / untrusted artifact test
```

Do not disable admission to make a model work.

---

# 72. Control Plane vs Data Plane

KServe control plane:

```text
Namespace:
kserve

Components:
controller
webhooks
RBAC
config
certificate
```

Model-serving data plane:

```text
expected workload namespace:
ai-platform
```

The data plane is where existing workload admission policy becomes especially important.

---

# 73. Next Concept — ServingRuntime

KServe's controller is healthy, but a framework-specific model still needs a serving runtime.

KServe uses:

```text
ServingRuntime
ClusterServingRuntime
```

for model-server definitions.

Examples may include:

```text
scikit-learn
XGBoost
PyTorch
TensorFlow
```

The next step is to inspect the official runtime resources before applying them.

---

# 74. Inspect Existing Runtimes

Run:

```bash
cd /mnt/data/ai-platform-gitops

echo "===== CLUSTER SERVING RUNTIMES ====="
kubectl get   clusterservingruntimes.serving.kserve.io

echo
echo "===== SERVING RUNTIMES ====="
kubectl get   servingruntimes.serving.kserve.io   -A

echo
echo "===== SKLEARN RUNTIME ====="
kubectl get   clusterservingruntime   kserve-sklearnserver   -o yaml   2>&1 || true
```

---

# 75. Inspect Official KServe Cluster Resources

Download for inspection only:

```bash
mkdir -p /tmp/kserve-v0.19.0

curl -fsSL   https://github.com/kserve/kserve/releases/download/v0.19.0/kserve-cluster-resources.yaml   -o /tmp/kserve-v0.19.0/kserve-cluster-resources.yaml
```

Do not blindly apply it yet.

Inspect resource kinds:

```bash
grep '^kind:'   /tmp/kserve-v0.19.0/kserve-cluster-resources.yaml   | sort -u
```

Inspect runtime names:

```bash
awk '
  /^kind: ClusterServingRuntime$/ { runtime=1; next }
  runtime && /^metadata:$/ { metadata=1; next }
  runtime && metadata && /^  name:/ {
    print $2
    runtime=0
    metadata=0
  }
' /tmp/kserve-v0.19.0/kserve-cluster-resources.yaml
```

Inspect scikit-learn:

```bash
grep -nEi   'sklearn|scikit'   /tmp/kserve-v0.19.0/kserve-cluster-resources.yaml   | head -n 120
```

Inspect images:

```bash
grep -E   '^[[:space:]]*image:'   /tmp/kserve-v0.19.0/kserve-cluster-resources.yaml   | sort -u
```

---

# 76. Why Runtime Inspection Matters

The current `ai-platform` namespace is protected by admission controls.

An upstream KServe model-server image may not automatically satisfy the existing first-party trust policy.

Therefore the runtime step must answer:

```text
Which runtime image?
Which version?
Which digest?
Who is trusted?
Should it be mirrored?
Should we build our own controlled runtime?
How does Sigstore validate it?
```

This is a security design decision, not just a deployment command.

---

# 77. Current Phase 8 Status

```text
[x] Phase 8 architecture defined

[x] KServe selected and version pinned
    KServe v0.19.0
    Standard mode
    InferenceService
    CPU first
    Gateway API

[x] KServe prerequisites validated
[x] KServe installed through GitOps
[x] KServe health validated

[ ] KServe serving runtimes installed/selected
[ ] CPU-based InferenceService deployed
[ ] Model artifact loaded
[ ] Prediction endpoint validated
[ ] Real prediction request succeeds
```

---

# 78. Installation Acceptance Summary

```text
KServe version:
v0.19.0

Mode:
Standard

Gateway API:
enabled

Gateway:
gateway-system/shared-gateway

CRDs:
Synced
Healthy
Established

Controller:
Running
Ready
Leader elected

Webhook TLS:
Certificate Ready
Issuer Ready

Admission webhooks:
Present

ClusterStorageContainer:
Present

Argo:
Synced
Healthy

Gateway:
Programmed=True
```

Result:

```text
KServe installation PASS
```

---

# 79. References

KServe Kubernetes Deployment Installation:

```text
https://kserve.github.io/website/docs/admin-guide/kubernetes-deployment
```

KServe Documentation:

```text
https://kserve.github.io/website/
```

KServe Releases:

```text
https://github.com/kserve/kserve/releases
```

KServe v0.19.0 Release:

```text
https://github.com/kserve/kserve/releases/tag/v0.19.0
```

Gateway API:

```text
https://gateway-api.sigs.k8s.io/
```

Argo CD:

```text
https://argo-cd.readthedocs.io/
```

cert-manager:

```text
https://cert-manager.io/docs/
```
