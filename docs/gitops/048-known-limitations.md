# Known Limitations

## Purpose

This document records what the current Phase 7 implementation does **not** prove or does not yet provide.

# 1. Development Environment Only

The implemented environment is:

```text
dev
```

There is no completed staging or production environment yet.

# 2. kind Is Not a Production Cluster

Current cluster:

```text
ai-platform-policy
```

using kind.

Production should use a supported production Kubernetes platform and repeat all compatibility/security validation.

# 3. `.local` Domains Are Development-Specific

Examples:

```text
auth.ai-platform.local
argocd.ai-platform.local
api.ai-platform.local
```

Production DNS/TLS must use production-managed names and certificates.

# 4. Persistent Data Recovery Is Not Fully Validated

GitOps can rebuild declarative resources.

It cannot recreate data lost from PVCs without a separate backup.

A full persistent-volume backup/restore test remains outside the validated scope.

# 5. Whole-Resource Prune Test Is Not Claimed

Child Applications are configured with prune.

Drift/self-heal behavior was validated.

A deliberate destructive whole-resource prune test is not claimed as empirically validated unless separately recorded.

# 6. Multi-Environment Promotion Is Designed, Not Implemented

The intended model is:

```text
dev -> staging -> prod
```

using the same digest.

Only dev exists today.

# 7. External Identity HA/DR Is Not Fully Documented

Keycloak integration works, but a complete production-grade Keycloak HA/backup/restore design is outside this phase.

# 8. Vault Production DR Is Not Fully Validated

Vault is the secret/PKI foundation, but this Phase 7 documentation does not claim a fully tested Vault disaster recovery exercise.

# 9. Prometheus Alert Delivery Is Not Fully Covered

Rules exist.

This documentation does not claim Alertmanager routing to email, PagerDuty, Slack, etc. unless separately implemented.

# 10. Policy Denial Audit UX Is Basic

Metrics and alerts exist, but there is not yet a dedicated rich dashboard for every admission denial reason.

# 11. Single-Maintainer Review Constraint

The source repository currently allows zero required approving reviews because the repository is solo-maintained.

A team/production repository should use independent approvals.

# 12. Security Tools Do Not Guarantee Vulnerability-Free Software

`govulncheck`, Trivy, CodeQL, and Gitleaks reduce risk.

They do not eliminate:

- zero-days
- malicious dependencies
- novel secrets
- logic vulnerabilities
- compromised trusted accounts

# 13. Current Version Pins Age

Examples:

```text
Argo CD v3.5.1
Policy Controller chart 0.10.6
Policy Controller app 0.13.1
Keycloak 26.7.0
Go 1.26.6
```

These are reproducibility pins, not permanent recommendations.

Before upgrading, read upstream release notes and rerun validation.

# 14. AppProject Is Manual Bootstrap State

This is intentional but means Git merge alone does not update live AppProject permissions.

Operators must remember the explicit apply step.

# 15. Development Networking Uses Private Addresses

Observed values such as:

```text
172.19.255.200
172.19.0.3:6443
10.96.0.10
```

are environment-specific and must not be assumed elsewhere.

# Official References

- Kubernetes production environment: https://kubernetes.io/docs/setup/production-environment/
- Argo CD releases: https://github.com/argoproj/argo-cd/releases
- Sigstore releases: https://github.com/sigstore/policy-controller/releases
