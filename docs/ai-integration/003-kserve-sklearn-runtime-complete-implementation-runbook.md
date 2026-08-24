# Phase 8.003 — Trusted KServe sklearn Runtime: Complete Implementation Runbook

> **Scope:** This runbook documents the complete implementation path followed to build, harden, release, verify, trust, and GitOps-deploy the `kserve-sklearnserver` runtime for the AI Platform.
>
> It starts with the upstream KServe v0.19.0 runtime decision and ends with a live Argo CD-managed `ClusterServingRuntime` using the verified immutable GHCR digest.
>
> This is intentionally implementation-focused. It includes the architecture, exact repository paths, build logic, scripts, Dockerfile, CI workflow, vulnerability remediation, Git history, GitOps manifests, Argo bootstrap behavior, failure modes, validation commands, and recovery/rollback guidance.

---

# 1. Final Result

The completed runtime path is:

```text
KServe v0.19.0 source
commit b0eda63d2c105479140af8ec9149d992b7e44be5
        |
        v
reproducible source fetch
        |
        +--> exact tag commit verification
        +--> GitHub tag tarball
        +--> symlink dereference for /mnt/data
        |
        v
dependency policy patch
        |
        +--> production-only uv sync
        +--> targeted dependency upgrades
        +--> dev dependency removal
        |
        v
multi-stage Docker build
        |
        +--> USER 1000
        +--> KServe 0.19.0
        +--> sklearnserver
        +--> hardened Python dependency graph
        |
        v
runtime smoke
        |
        v
Trivy HIGH/CRITICAL gate
        |
        v
0 HIGH / 0 CRITICAL
        |
        v
SPDX SBOM
        |
        v
GHCR push
        |
        v
GitHub provenance + SBOM attestations
        |
        v
immutable OCI digest
sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f
        |
        v
GitHub attestation verification
        |
        v
Sigstore ClusterImagePolicy
        |
        v
GitOps ClusterServingRuntime
        |
        v
Argo CD
        |
        v
LIVE kserve-sklearnserver
```

Final immutable runtime:

```text
ghcr.io/anselem-okeke/ai-platform-sklearnserver@sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f
```

Final source correlation SHA:

```text
1659c277a6ce20e06372826810ce796368a45d17
```

Final GitOps revision that introduced the runtime:

```text
11e694d8d94bb3a7d6542b5e0c60d58fb93163f5
```

---

# 2. Repository Boundaries

Two repositories are involved.

## 2.1 Source repository

**🟦 SOURCE REPO**

```text
/mnt/data/ai-platform-operator
```

Responsibilities:

```text
KServe source acquisition
dependency remediation
runtime Docker build
runtime validation
Trivy security gate
SBOM generation
GHCR push
provenance attestation
SBOM attestation
source SHA → registry digest correlation
```

Important files:

```text
Dockerfile.sklearn-runtime
.dockerignore
.gitignore
scripts/runtime/fetch-kserve-source.sh
scripts/runtime/patch-kserve-dependencies.py
.github/workflows/release-sklearn-runtime.yml
```

Generated but untracked:

```text
.runtime-src/
```

## 2.2 GitOps repository

**🟩 GITOPS REPO**

```text
/mnt/data/ai-platform-gitops
```

Responsibilities:

```text
Argo CD AppProject permission
Sigstore trust scope
ClusterServingRuntime manifest
Kustomize layout
Argo CD child Application
root App-of-Apps registration
live reconciliation
```

Important files:

```text
argocd/projects/ai-platform.yaml
clusters/dev/apps/trust-policies.yaml
clusters/dev/apps/kserve-runtimes.yaml
clusters/dev/apps/kustomization.yaml

platform/kserve/runtimes/base/kserve-sklearnserver.yaml
platform/kserve/runtimes/base/kustomization.yaml
platform/kserve/runtimes/overlays/dev/kustomization.yaml
```

---

# 3. Runtime Architecture Decision

The selected KServe stack was:

```text
KServe version:          v0.19.0
Deployment mode:         Standard
Serving API:             InferenceService
Runtime:                 kserve-sklearnserver
CPU/GPU:                 CPU first
Ingress model:           Gateway API
Knative:                 not used
```

The upstream `ClusterServingRuntime` selected as the implementation baseline was:

```yaml
apiVersion: serving.kserve.io/v1alpha1
kind: ClusterServingRuntime
metadata:
  annotations:
    serving.kserve.io/server-type: sklearnserver
  name: kserve-sklearnserver
spec:
  annotations:
    prometheus.kserve.io/path: /metrics
    prometheus.kserve.io/port: '8080'
  containers:
  - args:
    - --model_name={{.Name}}
    - --model_dir=/mnt/models
    - --http_port=8080
    image: kserve/sklearnserver:v0.19.0
    name: kserve-container
    resources:
      limits:
        cpu: '1'
        memory: 2Gi
      requests:
        cpu: '1'
        memory: 2Gi
    securityContext:
      allowPrivilegeEscalation: false
      capabilities:
        drop:
        - ALL
      privileged: false
      runAsNonRoot: true
  protocolVersions:
  - v1
  - v2
  supportedModelFormats:
  - autoSelect: true
    name: sklearn
    priority: 1
    version: '1'
```

The design decision was to preserve this runtime contract while replacing the upstream image with a first-party, controlled, digest-pinned build.

---

# 3.1 What KServe Is

KServe is the Kubernetes model-serving layer used by this project.

A normal Kubernetes `Deployment` can run a container, but an ML-serving platform needs more than simply starting a Pod. It needs a standard way to describe:

```text
which model should run
which serving runtime should execute it
where the model artifact is stored
what resources the model needs
how the model becomes reachable
how the serving workload is reconciled
```

KServe provides those model-serving abstractions on top of Kubernetes.

In this project, KServe sits **below the AI Platform Operator and above the actual serving Pods**:

```text
User / API
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
KServe controller
    |
    +--> chooses serving runtime
    +--> prepares model storage
    +--> creates serving workload
    +--> creates Kubernetes Service
    +--> manages model-serving lifecycle
    |
    v
Model-serving Pod
```

The AI Platform therefore does **not** need to implement an ML serving control plane from scratch.

The platform owns the higher-level product API and policy:

```text
model registration
approved model/version
ModelService API
platform policy
GitOps
security
routing
observability
```

KServe owns the Kubernetes-specific model-serving mechanics:

```text
InferenceService reconciliation
runtime selection
model initialization
serving workload construction
service exposure
serving status
```

This separation keeps the custom operator focused on platform behavior rather than rebuilding functionality already provided by a mature Kubernetes serving controller.

---

# 3.2 What a KServe `InferenceService` Is

`InferenceService` is the primary workload API used to request that a model be served.

Conceptually, an `InferenceService` says:

```text
Serve this model
using this model format/runtime
from this model artifact location
with these resource requirements
```

A future sklearn example in this project will conceptually resemble:

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: iris-model
  namespace: ai-platform
spec:
  predictor:
    model:
      modelFormat:
        name: sklearn
      storageUri: s3://models/iris/
```

The important point is that the `InferenceService` does not need to contain the complete implementation of sklearn serving.

Instead, KServe resolves a compatible serving runtime and creates the actual serving workload from it.

The intended project path is:

```text
ModelService
    |
    | reconciled by AI Platform Operator
    v
InferenceService
    |
    | reconciled by KServe
    v
serving Pod + Service
```

This gives the project a clean controller hierarchy:

```text
Platform intent
    |
    v
ModelService
    |
    v
AI Platform Operator
    |
    v
Serving intent
    |
    v
InferenceService
    |
    v
KServe
    |
    v
Kubernetes runtime resources
```

---

# 3.3 What a KServe Serving Runtime Is

A KServe **serving runtime** defines **how a particular class of models is actually executed**.

For this project, the runtime is:

```text
ClusterServingRuntime/kserve-sklearnserver
```

and its model type is:

```text
sklearn
```

The runtime contains the reusable execution template that tells KServe things such as:

```text
container image
container command/arguments
supported model formats
supported inference protocols
CPU/memory requirements
security context
metrics endpoint
```

Our runtime therefore answers the question:

> When an `InferenceService` requests an sklearn model, what trusted container should KServe start, and how should it start it?

The final runtime declares:

```text
model format:
sklearn

protocols:
v1
v2

container:
kserve-container

entry behavior:
--model_name={{.Name}}
--model_dir=/mnt/models
--http_port=8080
```

and, most importantly, it uses the project's verified first-party image:

```text
ghcr.io/anselem-okeke/ai-platform-sklearnserver@
sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f
```

---

# 3.4 `ServingRuntime` vs `ClusterServingRuntime`

KServe supports runtime definitions at different scopes.

Conceptually:

```text
ServingRuntime
    |
    +--> namespace-scoped
    +--> available to workloads in one namespace

ClusterServingRuntime
    |
    +--> cluster-scoped
    +--> reusable across namespaces
```

This project selected:

```text
ClusterServingRuntime
```

because the sklearn serving implementation is a **platform capability**, not an application-specific runtime.

The desired architecture is:

```text
one centrally controlled sklearn runtime
             |
             +--> model A
             +--> model B
             +--> model C
```

rather than duplicating a separate runtime definition for every model or namespace.

This also centralizes:

```text
runtime image upgrades
security policy
resource defaults
runtime arguments
supported protocol versions
supply-chain trust
```

---

# 3.5 Why the Runtime Is Separate From the Model Artifact

The runtime image and the model artifact are two different things.

The runtime image contains software such as:

```text
Python
KServe
sklearnserver
scikit-learn
FastAPI
Starlette
supporting Python libraries
```

The model artifact contains the trained model itself, for example:

```text
model.joblib
model.pkl
model metadata
```

The relationship is:

```text
Trusted sklearn runtime image
        |
        | loads
        v
Trained sklearn model artifact
        |
        v
Prediction service
```

This separation is critical for the architecture.

One trusted runtime image can serve many different sklearn models:

```text
                 +--> fraud-model-v1
                 |
sklearn runtime -+--> churn-model-v3
                 |
                 +--> iris-demo-v1
```

The runtime therefore changes less frequently than the model artifacts.

It also creates two separate supply-chain trust boundaries:

```text
Container image trust
        |
        +--> image digest
        +--> vulnerability scan
        +--> SBOM
        +--> provenance
        +--> Sigstore admission

Model artifact trust
        |
        +--> model version
        +--> artifact checksum/digest
        +--> registry approval
        +--> storage integrity
        +--> future model provenance
