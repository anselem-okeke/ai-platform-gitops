# Software Supply-Chain Security

## Purpose

Provides the complete source-to-runtime defense-in-depth model.

## Chain
```text
required source checks
  -> hardened build
  -> Trivy
  -> SPDX SBOM + provenance/SBOM attestations
  -> GHCR immutable digest
  -> GitHub App GitOps PR
  -> Kustomize/kubeconform/digest validation
  -> human merge
  -> Argo reconciliation
  -> native registry/digest admission
  -> Sigstore trusted-artifact verification
  -> runtime monitoring
```

## Controls by Threat
| Threat | Primary control |
|---|---|
| broken source | required tests/lint |
| reachable Go CVE | govulncheck |
| static-analysis issue | CodeQL |
| committed credential | Gitleaks |
| vulnerable image | Trivy |
| mutable tag | digest-only GitOps |
| action tag hijack | full SHA pinning |
| unknown build origin | provenance attestation |
| unknown contents | SBOM |
| CI-to-cluster bypass | separate GitOps repo + PR |
| invalid manifest | Kustomize/kubeconform |
| unapproved registry | native admission |
| non-digest image | native admission |
| untrusted digest | Sigstore |
| direct Pod/init/ephemeral bypass | Pod admission policy |
| policy-controller outage | Prometheus alerting |
| manual drift | Argo self-heal |
| bad promotion | Git revert |

## Trust Boundaries
The source repository may produce candidate artifacts but cannot directly authorize deployment. The GitOps repository declares deployment intent but cannot bypass cluster admission. Kubernetes admission re-verifies the exact runtime image.

## Residual Risk
The system reduces risk; it does not prove vulnerability-free software. Compromised identities, zero-days, malicious dependencies, cluster compromise, and incorrect policy configuration remain possible and require ongoing monitoring, patching, review, and incident response.

## Official References
- https://slsa.dev/
- https://docs.github.com/actions/security-for-github-actions/using-artifact-attestations
- https://docs.sigstore.dev/
- https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/
- https://docs.github.com/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
- https://csrc.nist.gov/Projects/ssdf

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
