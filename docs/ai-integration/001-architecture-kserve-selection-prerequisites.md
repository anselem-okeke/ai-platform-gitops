# Architecture, KServe Selection, and Prerequisite Validation

## Purpose

This document records the **first completed implementation decisions for Phase 8 — AI Platform Integrations**.
>This is an implementation baseline, not a future-looking architecture note.

---

# 1. Objective

Extends the current Kubernetes AI Platform from:

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

toward a real model-serving platform:

```text
Model producer
    |
    v
MLflow Registry
    |
    v
S3-compatible object storage
    |
    v
AI Platform REST API
    |
    v
ModelService CR
    |
    v
AI Platform Operator
    |
    v
KServe InferenceService
    |
    v
CPU model runtime
    |
    v
Prediction endpoint
```

The platform will continue to reuse the existing Phase 7 controls around this flow:

```text
Source Git
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
Native Admission
    |
    v
Sigstore
    |
    v
KServe Runtime
```

---

# 2. Architecture

![img](/img/model-serving.png)

```text
Developer / Platform User
        |
        v
AI Platform REST API
        |
        v
ModelService CR
platform.anselem.dev/v1alpha1
        |
        v
AI Platform Operator
        |
        v
KServe InferenceService
        |
        +-----------------------------+
        |                             |
        v                             v
Serving Runtime                 S3-compatible Storage
CPU model server                initially MinIO candidate
        |                             ^
        |                             |
        +------ loads artifact -------+
        |
        v
Kubernetes Service
        |
        v
Envoy Gateway
        |
        v
HTTPS Prediction Endpoint
```

The existing platform responsibilities remain separated.

---

# 3. Responsibility Split

## AI Platform REST API

The REST API owns higher-level deployment intent.

Future responsibilities include:

```text
receive deployment request
resolve approved model/version
create/update ModelService
read ModelService status
delete ModelService
```

The API should not directly create KServe resources.

---

# 4. ModelService Custom Resource

The platform keeps:

```text
platform.anselem.dev/v1alpha1
Kind: ModelService
```

as the platform-facing desired-state API.

The ModelService remains the abstraction presented by the AI Platform.

KServe is an implementation detail behind the platform API.

---

# 5. AI Platform Operator

The Go operator owns Kubernetes reconciliation.

Target flow:

```text
ModelService
    |
    v
Operator watches
    |
    v
Operator creates/updates
KServe InferenceService
    |
    v
Operator observes serving state
    |
    v
ModelService.status updated
```

The operator should remain focused on Kubernetes reconciliation.

It should not become a large MLflow/business-policy integration service.

---

# 6. KServe Role

KServe becomes the model-serving abstraction.

The operator will eventually reconcile:

```text
ModelService
    |
    v
InferenceService
```

KServe then manages the serving workload.

This avoids implementing a complete model-serving control plane from scratch.

---

# 7. Selected KServe Version

Selected version:

```text
KServe v0.19.0
```

This version is pinned for the beginning of Phase 8.

The installation should not use:

```text
latest
HEAD
floating Helm chart version
```

---

# 8. Selected KServe Deployment Mode

Selected mode:

```text
Standard mode
```

Not selected for the first Phase 8 implementation:

```text
Knative/serverless mode
```

The platform will start with standard Kubernetes-style model serving.

---

# 9. Why Standard Mode Was Selected

Standard mode fits the existing platform because the cluster already has:

```text
Envoy Gateway
Gateway API
Prometheus
Argo CD
native admission controls
Sigstore admission
GitOps
```

The first Phase 8 goal is to prove:

```text
deploy
load model
predict
observe
rollback
```

without introducing another serving/networking control plane.

---

# 10. Why Knative Is Deferred

Knative would add additional concepts such as:

```text
serverless revisions
scale-to-zero behavior
Knative networking
additional operational dependencies
```

Those are not required to prove the core AI Platform integration.

Therefore:

```text
Knative = deferred
```

not rejected permanently.

---

# 11. Selected Serving API

Selected API:

```text
InferenceService
```

This becomes the Kubernetes resource reconciled by the AI Platform operator.

The intended future flow is:

```text
ModelService
    |
    v
InferenceService
```

---