```

Securing the runtime does **not** automatically prove that a model artifact is trustworthy.

That second boundary is implemented in later model-storage and registry work.

---

# 3.6 Purpose of `kserve-sklearnserver` in This Project

The `kserve-sklearnserver` runtime provides the actual process that loads and serves scikit-learn models.

Its role in the complete project is:

```text
AI Platform REST API
        |
        v
ModelService
        |
        v
AI Platform Operator
        |
        v
KServe InferenceService
        |
        v
ClusterServingRuntime/kserve-sklearnserver
        |
        v
trusted sklearnserver container
        |
        +--> model artifact mounted/downloaded to /mnt/models
        |
        v
scikit-learn model loaded
        |
        v
HTTP inference server :8080
        |
        v
Kubernetes Service
        |
        v
Gateway API / Envoy
        |
        v
HTTPS prediction endpoint
```

The runtime is therefore **not the model** and it is **not the AI Platform Operator**.

It is the execution engine between KServe's declarative serving API and the trained sklearn model.

A useful responsibility split is:

| Component | Responsibility |
|---|---|
| AI Platform REST API | User-facing model/platform operations |
| `ModelService` | Platform-level desired model-serving state |
| AI Platform Operator | Converts platform intent into Kubernetes/KServe resources |
| KServe `InferenceService` | Declarative request to serve a model |
| KServe controller | Reconciles model-serving resources |
| `ClusterServingRuntime/kserve-sklearnserver` | Defines how sklearn models execute |
| sklearnserver container | Loads the sklearn artifact and handles inference requests |
| S3-compatible storage | Stores model artifact bytes |
| Envoy Gateway | Exposes the prediction endpoint |

---

# 3.7 Why We Built Our Own Trusted sklearn Runtime

KServe already provides:

```text
kserve/sklearnserver:v0.19.0
```

so the purpose of this project was **not** to rewrite sklearnserver.

The project rebuilt it because the platform security model requires the serving runtime to pass the same controlled software-supply-chain requirements as other first-party workloads.

The required path is:

```text
known upstream source
        |
        v
controlled dependency graph
        |
        v
security scan
        |
        v
SBOM
        |
        v
provenance
        |
        v
first-party GHCR image
        |
        v
immutable digest
        |
        v
admission trust
```

The upstream KServe implementation remains the functional base.

The project owns the security, reproducibility, release, and deployment envelope around it.

That is why the final runtime remains:

```text
KServe 0.19.0 sklearnserver behavior
```

while the container identity becomes:

```text
ghcr.io/anselem-okeke/ai-platform-sklearnserver@sha256:...
```

---

# 3.8 How Runtime Selection Will Work

When an `InferenceService` declares:

```yaml
modelFormat:
  name: sklearn
```

KServe can select a compatible runtime based on the runtime's:

```yaml
supportedModelFormats:
  - name: sklearn
    version: "1"
    autoSelect: true
    priority: 1
```

Our runtime advertises exactly that capability.

Conceptually:

```text
InferenceService
modelFormat=sklearn
        |
        v
KServe runtime matching
        |
        v
find runtime supporting sklearn
        |
        v
kserve-sklearnserver
        |
        v
instantiate runtime container
        |
        v
load model into /mnt/models
```

This is why `supportedModelFormats` is a key part of the `ClusterServingRuntime`, rather than just descriptive metadata.

---

# 3.9 Why This Matters to the Overall AI Platform

Without KServe, the custom platform would need to implement and maintain:

```text
model-serving Deployments
runtime-specific container templates
model download/init behavior
readiness/liveness conventions
model-serving Services
runtime selection
serving status reconciliation
protocol conventions
```

Using KServe gives the project a model-serving control plane while preserving a custom platform API above it.

The intended layering is therefore:

```text
+---------------------------------------------------+
| AI Platform product layer                         |
| REST API + ModelService + policies + workflow     |
+---------------------------------------------------+
                         |
                         v
+---------------------------------------------------+
| AI Platform Operator                              |
| converts platform intent into serving intent      |
+---------------------------------------------------+
                         |
                         v
+---------------------------------------------------+
| KServe                                             |
| InferenceService + runtime orchestration           |
+---------------------------------------------------+
                         |
                         v
+---------------------------------------------------+
| Trusted runtime                                    |
| kserve-sklearnserver                               |
+---------------------------------------------------+
                         |
                         v
+---------------------------------------------------+
| Model artifact                                     |
| S3-compatible object storage                       |
+---------------------------------------------------+
                         |
                         v
+---------------------------------------------------+
| Kubernetes networking                              |
| Service + Gateway API + Envoy                      |
+---------------------------------------------------+
```

This makes KServe a foundational internal service of the AI Platform rather than the user-facing product itself.

The user interacts with the platform API.

The platform operator interacts with KServe.

KServe interacts with Kubernetes to run the model.

---

# 4. Why the Upstream Image Was Not Used Directly

The upstream image identity inspected was:

```text
docker.io/kserve/sklearnserver:v0.19.0
```

Relevant upstream digests:

```text
index:
sha256:d8ffca6cabef0139e518d7549499d7203c8b312932979773fbbe2459dc34759b

linux/amd64:
sha256:5dccffa1665d18a50c308b4056d1012d36ab988c0bdf51867a5187623d7b688b
```

The Kind nodes were `linux/amd64`, so the AMD64 image was the correct platform target.

Initial wrapper strategy:

```dockerfile
FROM docker.io/kserve/sklearnserver@sha256:5dccffa1665d18a50c308b4056d1012d36ab988c0bdf51867a5187623d7b688b
```

This was deliberately simple: first inherit the exact immutable upstream runtime, then apply the existing supply-chain controls.

The release workflow correctly blocked.

Initial Trivy result:

```text
20 HIGH
0 CRITICAL
exit code 1
```

The important lesson was:

```text
The security pipeline was working.
The upstream runtime dependency graph was not acceptable.
```

We did **not** weaken the Trivy gate.

---

# 5. Original Vulnerability Set

The investigation identified these vulnerable packages and remediation targets:

| Package | Original | Hardened target / result |
|---|---:|---:|
| PyJWT | 2.12.1 | 2.13.0 |
| aiohttp | 3.13.5 | 3.14.3 |
| black | 24.3.0 | removed from production |
| cryptography | 47.0.0 | 50.0.0 |
| dulwich | 1.2.0 | 1.2.12 resolved |
| jaraco.context | 5.3.0 | removed with global tooling |
| pyasn1 | 0.6.3 | 0.6.4 |
| python-multipart | 0.0.27 | 0.0.32 resolved |
| starlette | 0.49.1 | 1.6.0 resolved |
| urllib3 | 2.6.3 | 2.7.0 |
| wheel | 0.45.1 | removed from final global tooling |

The original image contained vulnerable dependencies inside:

```text
/prod_venv/lib/python3.11/site-packages
```

and scanner-visible packaging/tooling metadata inside:

```text
/usr/local/lib/python3.11/site-packages
```

This distinction became important later.

---

# 6. Upstream Runtime Investigation

The upstream runtime environment was inspected before changing anything.

## 6.1 Active Python

The runtime uses:

```text
/prod_venv/bin/python
```

The Python path included:

```text
/sklearnserver
/usr/local/lib/python311.zip
/usr/local/lib/python3.11
/usr/local/lib/python3.11/lib-dynload
/prod_venv/lib/python3.11/site-packages
```

The production dependency path was therefore `/prod_venv`.

## 6.2 KServe source locations

The upstream image/build architecture uses local source trees:

```text
/kserve
/sklearnserver
/storage
/third_party
```

and builds a shared virtual environment:

```text
/prod_venv
```

## 6.3 Exact upstream source commit

KServe tag:

```text
v0.19.0
```

Resolved tag commit:

```text
b0eda63d2c105479140af8ec9149d992b7e44be5
```

This commit became the immutable source anchor for the rebuild.

## 6.4 Upstream build architecture

The KServe `python/sklearn.Dockerfile` pattern was effectively:

```text
Python builder
   |
   +--> install uv
   +--> create /prod_venv
   +--> sync KServe Python package
   +--> sync storage package
   +--> sync sklearnserver package
   |
   v
final image
   |
   +--> copy /prod_venv
   +--> copy /kserve
   +--> copy /storage
   +--> copy /sklearnserver
   +--> USER 1000
   +--> PYTHONPATH=/sklearnserver
   +--> ENTRYPOINT python -m sklearnserver
```

This architecture was preserved.

---

# 7. Why Black Was in the Production Image

One unexpected finding was:

```text
black==24.3.0
```

The runtime did not need Black to serve models.

The reason was KServe's uv project configuration.

The sklearnserver lock contained:

```toml
[package.dev-dependencies]
dev = [black[colorama]]
test = [mypy, pytest, pytest-asyncio, pytest-cov]
```

Plain:

```bash
uv sync
```

includes the default development group.

Therefore the production build had accidentally carried development tooling.

The fix was:

```bash
uv sync --active --no-dev
```

This removed Black from the production runtime.

Validation later confirmed:

```text
PASS: black is not installed
```

---

# 8. Dependency-Graph Strategy

A full global dependency upgrade was rejected because it could introduce uncontrolled KServe behavior changes.

The strategy became:

```text
keep KServe 0.19.0 source
        |
        v
patch known vulnerable dependency constraints
        |
        v
targeted uv lock upgrades
        |
        v
production-only sync
```

The KServe dependency policy was hardened with these replacements:

```text
"fastapi>=0.115.3"          → "fastapi==0.136.1"
"starlette==0.49.1"         → "starlette>=1.3.1"
"urllib3>=2.6.0"            → "urllib3>=2.7.0"
"aiohttp>=3.13.3"           → "aiohttp>=3.14.3"
"cryptography>=46.0.5"      → "cryptography>=50.0.0"
"python-multipart>=0.0.22"  → "python-multipart>=0.0.30"
"pyjwt>=2.12.0"             → "pyjwt>=2.13.0"
"pyasn1>=0.6.3"             → "pyasn1>=0.6.4"
```

Storage policy:

```text
"aiohttp<4.0.0,>=3.10.0"  → "aiohttp<4.0.0,>=3.14.3"
"dulwich>=0.21.0"          → "dulwich>=1.2.5"
"cryptography>=46.0.5"     → "cryptography>=50.0.0"
"pyjwt>=2.12.0"            → "pyjwt>=2.13.0"
"pyasn1>=0.6.3"            → "pyasn1>=0.6.4"
```

The patch script was designed to fail if the expected original text was missing. That is intentional drift detection.

---

# 9. Final Generated Source Model

The repository does **not** commit the entire upstream KServe source tree.

Instead:

```text
Git repository
   |
   +--> fetch script
   +--> dependency patch script
   +--> Dockerfile
   |
   v
