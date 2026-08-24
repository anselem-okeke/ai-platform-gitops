# Phase 7 Completion Checklist

## Purpose

This document records the evidence-backed completion state for Phase 7: GitOps and Delivery.

A checkbox should only be marked complete when the implementation and validation evidence exist.

# GitOps Architecture

- [x] GitOps architecture defined
- [x] Separate GitOps repository created
- [x] GitOps repository structure defined
- [x] Base and overlay strategy defined
- [x] Development environment configured
- [x] Git is the desired-state authority for managed platform resources

# Argo CD

- [x] Argo CD installed
- [x] Argo CD access secured
- [x] Argo CD CLI available
- [x] AppProject created
- [x] Root Application created
- [x] Child Applications created
- [x] Root topology is manually synchronized
- [x] Child Applications auto-sync where appropriate
- [x] Self-heal enabled where appropriate
- [x] Prune configured where appropriate
- [x] Argo health/sync validated
- [x] Drift self-heal validated

# Platform Desired State

- [x] Operator GitOps deployment
- [x] API GitOps deployment
- [x] ModelService GitOps structure
- [x] Gateway/routing GitOps deployment
- [x] Monitoring GitOps deployment
- [x] Namespace GitOps management
- [x] Admission policy GitOps management

# CI / Build

- [x] Lint
- [x] Unit tests
- [x] E2E tests
- [x] go vet
- [x] govulncheck gate
- [x] CodeQL
- [x] Gitleaks
- [x] Hardened Docker builds
- [x] Distroless runtime
- [x] Non-root runtime
- [x] Trivy scanning
- [x] SBOM generation
- [x] Provenance attestation
- [x] SBOM attestation

# Artifact Delivery

- [x] GHCR integrated
- [x] Operator image published
- [x] API image published
- [x] Immutable digests used
- [x] GitHub App automation used
- [x] GitOps digest PR created automatically
- [x] GitOps PR remains human-merged
- [x] Source release waits on both image jobs before GitOps update

# GitOps Validation

- [x] Kustomize rendering
- [x] kubeconform validation
- [x] approved registry check
- [x] full SHA-256 digest check
- [x] final mutable-tag rejection
- [x] secret-pattern check
- [x] `git diff --check`
- [x] required GitOps validation check

# Repository Protection

- [x] Protected source `main`
- [x] Required source checks
- [x] Non-fast-forward protection
- [x] Branch deletion protection
- [x] No bypass actors
- [x] GitOps pull-request workflow established
- [x] CODEOWNERS/ruleset strategy established

# Supply-Chain Admission

- [x] Native image registry policy
- [x] Native digest policy
- [x] Direct Pod protection
- [x] Init container protection
- [x] Ephemeral container protection
- [x] Sigstore Policy Controller installed
- [x] Policy Controller GitOps-managed
- [x] GitHub trust policy GitOps-managed
- [x] `TrustRoot/github`
- [x] `ClusterImagePolicy/github-policy`
- [x] protected namespaces labeled for Sigstore
- [x] trusted image positive test
- [x] public image negative test
- [x] fake digest negative test
- [x] expected Sigstore denial validated

# Monitoring

- [x] Policy Controller metrics exposed
- [x] ServiceMonitor GitOps-managed
- [x] Prometheus target confirmed `up == 1`
- [x] Policy Controller metrics queryable
- [x] PrometheusRule GitOps-managed
- [x] `release=kps` selector corrected
- [x] Policy Controller alert definitions added

# Secrets

- [x] secret-management strategy defined
- [x] plaintext secrets prohibited from Git
- [x] `.gitignore` hardened
- [x] Gitleaks CI
- [x] repository history scans reviewed
- [x] sensitive local files kept under ignored paths
- [x] Vault established as secret/PKI foundation

# Promotion and Rollback

- [x] build-once/promote-same-digest model defined
- [x] development promotion path implemented
- [x] Git-based rollback strategy defined
- [x] rollback behavior validated
- [x] future staging/production model documented

# Documentation

- [x] documentation index defined
- [x] platform overview documented
- [x] architecture documented
- [x] repository architecture documented
- [x] cluster/environment documented
- [x] GitOps/Argo documented
- [x] CI/build/supply-chain documented
- [x] admission/security documented
- [x] observability documented
- [x] secrets documented
- [x] end-to-end delivery documented
- [x] validation tests documented
- [x] disaster recovery/rebuild documented
- [x] troubleshooting documented
- [x] operations runbook documented
- [x] command reference documented
- [x] security model documented
- [x] design decisions documented
- [x] known limitations documented
- [x] future environment promotion documented
- [ ] final README.md completed
- [ ] final documentation hardening/cross-link review completed

# Explicit Limitations

The following are **not** claimed as fully production-validated:

- full persistent-volume disaster recovery
- production Kubernetes topology
- staging/production environments
- production Keycloak HA/DR
- production Vault DR exercise
- destructive whole-resource prune test
- production Alertmanager routing
- production multi-reviewer governance

# Final Phase 7 Exit Criteria

Phase 7 can be declared complete when:

```text
1. final README.md exists
2. documentation hardening review 000-050 is complete
3. links are valid
4. commands are internally consistent
5. implementation paths match repository state
6. known limitations remain explicit
7. repositories are clean and scans pass
```

# Official References

- Argo CD: https://argo-cd.readthedocs.io/en/stable/
- Kubernetes: https://kubernetes.io/docs/
- GitHub Actions: https://docs.github.com/actions
- Sigstore: https://docs.sigstore.dev/
- Prometheus: https://prometheus.io/docs/
