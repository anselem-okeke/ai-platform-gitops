# Sigstore Policy Controller

## Purpose

Documents Policy Controller installation, ownership, drift handling, and verification.

## Deployment
Namespace: `cosign-system`

Helm chart: `policy-controller 0.10.6`
Application version: `0.13.1`

Argo child: `clusters/dev/apps/policy-controller.yaml`
OCI source: `ghcr.io/sigstore/helm-charts`

## Enforcement
Namespaces `ai-platform` and `ai-platform-operator-system` are labeled `policy.sigstore.dev/include=true`. Native admission validates registry/digest shape; Policy Controller verifies trusted artifact evidence.

## CRD Ownership Conflict
An attempted second Helm installation failed because `clusterimagepolicies.policy.sigstore.dev` was already owned by the release in `cosign-system`. The platform standardized ownership there rather than forcing CRD adoption.

## Metrics
Service: `policy-controller-webhook-metrics`, port `9090`.

## Verification
```bash
kubectl get pods -n cosign-system
argocd app get policy-controller --refresh
```

## Official References
- https://docs.sigstore.dev/policy-controller/overview/
- https://github.com/sigstore/policy-controller
- https://helm.sh/docs/chart_best_practices/custom_resource_definitions/

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