# 12. CPU-First Decision

Phase 8 is explicitly:

```text
CPU first
```

The initial model-serving validation does not require GPU hardware.

The first real model should prove:

```text
artifact loading
runtime startup
prediction request
real prediction response
status propagation
monitoring
rollback
```

---

# 13. GPU Position

GPU support remains a future capability.

Phase 8 completion does not depend on:

```text
NVIDIA GPU operator
CUDA runtime
GPU scheduling
GPU node pools
accelerator autoscaling
```

The architecture should remain extensible to those later.

---

# 14. Gateway API Decision

Selected networking direction:

```text
Gateway API
```

The cluster already has an existing Envoy Gateway.

The intended public-serving path is eventually:

```text
Client
   |
   v
Existing Envoy Gateway
   |
   v
HTTPRoute
   |
   v
KServe predictor Service
```

---

# 15. Existing Gateway State

Validated GatewayClass:

```text
NAME: envoy
CONTROLLER: gateway.envoyproxy.io/gatewayclass-controller
ACCEPTED: True
```

Validated Gateway:

```text
namespace:
gateway-system

name:
shared-gateway

class:
envoy

address:
172.19.255.200

programmed:
True
```

This existing Gateway should be preserved rather than creating an unrelated external ingress stack.

---

# 16. Networking Ownership Decision

The preferred responsibility split is:

```text
KServe
    -> model serving workload

AI Platform / GitOps
    -> external routing
    -> Gateway integration
    -> TLS
```

This keeps KServe from becoming the owner of the entire public platform networking model.

---

# 17. First KServe Networking Milestone

The first KServe installation milestone is intentionally narrower:

```text
KServe controller installed
        |
        v
CRDs established
        |
        v
webhook healthy
        |
        v
InferenceService API available
```

Public Gateway routing will be integrated after KServe itself is proven healthy.

---

# 18. KServe Helm Charts

The selected KServe installation uses the official OCI Helm charts:

```text
oci://ghcr.io/kserve/charts/kserve-crd
oci://ghcr.io/kserve/charts/kserve-resources
```

Both are pinned to:

```text
v0.19.0
```

The eventual GitOps implementation should preserve that version pin.

---

# 19. KServe Mode Configuration

The selected configuration must explicitly set Standard mode.

Representative value:

```yaml
kserve:
  controller:
    deploymentMode: Standard
```

The exact committed Argo/Helm values must be verified from the GitOps repository after implementation.

---

# 20. Prerequisite Validation Summary

The cluster was inspected before any KServe installation.

Validated:

```text
Kubernetes compatibility
Gateway API availability
Envoy Gateway health
cert-manager availability
cert-manager version
Gateway API CRDs
existing GitOps/Argo health
current cluster workload health
```

No KServe installation was started before this validation.

---

# 21. Kubernetes Version Validation

Command:

```bash
kubectl config current-context
kubectl version
```

Observed context:

```text
kind-ai-platform-policy
```

Observed client:

```text
v1.36.2
```

Observed server:

```text
v1.36.1
```

The server version is the important compatibility target for KServe.

Result:

```text
PASS
```

---

# 22. GatewayClass Validation

Command:

```bash
kubectl get gatewayclass
```

Observed:

```text
NAME    CONTROLLER                                      ACCEPTED
envoy   gateway.envoyproxy.io/gatewayclass-controller   True
```

Result:

```text
PASS
```

---

# 23. Gateway Validation

Command:

```bash
kubectl get gateway -A
```

Observed:

```text
NAMESPACE        NAME             CLASS   ADDRESS          PROGRAMMED
gateway-system   shared-gateway   envoy   172.19.255.200   True
```

Result:

```text
PASS
```

---

# 24. Envoy Gateway Pod Validation

Command:

```bash
kubectl get pods -A \
  | grep -Ei 'envoy|gateway'
```

Observed:

```text
envoy-gateway-system/envoy-gateway
Running

envoy-gateway-system/shared-gateway data-plane Pod
Running
```

Result:

```text
PASS
```

---

# 25. cert-manager CRD Validation

Command:

```bash
kubectl get crd \
  certificates.cert-manager.io \
  issuers.cert-manager.io \
  clusterissuers.cert-manager.io
```

