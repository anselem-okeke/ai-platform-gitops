# GitHub Artifact Attestation Policy

## Purpose

This document is the implementation guide for enforcing GitHub Artifact Attestations in Kubernetes using GitHub's `trust-policies` Helm chart together with Sigstore Policy Controller.

## Implemented Components

```text
Namespace: cosign-system
Trust policy chart: v0.7.0
TrustRoot: github
ClusterImagePolicy: github-policy
GitHub owner: anselem-okeke
```

Protected image patterns:

```text
ghcr.io/anselem-okeke/ai-platform-operator**
ghcr.io/anselem-okeke/ai-platform-api**
```

## Architecture

```text
GitHub Actions release
      |
      +--> build image
      +--> push GHCR digest
      +--> provenance attestation
      +--> SBOM attestation
      |
      v
GHCR image@sha256:digest
      |
      v
TrustRoot/github + ClusterImagePolicy/github-policy
      |
      v
Sigstore Policy Controller
      |
      v
Kubernetes admission
```

## Prerequisites

Before installing trust policies:

```bash
kubectl get pods -n cosign-system
kubectl get crd trustroots.policy.sigstore.dev
kubectl get crd clusterimagepolicies.policy.sigstore.dev
argocd app get policy-controller --refresh
```

Policy Controller must be healthy first.

## AppProject Requirements

`argocd/projects/ai-platform.yaml` must allow:

```text
ghcr.io/github/artifact-attestations-helm-charts
```

and cluster resources:

```text
policy.sigstore.dev / TrustRoot
policy.sigstore.dev / ClusterImagePolicy
```

Because the AppProject is bootstrap-managed:

```bash
cd /mnt/data/ai-platform-gitops
kubectl apply --dry-run=server -f argocd/projects/ai-platform.yaml
kubectl apply -f argocd/projects/ai-platform.yaml
```

## Validated Helm Installation

The working installation command used during implementation was:

```bash
helm upgrade trust-policies --install \
  --rollback-on-failure \
  --namespace cosign-system \
  oci://ghcr.io/github/artifact-attestations-helm-charts/trust-policies \
  --version v0.7.0 \
  -f /tmp/github-attestation-policy-values.yaml
```

Validated values:

```yaml
policy:
  enabled: true
  organization: anselem-okeke
  images:
    - "ghcr.io/anselem-okeke/ai-platform-operator**"
    - "ghcr.io/anselem-okeke/ai-platform-api**"
```

The final platform state is GitOps-managed through the `trust-policies` Argo child Application rather than depending on a manually maintained Helm release.

## GitOps Ownership

Child Application:

```text
clusters/dev/apps/trust-policies.yaml
```

Important values:

```text
repoURL: ghcr.io/github/artifact-attestations-helm-charts
chart: trust-policies
targetRevision: v0.7.0
destination namespace: cosign-system
```

If this child Application is newly added or its topology changes, synchronize the manual root:

```bash
argocd app get ai-platform-root --refresh
argocd app sync ai-platform-root
argocd app wait ai-platform-root --sync --health --timeout 300
```

Then:

```bash
argocd app get trust-policies --refresh
argocd app wait trust-policies --sync --health --timeout 300
```

## Namespace Enforcement

The trust policy is not enforced merely because the TrustRoot and ClusterImagePolicy exist.

Protected namespaces must carry:

```yaml
metadata:
  labels:
    policy.sigstore.dev/include: "true"
```

Validated namespaces:

```text
ai-platform
ai-platform-operator-system
```

Verify:

```bash
kubectl get namespace ai-platform --show-labels
kubectl get namespace ai-platform-operator-system --show-labels
```

## Trust Resources

Verify:

```bash
kubectl get trustroot github -o yaml
kubectl get clusterimagepolicy github-policy -o yaml
```

The TrustRoot defines the trust material used to verify GitHub attestations. The ClusterImagePolicy specifies how image attestations are evaluated.

## Positive Verification

A known release image produced by the trusted GitHub workflow should pass admission:

```bash
kubectl rollout restart deployment/ai-platform-api -n ai-platform
kubectl rollout status deployment/ai-platform-api \
  -n ai-platform --timeout=300s
```

## Negative Verification

Use a full, syntactically valid digest with no trusted attestation:

```bash
kubectl create deployment attestation-negative \
  -n ai-platform \
  --image='ghcr.io/anselem-okeke/ai-platform-api@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' \
  --dry-run=server \
  -o yaml
```

Expected failure includes a Sigstore denial similar to:

```text
no valid bundles exist in registry
```

This proves the cluster is not merely checking image naming syntax.

## GitHub-Side Verification

Artifact attestations can also be inspected with GitHub CLI where applicable. For example, verify chart provenance as documented upstream:

```bash
gh attestation verify --owner github \
  oci://ghcr.io/github/artifact-attestations-helm-charts/trust-policies:v0.7.0
```

For application images, verify against the repository/owner policy appropriate to the release artifact.

## Failure Scenarios

### `TrustRoot` or `ClusterImagePolicy` missing

```bash
kubectl get trustroot
kubectl get clusterimagepolicy
argocd app get trust-policies --refresh
```

### Policy exists but untrusted images are admitted

Check namespace labels first.

### Trusted image is denied

Check:

- the exact deployed digest
- release workflow produced attestations for that digest
- organization name is correct
- image pattern matches the fully qualified image
- Policy Controller is healthy

### Image pattern mismatch

The upstream chart requires fully-qualified image patterns. Keep the configured patterns aligned with GHCR names.

## Security Notes

Artifact attestations prove build identity/provenance according to policy. They do **not** prove an artifact is vulnerability-free or non-malicious. They must be combined with:

- source review
- required checks
- vulnerability scanning
- immutable digests
- GitOps promotion
- admission policy

## Recovery

To restore trust policy after loss:

1. restore Policy Controller first
2. ensure AppProject permissions
3. restore `trust-policies` Application from Git
4. synchronize root if topology must be recreated
5. wait for TrustRoot and ClusterImagePolicy
6. restore namespace labels through GitOps
7. run positive and negative admission tests

## Official References

- GitHub Kubernetes attestation enforcement: https://docs.github.com/actions/how-tos/secure-your-work/use-artifact-attestations/enforce-artifact-attestations
- GitHub artifact attestations concepts: https://docs.github.com/actions/concepts/security/artifact-attestations
- GitHub Artifact Attestations Helm charts: https://github.com/github/artifact-attestations-helm-charts
- Sigstore Policy Controller: https://docs.sigstore.dev/policy-controller/overview/

## Related Documentation

- [022-sbom-and-provenance.md](022-sbom-and-provenance.md)
- [031-sigstore-policy-controller.md](031-sigstore-policy-controller.md)
- [039-software-supply-chain-security.md](039-software-supply-chain-security.md)
