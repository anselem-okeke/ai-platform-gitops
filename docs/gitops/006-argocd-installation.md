# Argo CD Installation

## Purpose

This document records the reproducible installation and validation procedure for Argo CD in the AI Platform development cluster.

## Implemented Version

```text
Argo CD v3.5.1
```

Namespace:

```text
argocd
```

Kubernetes context:

```text
kind-ai-platform-policy
```

## Prerequisites

Verify cluster:

```bash
kubectl config current-context
kubectl get nodes
```

Expected context:

```text
kind-ai-platform-policy
```

Ensure `kubectl` can create cluster-scoped resources.

## 1. Create Namespace

```bash
kubectl create namespace argocd \
  --dry-run=client \
  -o yaml \
  | kubectl apply -f -
```

## 2. Install the Pinned Argo CD Release

For reproducibility, install the exact version used by the project rather than an unpinned `stable` manifest.

Example pinned installation:

```bash
kubectl apply \
  -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.5.1/manifests/install.yaml
```

If the repository stores a vendored/pinned manifest, prefer that repository copy.

## 3. Wait for Control Plane

```bash
kubectl wait \
  --for=condition=Ready \
  pod \
  --all \
  -n argocd \
  --timeout=300s
```

Verify:

```bash
kubectl get pods -n argocd
```

## 4. Verify CRDs

```bash
kubectl get crd | grep argoproj.io
```

Expected CRDs include:

```text
applications.argoproj.io
applicationsets.argoproj.io
appprojects.argoproj.io
```

## 5. Verify Services

```bash
kubectl get svc -n argocd
```

Important service:

```text
argocd-server
```

Observed implementation:

```text
Type: ClusterIP
ClusterIP: 10.96.128.244
Ports: 80/TCP, 443/TCP
```

Do not change it to a public LoadBalancer as the normal access model.

## 6. Install / Verify Argo CD CLI

Verify:

```bash
argocd version --client
```

Install the CLI using the official release instructions for the same Argo CD major/minor version.

## 7. Bootstrap Access

Use port forwarding:

```bash
kubectl port-forward \
  -n argocd \
  svc/argocd-server \
  8080:443
```

Then access:

```text
https://127.0.0.1:8080
```

This is a bootstrap/administrative path.

Steady-state access uses the Gateway + TLS + OIDC model.

## 8. Apply AI Platform AppProject

The AppProject is bootstrap-managed.

From:

```bash
cd /mnt/data/ai-platform-gitops
```

Validate:

```bash
kubectl apply \
  --dry-run=server \
  -f argocd/projects/ai-platform.yaml
```

Apply:

```bash
kubectl apply \
  -f argocd/projects/ai-platform.yaml
```

Verify:

```bash
argocd proj get ai-platform
```

## 9. Apply Root Application

```bash
kubectl apply \
  -f clusters/dev/root-application.yaml
```

Verify:

```bash
argocd app get ai-platform-root --refresh
```

Because the root is manual:

```bash
argocd app sync ai-platform-root
```

Then:

```bash
argocd app wait \
  ai-platform-root \
  --sync \
  --health \
  --timeout 300
```

## 10. Verify Child Applications

```bash
argocd app list
```

Expected includes:

```text
ai-platform-api
ai-platform-operator
ai-platform-gateway
ai-platform-monitoring
ai-platform-modelservices
ai-platform-policies
ai-platform-namespaces
policy-controller
trust-policies
```

## Upgrade Procedure

Before upgrading:

1. read upstream release notes
2. verify Kubernetes compatibility
3. record current version
4. commit version/config change
5. test in development
6. validate OIDC/RBAC
7. validate AppProjects
8. validate Applications
9. validate repository access
10. rerun end-to-end security tests

## Recovery

If Argo is lost but Git remains:

1. reinstall pinned Argo version
2. restore AppProject
3. restore OIDC/RBAC
4. apply root Application
5. manually sync root
6. verify children
7. run Phase 7 validation

## Official References

- Argo CD installation: https://argo-cd.readthedocs.io/en/stable/operator-manual/installation/
- Getting started: https://argo-cd.readthedocs.io/en/stable/getting_started/
- CLI installation: https://argo-cd.readthedocs.io/en/stable/cli_installation/
- Argo CD releases: https://github.com/argoproj/argo-cd/releases