Observed:

```text
certificates.cert-manager.io
issuers.cert-manager.io
clusterissuers.cert-manager.io
```

Result:

```text
PASS
```

---

# 26. cert-manager Pod Validation

Command:

```bash
kubectl get pods -A \
  | grep -i cert-manager
```

Observed:

```text
cert-manager
Running

cert-manager-cainjector
Running

cert-manager-webhook
Running
```

Result:

```text
PASS
```

---

# 27. cert-manager Version Validation

Command:

```bash
helm list -A
```

Observed Helm release:

```text
name:
cert-manager

namespace:
cert-manager

chart:
cert-manager-v1.21.0

app version:
v1.21.0

status:
deployed
```

Selected KServe prerequisites require a sufficiently recent cert-manager.

Current version:

```text
v1.21.0
```

Result:

```text
PASS
```

---

# 28. Gateway API CRD Validation

Command:

```bash
kubectl get crd \
  | grep gateway.networking.k8s.io
```

Observed CRDs include:

```text
backendtlspolicies.gateway.networking.k8s.io
gatewayclasses.gateway.networking.k8s.io
gateways.gateway.networking.k8s.io
grpcroutes.gateway.networking.k8s.io
httproutes.gateway.networking.k8s.io
listenersets.gateway.networking.k8s.io
referencegrants.gateway.networking.k8s.io
tcproutes.gateway.networking.k8s.io
tlsroutes.gateway.networking.k8s.io
udproutes.gateway.networking.k8s.io
```

Result:

```text
PASS
```

---

# 29. Existing Helm Stack Validation

Observed Helm releases include:

```text
cert-manager
Envoy Gateway
kube-prometheus-stack
MetalLB
Policy Controller
trust-policies
```

Relevant versions observed:

```text
cert-manager:
v1.21.0

Envoy Gateway:
v1.8.3

kube-prometheus-stack:
88.2.0

MetalLB:
0.16.1

Policy Controller:
0.10.6

trust-policies:
v0.7.0
```

This confirms the cluster already contains the networking, certificate, monitoring, and admission foundations required for the next step.

---

# 30. Argo CD Health Validation

Command:

```bash
argocd app list
```

Observed applications include:

```text
ai-platform-api
ai-platform-gateway
ai-platform-modelservices
ai-platform-monitoring
ai-platform-namespaces
ai-platform-operator
ai-platform-policies
ai-platform-root
policy-controller
trust-policies
```

Observed state:

```text
Synced
Healthy
```

for the existing child Applications.

The root Application remains:

```text
Manual
```

by design.

Result:

```text
PASS
```

---

# 31. Current Platform Pod Health Validation

Command:

```bash
kubectl get pods -A
```

Relevant observed healthy components include:

```text
AI Platform operator
AI Platform API
existing fraud-model workload
Argo CD
Calico
cert-manager
Policy Controller
Envoy Gateway
Keycloak
CoreDNS
metrics-server
MetalLB
Prometheus
Grafana
Alertmanager
```

Result:

```text
PASS
```

---

# 32. Existing Admission Stack

The cluster already has:

```text
native admission policy
Sigstore Policy Controller
GitHub attestation trust
protected namespaces
```

This matters because future KServe workloads must pass the same supply-chain controls.

KServe will not receive a security bypass simply because it is a model-serving framework.

---

# 33. Existing Policy Controller State

Observed Helm state:

```text
chart:
policy-controller-0.10.6

app:
0.13.1

namespace:
cosign-system

status:
deployed
```

This remains part of the Phase 8 runtime security boundary.

---

# 34. Existing Trust Policy State

Observed:

```text
trust-policies-v0.7.0
```

The trust policy currently protects first-party image repositories.

Future KServe runtime images must be evaluated against the current policy model.

---

# 35. Existing Monitoring Foundation

Observed:

```text
kube-prometheus-stack
Prometheus
Grafana
Alertmanager
kube-state-metrics
node-exporter
```

This gives Phase 8 a ready monitoring foundation.

KServe/model metrics will be integrated later rather than installing a second monitoring stack.

---

# 36. Existing Storage State

The cluster currently has:

```text
local-path-provisioner
```