.runtime-src/kserve
   |
   +--> generated locally or in CI
   +--> ignored by Git
   +--> included in Docker build context
```

This avoids vendoring a large upstream source tree while preserving reproducibility.

---

# 10. `.gitignore`

The generated source must not be committed.

Required rule:

```gitignore
# Generated upstream runtime source
.runtime-src/
```

Verification:

```bash
git check-ignore -v .runtime-src/kserve/.ai-platform-upstream-commit
```

Expected concept:

```text
.gitignore:<line>:.runtime-src/
```

---

# 11. `.dockerignore`

The repository used a deny-by-default Docker context policy.

Final relevant structure:

```dockerignore
# More info: https://docs.docker.com/engine/reference/builder/#dockerignore-file
# Ignore everything by default and re-include only needed files
**

# Re-include Go source files (but not *_test.go)
!**/*.go
**/*_test.go

# Re-include Go module files
!go.mod
!go.sum

# Trusted sklearn runtime build inputs.
!.runtime-src/
!.runtime-src/**
!scripts/runtime/
!scripts/runtime/**
!Dockerfile.sklearn-runtime
```

Important distinction:

```text
.gitignore
    controls what Git tracks

.dockerignore
    controls what Docker receives as build context
```

Therefore this is deliberate:

```text
.runtime-src/
    ignored by Git
    included in Docker context
```

---

# 12. Reproducible KServe Source Fetch Script

File:

```text
scripts/runtime/fetch-kserve-source.sh
```

The script pins both the semantic version and exact commit.

Final implementation:

```bash
#!/usr/bin/env bash
set -euo pipefail

KSERVE_VERSION="v0.19.0"
KSERVE_COMMIT="b0eda63d2c105479140af8ec9149d992b7e44be5"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
DEST="${REPO_ROOT}/.runtime-src/kserve"

echo "Fetching KServe ${KSERVE_VERSION}"
echo "Expected commit: ${KSERVE_COMMIT}"
echo "Destination: ${DEST}"

REMOTE_COMMIT="$(
  git ls-remote \
    https://github.com/kserve/kserve.git \
    "refs/tags/${KSERVE_VERSION}" \
  | awk '{print $1}'
)"

if [[ -z "${REMOTE_COMMIT}" ]]; then
  echo "ERROR: unable to resolve ${KSERVE_VERSION}" >&2
  exit 1
fi

if [[ "${REMOTE_COMMIT}" != "${KSERVE_COMMIT}" ]]; then
  echo "ERROR: KServe tag commit mismatch" >&2
  echo "expected=${KSERVE_COMMIT}" >&2
  echo "actual=${REMOTE_COMMIT}" >&2
  exit 1
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT

ARCHIVE="${WORKDIR}/kserve.tar.gz"
SOURCE_DIR="${WORKDIR}/source"

mkdir -p "${SOURCE_DIR}"

curl \
  --fail \
  --location \
  --retry 5 \
  --retry-delay 2 \
  --output "${ARCHIVE}" \
  "https://github.com/kserve/kserve/archive/refs/tags/${KSERVE_VERSION}.tar.gz"

tar \
  -xzf "${ARCHIVE}" \
  --strip-components=1 \
  -C "${SOURCE_DIR}"

rm -rf "${DEST}"
mkdir -p "${DEST}"

# /mnt/data in this environment does not reliably support the symbolic links
# present in the upstream KServe source tree. Dereference them into ordinary
# files while materializing the generated Docker build context.
cp -aL \
  "${SOURCE_DIR}/." \
  "${DEST}/"

printf '%s\n' "${KSERVE_COMMIT}" \
  > "${DEST}/.ai-platform-upstream-commit"

echo "KServe source prepared:"
echo "version=${KSERVE_VERSION}"
echo "commit=${KSERVE_COMMIT}"
echo "path=${DEST}"
echo "symlink handling=dereferenced"
```

Make executable:

```bash
chmod +x scripts/runtime/fetch-kserve-source.sh
git update-index --chmod=+x scripts/runtime/fetch-kserve-source.sh
```

Verify Git mode:

```bash
git ls-files -s scripts/runtime/fetch-kserve-source.sh
```

Expected:

```text
100755 ...
```

---

# 13. `/mnt/data` Symlink Failure and Permanent Fix

The first materialization attempt failed:

```text
mv: cannot create symbolic link '/mnt/data/ai-platform-operator/.runtime-src/kserve/qpext/LICENSE': Input/output error
```

The KServe archive contains symbolic links.

The `/mnt/data` filesystem in this environment does not reliably permit those symlinks.

The initial approach preserved symlinks and therefore failed.

The permanent fix was:

```bash
cp -aL \
  "${WORKDIR}/source/." \
  "$DEST/"
```

`-L` dereferences symbolic links.

This turns the linked path into an ordinary file in `.runtime-src`.

Validation:

```bash
ls -l .runtime-src/kserve/qpext/LICENSE
```

Observed:

```text
-rwxr-xr-x ... .runtime-src/kserve/qpext/LICENSE
```

Hard assertion:

```bash
if [ -L .runtime-src/kserve/qpext/LICENSE ]; then
  echo "FAIL: still a symlink"
else
  echo "PASS: LICENSE materialized as a normal file"
fi
```

Observed:

```text
PASS: LICENSE materialized as a normal file
```

This is a build-context adaptation, not a claim that upstream KServe contains no symlinks.

---

# 14. Upstream Commit Marker

After materialization:

```bash
cat .runtime-src/kserve/.ai-platform-upstream-commit
```

Expected:

```text
b0eda63d2c105479140af8ec9149d992b7e44be5
```

This provides a local build-context marker for the verified upstream source.

---

# 15. Dependency Patch Script

File:

```text
scripts/runtime/patch-kserve-dependencies.py
```

Final intended implementation:

```python
#!/usr/bin/env python3

from pathlib import Path


SCRIPT = Path(__file__).resolve()
REPO_ROOT = SCRIPT.parents[2]
ROOT = REPO_ROOT / ".runtime-src" / "kserve" / "python"


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text()

    if old not in text:
        raise SystemExit(
            f"Expected dependency text not found in {path}: {old!r}"
        )

    path.write_text(text.replace(old, new, 1))


kserve_pyproject = ROOT / "kserve" / "pyproject.toml"
storage_pyproject = ROOT / "storage" / "pyproject.toml"

if not kserve_pyproject.exists():
    raise SystemExit(
        f"KServe pyproject not found: {kserve_pyproject}\n"
        "Run scripts/runtime/fetch-kserve-source.sh first."
    )

if not storage_pyproject.exists():
    raise SystemExit(
        f"KServe storage pyproject not found: {storage_pyproject}\n"
        "Run scripts/runtime/fetch-kserve-source.sh first."
    )


# KServe runtime dependency policy.
replacements = [
    (
        kserve_pyproject,
        '"fastapi>=0.115.3"',
        '"fastapi==0.136.1"',
    ),
    (
        kserve_pyproject,
        '"starlette==0.49.1"',
        '"starlette>=1.3.1"',
    ),
    (
        kserve_pyproject,
        '"urllib3>=2.6.0"',
        '"urllib3>=2.7.0"',
    ),
    (
        kserve_pyproject,
        '"aiohttp>=3.13.3"',
        '"aiohttp>=3.14.3"',
    ),
    (
        kserve_pyproject,
        '"cryptography>=46.0.5"',
        '"cryptography>=50.0.0"',
    ),
    (
        kserve_pyproject,
        '"python-multipart>=0.0.22"',
        '"python-multipart>=0.0.30"',
    ),
    (
        kserve_pyproject,
        '"pyjwt>=2.12.0"',
        '"pyjwt>=2.13.0"',
    ),
    (
        kserve_pyproject,
        '"pyasn1>=0.6.3"',
        '"pyasn1>=0.6.4"',
    ),

    # KServe storage dependency policy.
    (
        storage_pyproject,
        '"aiohttp<4.0.0,>=3.10.0"',
        '"aiohttp<4.0.0,>=3.14.3"',
    ),
    (
        storage_pyproject,
        '"dulwich>=0.21.0"',
        '"dulwich>=1.2.5"',
    ),
    (
        storage_pyproject,
        '"cryptography>=46.0.5"',
        '"cryptography>=50.0.0"',
    ),
    (
        storage_pyproject,
        '"pyjwt>=2.12.0"',
        '"pyjwt>=2.13.0"',
    ),
    (
        storage_pyproject,
        '"pyasn1>=0.6.3"',
        '"pyasn1>=0.6.4"',
    ),
]


for path, old, new in replacements:
    replace_exact(path, old, new)


print(f"Patched KServe runtime dependency policy in: {ROOT}")
```

The intentional property is:

```text
old expected text missing
        ↓
script fails
        ↓
upstream drift becomes visible
```

We do not silently patch a source version we no longer recognize.

---

# 16. Run the Fetch + Patch Pipeline

**🟦 SOURCE REPO**

```bash
cd /mnt/data/ai-platform-operator
```

Fetch:

```bash
./scripts/runtime/fetch-kserve-source.sh
```

Observed successful output:

```text
Fetching KServe v0.19.0
Expected commit: b0eda63d2c105479140af8ec9149d992b7e44be5
Destination: /mnt/data/ai-platform-operator/.runtime-src/kserve
KServe source prepared:
version=v0.19.0
commit=b0eda63d2c105479140af8ec9149d992b7e44be5
path=/mnt/data/ai-platform-operator/.runtime-src/kserve
symlink handling=dereferenced
```

Verify marker:

```bash
cat .runtime-src/kserve/.ai-platform-upstream-commit
```

Patch:

```bash
python3 scripts/runtime/patch-kserve-dependencies.py
```

Observed:

```text
Patched KServe runtime dependency policy in: /mnt/data/ai-platform-operator/.runtime-src/kserve/python
```

Verify hardened KServe constraints:

```bash
grep -nE \
  'fastapi|starlette|urllib3|aiohttp|cryptography|python-multipart|pyjwt|pyasn1' \
  .runtime-src/kserve/python/kserve/pyproject.toml
```

Observed values included:

```text
fastapi==0.136.1
starlette>=1.3.1
urllib3>=2.7.0
aiohttp>=3.14.3
cryptography>=50.0.0
python-multipart>=0.0.30
pyjwt>=2.13.0
pyasn1>=0.6.4
```

---

# 17. Final Runtime Dockerfile

File:

```text
Dockerfile.sklearn-runtime
```

The final design is a source rebuild rather than a wrapper around the vulnerable upstream image.

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.11-slim-bookworm AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV VIRTUAL_ENV=/prod_venv
ENV PATH="/prod_venv/bin:/root/.local/bin:${PATH}"
ENV UV_HTTP_TIMEOUT=120

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       curl \
       python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf \
      https://astral.sh/uv/0.11.21/install.sh \
    | sh

RUN python -m venv "${VIRTUAL_ENV}"

WORKDIR /build/python

COPY .runtime-src/kserve/python/kserve ./kserve
COPY .runtime-src/kserve/python/storage ./storage
COPY .runtime-src/kserve/python/sklearnserver ./sklearnserver

# Resolve the KServe dependency graph using targeted upgrades.
RUN --mount=type=cache,target=/root/.cache/uv \
    cd kserve \
    && uv lock \
       --upgrade-package starlette \
       --upgrade-package urllib3 \
       --upgrade-package aiohttp \
       --upgrade-package cryptography \
       --upgrade-package python-multipart \
       --upgrade-package pyjwt \
       --upgrade-package pyasn1 \
    && uv sync \
       --active \
       --no-dev

# Install KServe storage into the same production virtual environment.
RUN --mount=type=cache,target=/root/.cache/uv \
    cd storage \
    && uv pip install \
       --python "${VIRTUAL_ENV}/bin/python" \
       .

# Resolve sklearnserver with the same hardened production policy.
RUN --mount=type=cache,target=/root/.cache/uv \
    cd sklearnserver \
    && uv lock \
       --upgrade-package starlette \
       --upgrade-package urllib3 \
       --upgrade-package aiohttp \
       --upgrade-package cryptography \
       --upgrade-package python-multipart \
       --upgrade-package pyjwt \
       --upgrade-package pyasn1 \
       --upgrade-package dulwich \
    && uv sync \
       --active \
       --no-dev

# Fail the build if core package identities are not what we expect.
RUN "${VIRTUAL_ENV}/bin/python" - <<'PY'
from importlib import metadata

expected = {
    "kserve": "0.19.0",
    "fastapi": "0.136.1",
}

for package, wanted in expected.items():
    actual = metadata.version(package)
    if actual != wanted:
        raise SystemExit(
            f"{package}: expected {wanted}, got {actual}"
        )

try:
    metadata.version("black")
except metadata.PackageNotFoundError:
    pass
else:
    raise SystemExit("black must not be installed in the production runtime")

print("Runtime dependency checks passed.")
PY


FROM python:3.11-slim-bookworm AS runtime

ENV VIRTUAL_ENV=/prod_venv
ENV PATH="/prod_venv/bin:${PATH}"
ENV PYTHONPATH=/sklearnserver

# pip/setuptools/wheel are not needed by the running model server.
# Removing them also removes scanner-visible packaging metadata that was
# responsible for the final two HIGH findings.
RUN /usr/local/bin/python -m pip uninstall --yes \
      pip \
      setuptools \
      wheel

COPY --from=builder /prod_venv /prod_venv
COPY --from=builder /build/python/kserve /kserve
COPY --from=builder /build/python/storage /storage
COPY --from=builder /build/python/sklearnserver /sklearnserver

USER 1000

ENTRYPOINT ["python", "-m", "sklearnserver"]
```

## Important implementation notes

The exact build retained these properties:

```text
Python:       3.11
VENV:         /prod_venv
KServe:       0.19.0
USER:         1000
PYTHONPATH:   /sklearnserver
ENTRYPOINT:   python -m sklearnserver
```

Targeted `uv lock --upgrade-package` was preferred to a global upgrade.

Production sync used:

```text
--no-dev
```

to prevent Black and test tooling from entering the runtime.

The final stage removed global packaging tooling because it was not needed to run sklearnserver.

---

# 18. Local Build

After regenerating `.runtime-src` from scratch:

```bash
docker build \
  --progress=plain \
  --platform linux/amd64 \
  -f Dockerfile.sklearn-runtime \
  -t ai-platform-sklearnserver:repro-test \
  .
```

Earlier remediation iterations used:

```text
ai-platform-sklearnserver:patched-test
```

The important distinction of `repro-test` was that it proved the image could be recreated from the repository-controlled fetch/patch pipeline rather than a stale local source tree.

---

# 19. Runtime Image Metadata Validation

Example metadata inspection:

```bash
docker image inspect \
  ai-platform-sklearnserver:patched-test \
  --format '
Id={{.Id}}
Architecture={{.Architecture}}
Os={{.Os}}
User={{.Config.User}}
Entrypoint={{json .Config.Entrypoint}}
Env={{json .Config.Env}}
'
```

Observed:

```text
Architecture=amd64
Os=linux
User=1000
Entrypoint=["python","-m","sklearnserver"]
```

The runtime executed from:

```text
/prod_venv/bin/python
```

and had:

```text
PYTHONPATH=/sklearnserver
```

---

# 20. Package Version Validation

Command:

```bash
docker run --rm \
  --entrypoint python \
  ai-platform-sklearnserver:patched-test \
  -c '
from importlib import metadata

packages = [
    "kserve",
    "fastapi",
    "starlette",
    "PyJWT",
    "aiohttp",
    "cryptography",
    "dulwich",
    "pyasn1",
    "python-multipart",
    "urllib3",
    "scikit-learn",
]

print("===== RUNTIME PACKAGE VERSIONS =====")

for package in packages:
    d = metadata.distribution(package)
    print(f"{package}={d.version}")
'
```

Validated results:

```text
kserve=0.19.0
fastapi=0.136.1
starlette=1.6.0
PyJWT=2.13.0
aiohttp=3.14.3
cryptography=50.0.0
dulwich=1.2.12
pyasn1=0.6.4
python-multipart=0.0.32
urllib3=2.7.0
scikit-learn=1.5.2
```

The resolver was therefore allowed to choose secure compatible versions above the configured floors where appropriate.

---

# 21. Prove Black Is Not Installed

```bash
docker run --rm \
  --entrypoint python \
  ai-platform-sklearnserver:patched-test \
  -c '
from importlib import metadata

try:
    d = metadata.distribution("black")
except metadata.PackageNotFoundError:
    print("PASS: black is not installed")
else:
    raise SystemExit(
        f"FAIL: black is installed: {d.version}"
    )
'
```

Observed:

```text
PASS: black is not installed
```

---

# 22. Core Import Smoke Test

```bash
docker run --rm \
  --entrypoint python \
  ai-platform-sklearnserver:patched-test \
  -c '
import fastapi
import starlette
import kserve
import sklearn
import pandas
import numpy
import aiohttp
import cryptography
import jwt
import urllib3

print("PASS: core runtime imports succeeded")
'
```

Observed:

```text
PASS: core runtime imports succeeded
```

---

# 23. CLI Smoke Test

```bash
docker run --rm \
  ai-platform-sklearnserver:patched-test \
  --help >/tmp/sklearn-help.txt

echo "exit=$?"
head -20 /tmp/sklearn-help.txt
```

Observed:

```text
exit=0
```

For the reproducibility image:

```bash
docker run --rm \
  ai-platform-sklearnserver:repro-test \
  --help >/dev/null

echo "runtime_exit=$?"
```

Expected:

```text
runtime_exit=0
```

This proves sklearnserver initialization and CLI parsing.

It does **not** by itself prove a trained model can be loaded and predicted against. That real prediction test is intentionally left for the next model-storage/InferenceService stage.

---

# 24. Trivy Gate — Exact Blocking Command

The final local blocking command was:

```bash
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:0.70.0 \
  image \
  --scanners vuln \
  --severity HIGH,CRITICAL \
  --ignore-unfixed \
  --pkg-types os,library \
  --exit-code 1 \
  --skip-version-check \
  ai-platform-sklearnserver:patched-test
```

For reproducibility validation:

```bash
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:0.70.0 \
  image \
  --scanners vuln \
  --severity HIGH,CRITICAL \
  --ignore-unfixed \
  --pkg-types os,library \
  --exit-code 1 \
  --skip-version-check \
  ai-platform-sklearnserver:repro-test

echo "trivy_exit=$?"
```

Final expected:

```text
trivy_exit=0
```

---

# 25. Security Remediation Sequence

The vulnerability-remediation history matters because it explains why the Dockerfile looks the way it does.

## Stage 1 — upstream runtime

```text
20 HIGH
0 CRITICAL
```

The release was blocked.

## Stage 2 — source-level dependency rebuild

The targeted runtime dependency remediation reduced the scan to:

```text
2 HIGH
0 CRITICAL
```

The remaining findings were:

```text
jaraco.context 5.3.0
wheel 0.45.1
```

Those were scanner-visible global packaging/tooling metadata, not the active KServe `/prod_venv` dependency graph.

## Stage 3 — remove unnecessary global packaging tooling

Final image removed:

```text
pip
setuptools
wheel
```

from the final Python base environment.

Final blocking result:

```text
0 HIGH
0 CRITICAL
exit code 0
```

The security policy was never weakened.

---

# 26. Reproducibility Acceptance Gate

The reproducibility checkpoint was:

```text
fresh Git checkout
        |
        v
fetch exact KServe v0.19.0
        |
        v
verify exact commit
        |
        v
materialize source
        |
        v
patch dependencies
        |
        v
docker build
        |
        v
runtime --help
        |
        v
Trivy HIGH/CRITICAL
        |
        v
PASS
```

The successful fetch output included:

```text
version=v0.19.0
commit=b0eda63d2c105479140af8ec9149d992b7e44be5
symlink handling=dereferenced
```

The final Trivy output returned:

```text
trivy_exit=0
```

---

# 27. Runtime Release Workflow

File:

```text
.github/workflows/release-sklearn-runtime.yml
```

The final workflow performs PR validation without publishing, then performs release/attestation on `main`.

```yaml
name: Release sklearn Runtime

on:
  pull_request:
    branches:
      - main
    paths:
      - Dockerfile.sklearn-runtime
      - .dockerignore
      - scripts/runtime/**
      - .github/workflows/release-sklearn-runtime.yml

  push:
    branches:
      - main
    paths:
      - Dockerfile.sklearn-runtime
      - .dockerignore
      - scripts/runtime/**
      - .github/workflows/release-sklearn-runtime.yml

  workflow_dispatch:

permissions: {}

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ai-platform-sklearnserver

jobs:
  build-runtime:
    name: Build sklearn Runtime
    runs-on: ubuntu-latest

    outputs:
      digest: ${{ steps.build.outputs.digest }}

    permissions:
      contents: read
      packages: write
      attestations: write
      id-token: write

    steps:
      - name: Clone the code
        uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
        with:
          persist-credentials: false

      - name: Fetch pinned KServe source
        shell: bash
        run: |
          set -euo pipefail

          ./scripts/runtime/fetch-kserve-source.sh

      - name: Apply hardened runtime dependency policy
        shell: bash
        run: |
          set -euo pipefail

          python3 scripts/runtime/patch-kserve-dependencies.py

      - name: Verify prepared KServe source
        shell: bash
        run: |
          set -euo pipefail

          EXPECTED_COMMIT="b0eda63d2c105479140af8ec9149d992b7e44be5"

          ACTUAL_COMMIT="$(
            cat .runtime-src/kserve/.ai-platform-upstream-commit
          )"

          if [[ "$ACTUAL_COMMIT" != "$EXPECTED_COMMIT" ]]; then
            echo "ERROR: prepared KServe source does not match expected commit" >&2
            echo "expected=${EXPECTED_COMMIT}" >&2
            echo "actual=${ACTUAL_COMMIT}" >&2
            exit 1
          fi

          grep -F '"fastapi==0.136.1"' \
            .runtime-src/kserve/python/kserve/pyproject.toml

          grep -F '"starlette>=1.3.1"' \
            .runtime-src/kserve/python/kserve/pyproject.toml

          grep -F '"cryptography>=50.0.0"' \
            .runtime-src/kserve/python/kserve/pyproject.toml

          echo "Prepared KServe source verified."

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@bb05f3f5519dd87d3ba754cc423b652a5edd6d2c # v4.2.0

      - name: Define image metadata
        id: meta
        shell: bash
        run: |
          set -euo pipefail

          echo "image=${REGISTRY}/${GITHUB_REPOSITORY_OWNER}/${IMAGE_NAME}" >> "$GITHUB_OUTPUT"
          echo "tag=sha-${GITHUB_SHA}" >> "$GITHUB_OUTPUT"
          echo "local=${IMAGE_NAME}:ci-${GITHUB_SHA}" >> "$GITHUB_OUTPUT"

      - name: Build runtime for security validation
        uses: docker/build-push-action@53b7df96c91f9c12dcc8a07bcb9ccacbed38856a
        with:
          context: .
          file: ./Dockerfile.sklearn-runtime
          platforms: linux/amd64
          load: true
          push: false
          tags: ${{ steps.meta.outputs.local }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Smoke test runtime
        shell: bash
        env:
          IMAGE: ${{ steps.meta.outputs.local }}
        run: |
          set -euo pipefail

          docker run --rm \
            "$IMAGE" \
            --help >/tmp/sklearn-help.txt

          test -s /tmp/sklearn-help.txt

          echo "Runtime smoke test passed."

      - name: Scan runtime image
        uses: aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25 # v0.36.0
        with:
          image-ref: ${{ steps.meta.outputs.local }}
          format: table
          exit-code: '1'
          ignore-unfixed: true
          vuln-type: os,library
          severity: HIGH,CRITICAL

      - name: Generate runtime SBOM
        uses: anchore/sbom-action@e22c389904149dbc22b58101806040fa8d37a610 # v0.24.0
        with:
          image: ${{ steps.meta.outputs.local }}
          format: spdx-json
          output-file: sklearn-runtime-sbom.spdx.json

      - name: Log in to GHCR
        if: github.event_name != 'pull_request'
        uses: docker/login-action@dbcb813823bdd20940b903addbd779551569679f # v4.6.0
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push runtime
        if: github.event_name != 'pull_request'
        id: build
        uses: docker/build-push-action@53b7df96c91f9c12dcc8a07bcb9ccacbed38856a
        with:
          context: .
          file: ./Dockerfile.sklearn-runtime
          platforms: linux/amd64
          push: true
          tags: |
            ${{ steps.meta.outputs.image }}:${{ steps.meta.outputs.tag }}
          cache-from: type=gha

      - name: Generate runtime provenance
        if: github.event_name != 'pull_request'
        uses: actions/attest@508db95dd578ae2727ebd6217d5ba78e4fbda05d # v4.2.1
        with:
          subject-name: ${{ steps.meta.outputs.image }}
          subject-digest: ${{ steps.build.outputs.digest }}
          push-to-registry: true

      - name: Attest runtime SBOM
        if: github.event_name != 'pull_request'
        uses: actions/attest@508db95dd578ae2727ebd6217d5ba78e4fbda05d # v4.2.1
        with:
          subject-name: ${{ steps.meta.outputs.image }}
          subject-digest: ${{ steps.build.outputs.digest }}
          predicate-type: https://spdx.dev/Document/v2.3
          predicate-path: sklearn-runtime-sbom.spdx.json
          push-to-registry: true

      - name: Print immutable runtime reference
        if: github.event_name != 'pull_request'
        shell: bash
        env:
          IMAGE: ${{ steps.meta.outputs.image }}
          DIGEST: ${{ steps.build.outputs.digest }}
        run: |
          set -euo pipefail

          echo
          echo "===== IMMUTABLE SKLEARN RUNTIME ====="
          echo "${IMAGE}@${DIGEST}"
```

---

# 28. Why Pull Requests Run the Runtime Workflow

The first version of the workflow only triggered on:

```text
push to main
workflow_dispatch
```

That meant the runtime release implementation itself would not be tested until after merge.

This was corrected.

PR behavior:

```text
checkout
fetch source
verify source
patch dependencies
build
smoke
Trivy
SBOM
STOP
```

Main behavior:

```text
same validation
        |
        v
GHCR login
        |
        v
push
        |
        v
provenance
        |
        v
SBOM attestation
        |
        v
digest output
```

Publishing steps use:

```yaml
if: github.event_name != 'pull_request'
```

This prevents untrusted PR contexts from publishing images.

---

# 29. CI Failure: Fetch Script Permission Denied

The first PR runtime validation failed:

```text
./scripts/runtime/fetch-kserve-source.sh: Permission denied
Process completed with exit code 126
```

Git showed:

```text
100644 scripts/runtime/fetch-kserve-source.sh
```

The fix:

```bash
chmod +x scripts/runtime/fetch-kserve-source.sh
git update-index --chmod=+x scripts/runtime/fetch-kserve-source.sh
```

Validation:

```bash
git ls-files -s scripts/runtime/fetch-kserve-source.sh
```

Expected:

```text
100755
```

Commit:

```bash
git commit -m "fix(runtime): mark KServe fetch script executable"
```

Resulting commit:

```text
790eaa7
```

After push, PR checks passed.

---

# 30. Source Repository Git History

Relevant runtime sequence:

Initial trusted runtime source PR:

```text
PR #4
feat(runtime): add trusted sklearn serving image
merge/main commit:
6aa37e1fdc4f465777a891d632e19b53f80d6b86
```

That first implementation was blocked by upstream vulnerabilities.

Hardened runtime feature branch:

```text
fix/sklearn-runtime-vulnerabilities
```

PR validation workflow commit:

```text
b538f0b
ci(runtime): validate sklearn runtime on pull requests
```

Executable-bit fix:

```text
790eaa7
fix(runtime): mark KServe fetch script executable
```

Hardened runtime PR:

```text
PR #12
fix(runtime): rebuild trusted sklearn runtime
```

Merged:

```text
1659c277a6ce20e06372826810ce796368a45d17
```

This became the source correlation SHA for the released runtime.

---

# 31. PR Validation

PR #12 completed with:

```text
0 cancelled
0 failing
13 successful
0 skipped
0 pending
```

The important runtime check was:

```text
Release sklearn Runtime / Build sklearn Runtime (pull_request)
PASS
```

Other source repository checks also passed, including:

```text
CodeQL
E2E
Gitleaks
Go Vulnerability Scan
Lint
Tests
GitGuardian
```

---

# 32. Main Release

After PR #12 merge, the main runtime workflow ran:

```text
Run ID:
32635369462
```

Job:

```text
97184181704
```

Result:

```text
Build sklearn Runtime
SUCCESS
```

SBOM artifact included:

```text
ai-platform-sklearnserver_ci-1659c277a6ce20e06372826810ce796368a45d17.spdx.json
```

---

# 33. Source SHA → Registry Tag → Digest

Source commit:

```text
1659c277a6ce20e06372826810ce796368a45d17
```

Source-correlated registry tag:

```text
ghcr.io/anselem-okeke/ai-platform-sklearnserver:sha-1659c277a6ce20e06372826810ce796368a45d17
```

Workflow immutable output:

```text
ghcr.io/anselem-okeke/ai-platform-sklearnserver@sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f
```

Verification:

```bash
SOURCE_SHA="1659c277a6ce20e06372826810ce796368a45d17"
IMAGE="ghcr.io/anselem-okeke/ai-platform-sklearnserver"
DIGEST="sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f"

docker buildx imagetools inspect \
  "${IMAGE}:sha-${SOURCE_SHA}"
```

Observed:

```text
MediaType: application/vnd.oci.image.index.v1+json
Digest: sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f
```

Hard assertion:

```bash
ACTUAL_DIGEST="$(
  docker buildx imagetools inspect \
    "${IMAGE}:sha-${SOURCE_SHA}" \
    --format '{{json .Manifest}}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["digest"])'
)"

echo "expected=${DIGEST}"
echo "actual=${ACTUAL_DIGEST}"

test "$ACTUAL_DIGEST" = "$DIGEST"

echo "PASS: source SHA tag resolves to expected immutable digest"
```

Observed:

```text
PASS: source SHA tag resolves to expected immutable digest
```

---

# 34. OCI Manifest Details

The published top-level OCI index digest is:

```text
sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f
```

The linux/amd64 image manifest under that index is:

```text
sha256:cb5b509b8b9f851e18fbc6ddb0b1a732650799f4b07737f5db37450e290467e2
```

A BuildKit attestation manifest was also present:

```text
sha256:cf29af8bd3f6d5a3ab55857c5711c3e9ef1c5dd97bbeeac16d34cb98596eaef2
```

For GitOps, the selected immutable deployment identity is the published top-level digest:

```text
sha256:42aa6c49...
```

Do not replace it with the child AMD64 manifest digest unless the registry/deployment model is intentionally changed.

---

# 35. GitHub Attestation Objects

GitHub Actions generated provenance and SBOM attestations against the runtime digest.

Runtime subject digest:

```text
sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f
```

Provenance attestation OCI object observed:

```text
sha256:2d18700851667178e173f568cca6b25888476f67fc4d792e4b6fba688377feb4
```

SBOM attestation OCI object observed:

```text
sha256:addcde7d186757b7c6068ac22852829e0e3d2bb31e6ae72df0cfaa2ca500417f
```

These are attestation object identities; they do not replace the runtime deployment digest.

---

# 36. GitHub CLI Upgrade for Attestation Verification

The server initially had:

```text
gh 2.45.0
```

which did not expose:

```text
gh attestation
```

The Ubuntu repository candidate was also `2.45.0`, so simply running an Ubuntu package upgrade would not add the command.

After upgrading GitHub CLI using the official GitHub package repository, `gh attestation verify` became available.

---

# 37. Verify SLSA Provenance

```bash
IMAGE="ghcr.io/anselem-okeke/ai-platform-sklearnserver"
DIGEST="sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f"

gh attestation verify \
  "oci://${IMAGE}@${DIGEST}" \
  --repo anselem-okeke/ai-platform-operator
```

Verification enforced:

```text
Predicate:
https://slsa.dev/provenance/v1

Source Repository Owner:
https://github.com/anselem-okeke

Source Repository:
https://github.com/anselem-okeke/ai-platform-operator

OIDC Issuer:
https://token.actions.githubusercontent.com
```

Observed:

```text
✓ Verification succeeded!
```

Build workflow identity:

```text
.github/workflows/release-sklearn-runtime.yml@refs/heads/main
```

---

# 38. Verify SPDX SBOM Attestation

```bash
gh attestation verify \
  "oci://${IMAGE}@${DIGEST}" \
  --repo anselem-okeke/ai-platform-operator \
  --predicate-type https://spdx.dev/Document/v2.3
```

Observed:

```text
✓ Verification succeeded!
```

Therefore both:

```text
SLSA provenance
SPDX SBOM attestation
```

were independently verifiable against the exact immutable runtime digest.

---

# 39. Supply-Chain Identity Model

Keep these concepts separate.

## Source SHA

```text
1659c277a6ce20e06372826810ce796368a45d17
```

Meaning:

```text
which source revision produced the release
```

## Registry tag

```text
sha-1659c277a6ce20e06372826810ce796368a45d17
```

Meaning:

```text
human/searchable correlation label
```

## Registry digest

```text
sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f
```

Meaning:

```text
immutable deployment identity
```

## Attestation

Meaning:

```text
cryptographically verifiable statement about that immutable artifact
```

Deployment state uses the digest, not the source SHA tag.

---

# 40. GitOps Runtime Design

After the runtime passed all source-side release checks, deployment ownership moved to GitOps.

Architecture:

```text
verified GHCR digest
      |
      +--> Sigstore trust policy
      |
      +--> ClusterServingRuntime
      |
      v
GitOps PR
      |
      v
GitOps CI
      |
      v
human merge
      |
      v
Argo CD
      |
      v
live KServe runtime
```

---

# 41. GitOps Feature Branch

**🟩 GITOPS REPO**

```bash
cd /mnt/data/ai-platform-gitops
git switch -c feat/kserve-sklearn-runtime
```

Unrelated untracked documentation/images were intentionally not staged.

Never use:

```bash
git add .
```

for this work.

---

# 42. AppProject Permission

`ClusterServingRuntime` is cluster-scoped.

Existing AppProject already allowed:

```yaml
- group: serving.kserve.io
  kind: ClusterStorageContainer
```

Added:

```yaml
- group: serving.kserve.io
  kind: ClusterServingRuntime
```

Resulting section:

```yaml
    - group: serving.kserve.io
      kind: ClusterStorageContainer

    - group: serving.kserve.io
      kind: ClusterServingRuntime
```

File:

```text
argocd/projects/ai-platform.yaml
```

This permission is mandatory. Without it, Argo reports:

```text
resource serving.kserve.io:ClusterServingRuntime is not permitted in project ai-platform
```

---

# 43. Sigstore Trust Extension

Existing first-party trust images:

```yaml
images:
  - "ghcr.io/anselem-okeke/ai-platform-operator**"
  - "ghcr.io/anselem-okeke/ai-platform-api**"
```

Added runtime:

```yaml
  - "ghcr.io/anselem-okeke/ai-platform-sklearnserver**"
```

File:

```text
clusters/dev/apps/trust-policies.yaml
```

Final relevant Application:

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
      releaseName: trust-policies
      valuesObject:
        policy:
          enabled: true
          organization: anselem-okeke
          images:
            - "ghcr.io/anselem-okeke/ai-platform-operator**"
            - "ghcr.io/anselem-okeke/ai-platform-api**"
            - "ghcr.io/anselem-okeke/ai-platform-sklearnserver**"

  destination:
    server: https://kubernetes.default.svc
    namespace: cosign-system

  syncPolicy:
    automated:
      prune: true
      selfHeal: true

    syncOptions:
      - CreateNamespace=true
```

The `ai-platform` namespace already had:

```text
policy.sigstore.dev/include=true
```

so extending the trusted image set was required before running first-party model-serving Pods there.

---

# 44. Runtime GitOps Layout

Created:

```text
platform/kserve/runtimes/
├── base/
│   ├── kserve-sklearnserver.yaml
│   └── kustomization.yaml
└── overlays/
    └── dev/
        └── kustomization.yaml

clusters/dev/apps/
└── kserve-runtimes.yaml
```

---

# 45. `ClusterServingRuntime` Manifest

File:

```text
platform/kserve/runtimes/base/kserve-sklearnserver.yaml
```

Final manifest:

```yaml
apiVersion: serving.kserve.io/v1alpha1
kind: ClusterServingRuntime
metadata:
  name: kserve-sklearnserver
  annotations:
    serving.kserve.io/server-type: sklearnserver
spec:
  annotations:
    prometheus.kserve.io/path: /metrics
    prometheus.kserve.io/port: "8080"

  supportedModelFormats:
    - name: sklearn
      version: "1"
      autoSelect: true
      priority: 1

  protocolVersions:
    - v1
    - v2

  containers:
    - name: kserve-container
      image: ghcr.io/anselem-okeke/ai-platform-sklearnserver@sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f

      args:
        - --model_name={{.Name}}
        - --model_dir=/mnt/models
        - --http_port=8080

      resources:
        requests:
          cpu: "1"
          memory: 2Gi
        limits:
          cpu: "1"
          memory: 2Gi

      securityContext:
        allowPrivilegeEscalation: false
        capabilities:
          drop:
            - ALL
        privileged: false
        runAsNonRoot: true
```

This preserved the upstream runtime contract and replaced only the image identity.

---

# 46. Runtime Base Kustomization

File:

```text
platform/kserve/runtimes/base/kustomization.yaml
```

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - kserve-sklearnserver.yaml
```

---

# 47. Runtime Dev Overlay

File:

```text
platform/kserve/runtimes/overlays/dev/kustomization.yaml
```

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base
```

---

# 48. Argo CD Runtime Application

File:

```text
clusters/dev/apps/kserve-runtimes.yaml
```

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: kserve-runtimes
  namespace: argocd

  finalizers:
    - resources-finalizer.argocd.argoproj.io

spec:
  project: ai-platform

  source:
    repoURL: https://github.com/anselem-okeke/ai-platform-gitops.git
    targetRevision: HEAD
    path: platform/kserve/runtimes/overlays/dev

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

The runtime resource itself is cluster-scoped. The Application destination namespace remains `kserve` as the Argo destination context.

---

# 49. Root App-of-Apps Registration

File:

```text
clusters/dev/apps/kustomization.yaml
```

The runtime Application was added after KServe:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - kserve-crd.yaml
  - kserve.yaml
  - kserve-runtimes.yaml
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

---

# 50. Local GitOps Validation

Render runtime:

```bash
kubectl kustomize platform/kserve/runtimes/overlays/dev
```

Expected resource:

```text
kind: ClusterServingRuntime
name: kserve-sklearnserver
```

Exact image check:

```bash
kubectl kustomize platform/kserve/runtimes/overlays/dev \
  | grep -F \
  'ghcr.io/anselem-okeke/ai-platform-sklearnserver@sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f'
```

Server-side dry-run:

```bash
kubectl apply \
  --dry-run=server \
  -f <(kubectl kustomize platform/kserve/runtimes/overlays/dev)
```

Observed:

```text
clusterservingruntime.serving.kserve.io/kserve-sklearnserver created (server dry run)
```

---

# 51. Root App Tree Validation

```bash
kubectl kustomize clusters/dev/apps >/tmp/dev-apps.yaml
echo "render_exit=$?"
```

Observed:

```text
render_exit=0
```

AppProject dry-run:

```bash
kubectl apply \
  --dry-run=server \
  -f argocd/projects/ai-platform.yaml
```

Observed:

```text
appproject.argoproj.io/ai-platform configured (server dry run)
```

Runtime Application dry-run:

```bash
kubectl apply \
  --dry-run=server \
  -f clusters/dev/apps/kserve-runtimes.yaml
```

Observed:

```text
application.argoproj.io/kserve-runtimes created (server dry run)
```

A finalizer naming warning was emitted but did not block validation.

---

# 52. Stage Only Intended GitOps Files

Explicit staging:

```bash
git add \
  argocd/projects/ai-platform.yaml \
  clusters/dev/apps/kustomization.yaml \
  clusters/dev/apps/trust-policies.yaml \
  clusters/dev/apps/kserve-runtimes.yaml \
  platform/kserve/runtimes/base/kserve-sklearnserver.yaml \
  platform/kserve/runtimes/base/kustomization.yaml \
  platform/kserve/runtimes/overlays/dev/kustomization.yaml
```

Validation:

```bash
git status --short
git diff --cached --name-only
git diff --cached --check
```

Intended staged files:

```text
argocd/projects/ai-platform.yaml
clusters/dev/apps/kserve-runtimes.yaml
clusters/dev/apps/kustomization.yaml
clusters/dev/apps/trust-policies.yaml
platform/kserve/runtimes/base/kserve-sklearnserver.yaml
platform/kserve/runtimes/base/kustomization.yaml
platform/kserve/runtimes/overlays/dev/kustomization.yaml
```

---

# 53. GitOps Commit and PR

Commit:

```bash
git commit -m "feat(kserve): add trusted sklearn serving runtime"
```

Push:

```bash
git push -u origin feat/kserve-sklearn-runtime
```

GitOps PR:

```text
#31
feat(kserve): add trusted sklearn serving runtime
```

Checks:

```bash
gh pr checks 31 --watch
```

Observed:

```text
0 cancelled
0 failing
4 successful
0 skipped
0 pending
```

Passing checks included:

```text
GitGuardian Security Checks
Secret Scan/Gitleaks (push)
Secret Scan/Gitleaks (pull_request)
Validate GitOps/Validate GitOps Manifests (pull_request)
```

---

# 54. GitOps Merge

The established GitOps merge style was squash.

Command:

```bash
gh pr merge 31 --squash --delete-branch
```

Result:

```text
PR #31 merged
```

GitOps main advanced to:

```text
11e694d
```

Full sync revision later observed:

```text
11e694d8d94bb3a7d6542b5e0c60d58fb93163f5
```

Files added/changed:

```text
argocd/projects/ai-platform.yaml
clusters/dev/apps/kserve-runtimes.yaml
clusters/dev/apps/kustomization.yaml
clusters/dev/apps/trust-policies.yaml
platform/kserve/runtimes/base/kserve-sklearnserver.yaml
platform/kserve/runtimes/base/kustomization.yaml
platform/kserve/runtimes/overlays/dev/kustomization.yaml
```

---

# 55. Why the AppProject Required a Manual Apply

This is an important architecture detail.

The root Application does **not** manage:

```text
argocd/projects/ai-platform.yaml
```

The AppProject is part of the bootstrap layer.

Architecture:

```text
Kubernetes bootstrap
       |
       v
AppProject/ai-platform
       |
       v
ai-platform-root
       |
       +--> child Applications
```

The AppProject defines what those child Applications are allowed to deploy.

When the new runtime Application first reconciled, Argo used the **live** AppProject.

Git contained:

```yaml
- group: serving.kserve.io
  kind: ClusterServingRuntime
```

but the live cluster AppProject still had the older whitelist.

Therefore Argo correctly failed with:

```text
resource serving.kserve.io:ClusterServingRuntime is not permitted in project ai-platform
```

This was not a runtime manifest failure.

It was a bootstrap authority mismatch.

---

# 56. Apply the Bootstrap AppProject

**🟩 GITOPS REPO**

```bash
cd /mnt/data/ai-platform-gitops
```

Apply:

```bash
kubectl apply \
  --server-side \
  -f argocd/projects/ai-platform.yaml
```

Observed:

```text
appproject.argoproj.io/ai-platform serverside-applied
```

Verify live permission:

```bash
kubectl get appproject ai-platform \
  -n argocd \
  -o yaml \
  | grep -A5 -B5 'ClusterServingRuntime'
```

Live cluster now contained:

```yaml
- group: serving.kserve.io
  kind: ClusterServingRuntime
```

---

# 57. Argo Retry

Before the bootstrap permission update:

```text
kserve-runtimes  OutOfSync  Missing
```

Argo reported:

```text
resource serving.kserve.io:ClusterServingRuntime is not permitted in project ai-platform
```

After AppProject update:

```bash
argocd app sync kserve-runtimes
```

Wait:

```bash
argocd app wait kserve-runtimes \
  --sync \
  --health \
  --timeout 300
```

Final result:

```text
Sync Status:   Synced to HEAD (11e694d)
Health Status: Healthy
```

Operation:

```text
Phase: Succeeded
Message: successfully synced (all tasks run)
```

Runtime resource:

```text
ClusterServingRuntime kserve-sklearnserver
Running
Synced
```

---

# 58. Verify Trust Policy Is Live

```bash
kubectl get clusterimagepolicy github-policy \
  -o yaml \
  | grep -A10 -B5 'ai-platform-sklearnserver'
```

Live policy included:

```yaml
images:
  - glob: ghcr.io/anselem-okeke/ai-platform-operator**
  - glob: ghcr.io/anselem-okeke/ai-platform-api**
  - glob: ghcr.io/anselem-okeke/ai-platform-sklearnserver**
mode: enforce
```

This proved the runtime image was inside the first-party Sigstore trust boundary.

---

# 59. Verify Runtime Is Live

```bash
kubectl get clusterservingruntime \
  kserve-sklearnserver
```

Observed:

```text
NAME                   DISABLED   MODELTYPE   CONTAINERS
kserve-sklearnserver              sklearn     kserve-container
```

Full:

```bash
kubectl get clusterservingruntime \
  kserve-sklearnserver \
  -o yaml
```

Live image:

```text
ghcr.io/anselem-okeke/ai-platform-sklearnserver@sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f
```

---

# 60. Hard Assertion of Live Digest

```bash
EXPECTED='ghcr.io/anselem-okeke/ai-platform-sklearnserver@sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f'

ACTUAL="$(
  kubectl get clusterservingruntime \
    kserve-sklearnserver \
    -o jsonpath='{.spec.containers[0].image}'
)"

echo "expected=${EXPECTED}"
echo "actual=${ACTUAL}"

test "$ACTUAL" = "$EXPECTED"

echo "PASS: live KServe runtime uses trusted immutable digest"
```

Observed:

```text
expected=ghcr.io/anselem-okeke/ai-platform-sklearnserver@sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f
actual=ghcr.io/anselem-okeke/ai-platform-sklearnserver@sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f
PASS: live KServe runtime uses trusted immutable digest
```

---

# 61. Runtime Registration Summary

```bash
kubectl get clusterservingruntime \
  kserve-sklearnserver \
  -o jsonpath='
name={.metadata.name}
formats={.spec.supportedModelFormats[*].name}
protocols={.spec.protocolVersions[*]}
image={.spec.containers[0].image}
{"\n"}'
```

Observed:

```text
name=kserve-sklearnserver
formats=sklearn
protocols=v1 v2
image=ghcr.io/anselem-okeke/ai-platform-sklearnserver@sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f
```

---

# 62. Final Runtime State

The complete runtime trust chain is:

```text
KServe upstream v0.19.0
        |
        v
commit b0eda63...
        |
        v
reproducible materialized source
        |
        v
hardened dependency policy
        |
        v
controlled Docker build
        |
        v
Trivy 0 HIGH / 0 CRITICAL
        |
        v
source SHA 1659c277...
        |
        v
GHCR sha-1659c277... tag
        |
        v
OCI digest 42aa6c49...
        |
        +--> SLSA provenance VERIFIED
        |
        +--> SPDX SBOM VERIFIED
        |
        v
Sigstore github-policy
        |
        v
GitOps ClusterServingRuntime
        |
        v
Argo kserve-runtimes
        |
        v
LIVE kserve-sklearnserver
```

---

# 63. Security Properties Achieved

## Immutable deployment identity

No mutable tag is used in the live runtime:

```text
@sha256:...
```

## First-party registry boundary

Runtime is:

```text
ghcr.io/anselem-okeke/ai-platform-sklearnserver
```

## Vulnerability gate

Release blocks on:

```text
HIGH
CRITICAL
```

with:

```text
exit-code: 1
```

## Build provenance

GitHub OIDC-backed provenance is attached to the exact digest.

## SBOM

SPDX JSON is generated and attested.

## Admission trust

The live ClusterImagePolicy includes the runtime image pattern.

## Non-root runtime

```text
USER 1000
runAsNonRoot: true
```

## Privilege hardening

```yaml
allowPrivilegeEscalation: false
privileged: false
capabilities:
  drop:
    - ALL
```

---

# 64. What Was Deliberately Not Done

Do not overstate the current implementation.

The following was **not yet empirically proven** during this runtime stage:

```text
trained sklearn model load
real HTTP inference request
InferenceService rollout
S3 model artifact download
external prediction endpoint
```

The runtime itself was validated for:

```text
build
package graph
imports
CLI startup
Trivy
SBOM
provenance
registry identity
attestation verification
Sigstore trust
KServe runtime registration
Argo reconciliation
```

The real model prediction test belongs to the next object-storage + `InferenceService` stage.

---

# 65. Troubleshooting — Trivy Finds 20 HIGH Again

Symptom:

```text
Total: 20 (HIGH: 20, CRITICAL: 0)
```

Likely causes:

```text
using upstream wrapper image again
patch script not run
Docker context contains stale source
uv sync included dev dependencies
```

Recovery:

```bash
rm -rf .runtime-src/kserve

./scripts/runtime/fetch-kserve-source.sh
python3 scripts/runtime/patch-kserve-dependencies.py

docker build \
  --no-cache \
  --progress=plain \
  --platform linux/amd64 \
  -f Dockerfile.sklearn-runtime \
  -t ai-platform-sklearnserver:repro-test \
  .
```

Then rerun blocking Trivy.

Do not change:

```text
--severity HIGH,CRITICAL
--exit-code 1
```

to make the release pass.

---

# 66. Troubleshooting — Two HIGH Remain

Symptom:

```text
jaraco.context
wheel
```

Check whether they are coming from:

```text
/usr/local/lib/python3.11/site-packages
```

rather than `/prod_venv`.

The final runtime does not need pip/setuptools/wheel at runtime.

Ensure final-stage removal exists.

Rebuild and rescan.

---

# 67. Troubleshooting — Black Reappears

Symptom:

```text
black installed
```

Check:

```text
uv sync
```

versus:

```text
uv sync --active --no-dev
```

The latter is required for production.

---

# 68. Troubleshooting — KServe Tag Drift

The fetch script must fail if:

```text
refs/tags/v0.19.0
```

no longer resolves to:

```text
b0eda63d2c105479140af8ec9149d992b7e44be5
```

Do not update the expected SHA silently.

If a version upgrade is intentional:

```text
new KServe version
        |
        v
inspect source/build changes
        |
        v
new exact commit pin
        |
        v
re-run vulnerability analysis
        |
        v
re-test runtime behavior
```

---

# 69. Troubleshooting — Source Fetch Symlink Error

Symptom:

```text
cannot create symbolic link
Input/output error
```

Use the materialization logic:

```bash
cp -aL source/. destination/
```

Do not move a symlink-preserving source tree directly into `/mnt/data`.

---

# 70. Troubleshooting — Fetch Script Permission Denied in Actions

Symptom:

```text
Permission denied
exit code 126
```

Check:

```bash
git ls-files -s scripts/runtime/fetch-kserve-source.sh
```

Expected:

```text
100755
```

Fix:

```bash
chmod +x scripts/runtime/fetch-kserve-source.sh
git update-index --chmod=+x scripts/runtime/fetch-kserve-source.sh
git add scripts/runtime/fetch-kserve-source.sh
git commit -m "fix(runtime): mark KServe fetch script executable"
git push
```

---

# 71. Troubleshooting — Runtime Tag Does Not Match Expected Digest

Inspect:

```bash
docker buildx imagetools inspect \
  "ghcr.io/anselem-okeke/ai-platform-sklearnserver:sha-${SOURCE_SHA}"
```

Do not deploy until:

```text
tag digest == workflow output digest
```

If different:

```text
stop
inspect workflow run
inspect registry
inspect source SHA
do not update GitOps
```

---

# 72. Troubleshooting — `gh attestation` Missing

Check:

```bash
gh --version
```

Old Ubuntu-packaged versions may not include:

```text
gh attestation
```

Install/upgrade GitHub CLI from the official GitHub CLI apt repository, then verify:

```bash
gh attestation --help
```

Do not treat successful Actions attestation steps as the only evidence if independent verification is required.

---

# 73. Troubleshooting — Argo Says Runtime Not Permitted

Symptom:

```text
resource serving.kserve.io:ClusterServingRuntime is not permitted in project ai-platform
```

Check Git:

```bash
grep -nA8 -B4 \
  'ClusterStorageContainer' \
  argocd/projects/ai-platform.yaml
```

Check live:

```bash
kubectl get appproject ai-platform \
  -n argocd \
  -o yaml \
  | grep -A5 -B5 'ClusterServingRuntime'
```

If Git contains the permission but live does not, apply the bootstrap AppProject:

```bash
kubectl apply \
  --server-side \
  -f argocd/projects/ai-platform.yaml
```

Then retry:

```bash
argocd app sync kserve-runtimes
```

---

# 74. Why the AppProject Is Bootstrap-Managed

Current design:

```text
AppProject/ai-platform
        |
        v
ai-platform-root
        |
        v
child Applications
```

The project defines the child's authorization boundary.

If the child Application could expand its own AppProject permission, that would create a circular/self-authorization problem.

Therefore the project currently sits outside the root child tree and must be deliberately applied during bootstrap-authority changes.

A future architecture could introduce:

```text
default/bootstrap project
        |
        v
bootstrap Application
        |
        +--> ai-platform AppProject
        +--> ai-platform-root
```

but that was not introduced during this runtime implementation.

---

# 75. Rollback — Source Runtime

If a new runtime release is bad:

```text
do not mutate the old digest
```

The old digest remains immutable.

Identify the previous known-good runtime digest and update GitOps back to it.

Example:

```yaml
image: ghcr.io/anselem-okeke/ai-platform-sklearnserver@sha256:<known-good>
```

Commit:

```bash
git commit -m "revert(kserve): restore known-good sklearn runtime"
```

Merge through normal GitOps PR validation.

Argo then reconciles the old immutable digest.

---

# 76. Rollback — Trust Policy

If the runtime should no longer be trusted:

remove:

```yaml
- "ghcr.io/anselem-okeke/ai-platform-sklearnserver**"
```

from:

```text
clusters/dev/apps/trust-policies.yaml
```

Merge through GitOps.

Allow `trust-policies` to reconcile.

Be aware that workloads attempting to use that runtime inside an included namespace may then fail admission.

---

# 77. Rollback — Remove Runtime Registration

Remove:

```text
clusters/dev/apps/kserve-runtimes.yaml
```

from the root apps kustomization or remove the specific runtime resource.

Because child Applications use:

```yaml
prune: true
```

Argo can remove managed resources after the Git state is intentionally changed.

Do not manually delete the live runtime as the primary rollback path unless emergency break-glass behavior is required.

---

# 78. Rebuild From Zero — Source Side

**🟦 SOURCE REPO**

```bash
cd /mnt/data/ai-platform-operator

git switch main
git pull --ff-only

rm -rf .runtime-src/kserve

./scripts/runtime/fetch-kserve-source.sh

cat .runtime-src/kserve/.ai-platform-upstream-commit

python3 scripts/runtime/patch-kserve-dependencies.py

docker build \
  --progress=plain \
  --platform linux/amd64 \
  -f Dockerfile.sklearn-runtime \
  -t ai-platform-sklearnserver:repro-test \
  .

docker run --rm \
  ai-platform-sklearnserver:repro-test \
  --help >/dev/null

echo "runtime_exit=$?"

docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:0.70.0 \
  image \
  --scanners vuln \
  --severity HIGH,CRITICAL \
  --ignore-unfixed \
  --pkg-types os,library \
  --exit-code 1 \
  --skip-version-check \
  ai-platform-sklearnserver:repro-test

echo "trivy_exit=$?"
```

Required:

```text
runtime_exit=0
trivy_exit=0
```

---

# 79. Rebuild From Zero — Release Side

Merge a runtime-affecting change to `main`.

The workflow must produce:

```text
ghcr.io/anselem-okeke/ai-platform-sklearnserver:sha-${GITHUB_SHA}
```

and print:

```text
ghcr.io/anselem-okeke/ai-platform-sklearnserver@sha256:<digest>
```

Verify:

```bash
docker buildx imagetools inspect \
  "ghcr.io/anselem-okeke/ai-platform-sklearnserver:sha-${SOURCE_SHA}"
```

Verify provenance:

```bash
gh attestation verify \
  "oci://ghcr.io/anselem-okeke/ai-platform-sklearnserver@${DIGEST}" \
  --repo anselem-okeke/ai-platform-operator
```

Verify SBOM:

```bash
gh attestation verify \
  "oci://ghcr.io/anselem-okeke/ai-platform-sklearnserver@${DIGEST}" \
  --repo anselem-okeke/ai-platform-operator \
  --predicate-type https://spdx.dev/Document/v2.3
```

---

# 80. Rebuild From Zero — GitOps Side

**🟩 GITOPS REPO**

Update the runtime manifest with the new verified digest.

Validate:

```bash
kubectl kustomize \
  platform/kserve/runtimes/overlays/dev

kubectl apply \
  --dry-run=server \
  -f <(
    kubectl kustomize \
      platform/kserve/runtimes/overlays/dev
  )
```

Open GitOps PR.

Wait for GitOps checks.

Merge with the repository's established merge style.

If AppProject permissions are unchanged, no manual AppProject reapply is needed.

If a new cluster-scoped resource kind was added to the AppProject, update the bootstrap AppProject deliberately.

---

# 81. Evidence Snapshot

## Upstream

```text
KServe:
v0.19.0

commit:
b0eda63d2c105479140af8ec9149d992b7e44be5
```

## Source release

```text
source commit:
1659c277a6ce20e06372826810ce796368a45d17
```

## Runtime

```text
image:
ghcr.io/anselem-okeke/ai-platform-sklearnserver
```

## Digest

```text
sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f
```

## Attestations

```text
SLSA provenance: VERIFIED
SPDX SBOM:        VERIFIED
```

## GitOps

```text
PR #31
GitOps revision:
11e694d8d94bb3a7d6542b5e0c60d58fb93163f5
```

## Argo

```text
Application:
kserve-runtimes

Sync:
Synced

Health:
Healthy
```

## Live runtime

```text
name:
kserve-sklearnserver

format:
sklearn

protocols:
v1 v2

image:
ghcr.io/anselem-okeke/ai-platform-sklearnserver@sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f
```

---

# 82. Implementation Definition of Done

The trusted sklearn runtime stage is complete when all of the following are true:

```text
exact KServe source version chosen
exact upstream source commit pinned
source fetch reproducible
source commit verified before build
filesystem symlink behavior handled
dependency policy patch deterministic
production-only dependency sync used
KServe 0.19.0 preserved
runtime imports pass
runtime CLI smoke passes
runtime runs non-root
Trivy HIGH/CRITICAL blocking gate passes
SBOM generated
image pushed to GHCR
source SHA tag resolves to expected digest
SLSA provenance created
SPDX SBOM attestation created
SLSA provenance independently verifies
SPDX SBOM independently verifies
Sigstore trust covers runtime image
ClusterServingRuntime uses exact digest
GitOps CI passes
GitOps PR merged
AppProject allows ClusterServingRuntime
Argo Application is Synced
Argo Application is Healthy
live ClusterServingRuntime exact digest matches release
```

All of those conditions were reached.

---

# 83. Current Boundary / Next Work

The runtime is complete.

The next model-serving block begins at:

```text
model artifact
      |
      v
S3-compatible object storage
      |
      v
KServe InferenceService
      |
      v
kserve-sklearnserver
      |
      v
real prediction
```

The next planned implementation is:

```text
MinIO / S3-compatible storage
model artifact upload
KServe storage credentials
InferenceService
real sklearn model load
HTTP prediction
Gateway/TLS route
ModelService → InferenceService reconciliation
```

That next work should treat two trust boundaries separately:

```text
container image integrity
    ≠
model artifact integrity
```

The runtime stage documented here secures the container image supply chain. The model artifact supply chain is a separate concern and should receive its own controls.

---

# 84. Compact Reproduction Flow

For a new engineer, the shortest end-to-end mental model is:

```text
1. clone source repo
2. fetch exact KServe v0.19.0 source
3. verify exact upstream commit
4. dereference symlinks into .runtime-src
5. patch known vulnerable dependency constraints
6. build hardened sklearnserver image
7. verify runtime metadata/imports/CLI
8. run blocking Trivy scan
9. merge via PR after CI passes
10. main workflow builds and pushes sha-${GITHUB_SHA}
11. record immutable OCI digest
12. verify provenance
13. verify SPDX SBOM attestation
14. update GitOps ClusterServingRuntime with exact digest
15. extend Sigstore trust image list
16. allow ClusterServingRuntime in AppProject
17. validate Kustomize and server-side dry-run
18. merge GitOps PR
19. apply bootstrap AppProject if its permissions changed
20. allow Argo to sync kserve-runtimes
21. verify live ClusterServingRuntime image digest
```

---

# 85. Critical Rules to Preserve

Do not weaken these controls in future changes:

```text
Do not deploy :latest.
Do not deploy a source SHA tag instead of a digest.
Do not disable Trivy HIGH/CRITICAL exit-code blocking.
Do not silently update the KServe source commit.
Do not globally upgrade the KServe dependency graph without review.
Do not reintroduce dev dependencies into the runtime.
Do not commit .runtime-src.
Do not remove Sigstore trust verification for first-party runtime images.
Do not bypass GitOps for routine runtime updates.
Do not confuse image trust with model artifact trust.
```

---

# 86. End State

The final deployed runtime is:

```text
ClusterServingRuntime/kserve-sklearnserver
```

managed by:

```text
Argo CD Application/kserve-runtimes
```

trusted by:

```text
ClusterImagePolicy/github-policy
```

and pinned to:

```text
ghcr.io/anselem-okeke/ai-platform-sklearnserver@sha256:42aa6c49a5348897c923925ab0fdbba16aed8a288346f3c10d3c5af223ec355f
```

This completes the trusted KServe sklearn runtime implementation stage.