for Kubernetes storage.

This is not the same thing as the S3-compatible model artifact store required later in Phase 8.

The object-storage decision remains:

```text
pending implementation
```

---

# 37. S3-Compatible Object Storage Direction

The Phase 8 architecture requires:

```text
S3-compatible object storage
```

for model artifacts.

Likely development option:

```text
MinIO
```

but the exact version is not yet pinned in this document.

Therefore the checklist remains:

```text
[ ] S3-compatible object storage selected and version pinned
```

---

# 38. MLflow Direction

MLflow will later provide:

```text
experiment tracking
model metadata
model versioning
Model Registry
artifact URI
promotion/rollback metadata
```

The actual model artifact bytes should live in S3-compatible object storage.

MLflow version is not yet pinned here.

---

# 39. Future MLflow/Object Storage Split

Target:

```text
MLflow
   |
   +--> experiment metadata
   +--> model metadata
   +--> model version
   +--> artifact URI
            |
            v
        MinIO / S3
            |
            v
      model artifact bytes
```

This prevents the architecture from treating the metadata registry as the artifact-storage layer itself.

---

# 40. Future Model Deployment Flow

Target:

```text
Registered model
      |
      v
AI Platform API resolves approved version
      |
      v
ModelService
      |
      v
Operator
      |
      v
InferenceService
      |
      v
KServe loads artifact from S3
      |
      v
Prediction endpoint
```

---

# 41. Future Model Status Flow

Target:

```text
InferenceService status
      |
      v
Operator observes
      |
      v
ModelService.status
      |
      v
REST API status endpoint
```

The platform user should not need direct KServe knowledge for normal operation.

---

# 42. Future Model Deletion Flow

Target:

```text
REST API DELETE
      |
      v
ModelService removed
      |
      v
Operator reconciliation
      |
      v
InferenceService removed
```

Deletion must still preserve Git/runtime policy boundaries where applicable.

---

# 43. Future Routing Flow

After internal serving is validated:

```text
Prediction client
      |
      v
HTTPS
      |
      v
shared Envoy Gateway
      |
      v
HTTPRoute
      |
      v
KServe predictor Service
      |
      v
Model runtime
```

The first KServe milestone intentionally does not start here.

---

# 44. Why Public Routing Is Deferred Until After Health

If installation, model loading, and public routing are introduced simultaneously, a failed prediction could come from:

```text
KServe controller
InferenceService spec
model artifact
storage credentials
runtime image
Service
Gateway
HTTPRoute
TLS
DNS
```

By validating KServe internally first, the failure domain remains much smaller.

---

# 45. Phase 8 Implementation Order

The selected execution order is:

```text
1. Architecture
2. KServe prerequisite validation
3. KServe GitOps installation
4. KServe health validation
5. Initial CPU InferenceService
6. Internal prediction validation
7. S3-compatible object storage
8. Model artifact upload/download
9. KServe artifact load from object storage
10. ModelService -> KServe
11. REST API -> ModelService -> KServe
12. Gateway/TLS integration
13. MLflow
14. MLflow -> object storage
15. Registered model deployment
16. model promotion/rollback
17. metrics/Grafana/alerts
18. admission/supply-chain validation
19. full E2E
20. recovery/operations documentation
```

---

# 46. What Is Complete Now

The following are complete:

```text
[x] Phase 8 architecture defined

[x] KServe selected and version pinned
    KServe v0.19.0
    Standard mode
    InferenceService
    CPU first
    Gateway API

[x] KServe prerequisites validated
```

---

# 47. What Is Not Yet Complete

Still pending:

```text
[ ] KServe installed through GitOps
[ ] KServe health validated

[ ] object storage selected/version pinned
[ ] object storage installed
[ ] bucket created
[ ] artifact upload/download
[ ] KServe object-storage access

[ ] CPU InferenceService
[ ] prediction request
[ ] ModelService -> KServe
[ ] REST API integration
[ ] Gateway routing
[ ] MLflow
[ ] model metrics
[ ] full Phase 8 E2E
```

---

# 48. Next Implementation Step

Before creating KServe Argo Applications, inspect the existing GitOps topology and AppProject so no permissions or naming conventions are guessed.

Run from:

```text
/mnt/data/ai-platform-gitops
```

Commands:

```bash
cd /mnt/data/ai-platform-gitops

echo "===== APPPROJECT ====="
sed -n '1,360p' \
  argocd/projects/ai-platform.yaml

echo
echo "===== APPS KUSTOMIZATION ====="
cat \
  clusters/dev/apps/kustomization.yaml

echo
echo "===== CURRENT CHILD APPLICATIONS ====="
for f in clusters/dev/apps/*.yaml; do
  echo
  echo "===== ${f} ====="
  sed -n '1,260p' "${f}"
done

echo
echo "===== NAMESPACE KUSTOMIZATION ====="
find platform/namespaces \
  -maxdepth 3 \
  -type f \
  -print \
  -exec sh -c 'echo "---"; sed -n "1,220p" "$1"' _ {} \;

echo
echo "===== GIT STATUS ====="
git status --short
```

The output of this inspection will determine the exact KServe GitOps manifests.

---

# 49. Intended KServe GitOps Shape

Likely future structure:

```text
clusters/dev/apps/
├── ...
├── kserve-crd.yaml
└── kserve.yaml
```

Potential namespace:

```text
kserve
```

However, this is not yet declared as exact committed state.

The repository inspection must determine:

```text
actual naming pattern
namespace management pattern
Argo sync options
AppProject permissions
OCI Helm repository declarations
```

---

# 50. Why We Do Not Install KServe Manually

Normal Phase 8 deployment must preserve the existing model:

```text
GitOps
    |
    v
Argo CD
    |
    v
Kubernetes
```

Therefore the normal installation should not be:

```bash
helm install ...
```

run manually as the final state.

A manual Helm command may be useful for reference or controlled troubleshooting, but the desired implementation belongs in GitOps.

---

# 51. Security Requirement for KServe

KServe is not exempt from the existing Phase 7 controls.

Future KServe workloads must preserve:

```text
trusted container registry
digest pinning
SBOM/provenance flow
native admission
Sigstore verification
protected namespace policy
Prometheus visibility
GitOps reconciliation
```

---

# 52. KServe Runtime Image Requirement

When KServe creates predictor workloads, their runtime images must be compatible with the existing admission rules.

This must be validated explicitly later.

The checklist therefore retains:

```text
[ ] KServe workloads pass existing admission controls
[ ] Trusted image positive test passes
[ ] Untrusted image negative test passes
[ ] Fake digest / untrusted artifact test passes
```

---

# 53. Model Artifact Trust Is Separate

Container trust and model artifact trust are different.

Current Phase 7 controls prove:

```text
container image trust
```

Phase 8 must additionally define:

```text
model artifact location
artifact checksum/integrity
registry approval
model version
artifact URI
promotion
rollback
```

This will be addressed when object storage and MLflow are implemented.

---

# 54. Recovery Consideration

KServe must eventually be recoverable from:

```text
GitOps state
object-storage artifact
model metadata
runtime secret source
```

A cluster rebuild should not depend on undocumented manual model deployment.

---

# 55. Operational Boundary

Phase 8 should preserve the same operating rules already established:

```text
no direct deployment from source CI
no mutable deployment tags
no plaintext secrets in Git
no admission bypass
no undocumented manual drift
rollback through controlled desired state
```

---

# 56. Current Phase 8 Status

```text
Phase 8 — AI Platform Integrations

[x] Phase 8 architecture defined

[x] KServe selected and version pinned
    KServe v0.19.0
    Standard mode
    InferenceService
    CPU first
    Gateway API

[x] KServe prerequisites validated

[ ] KServe installed through GitOps
[ ] KServe health validated
```

This is the current handoff point.

---

# 57. References

KServe documentation:

```text
https://kserve.github.io/website/
```

KServe Kubernetes deployment / Standard mode:

```text
https://kserve.github.io/website/docs/admin-guide/kubernetes-deployment
```

KServe dependencies:

```text
https://kserve.github.io/website/docs/install/dependencies
```

Kubernetes Gateway API:

```text
https://gateway-api.sigs.k8s.io/
```

cert-manager:

```text
https://cert-manager.io/docs/
```
