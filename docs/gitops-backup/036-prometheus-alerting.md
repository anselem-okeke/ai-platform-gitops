# Prometheus Alerting

## Purpose

Documents Policy Controller alert rules and the Prometheus rule selector requirement.

## Resource
`PrometheusRule/monitoring/policy-controller` at `platform/monitoring/base/policy-controller-prometheusrule.yaml`.

## Selector Requirement
Prometheus uses:
```yaml
ruleSelector:
  matchLabels:
    release: kps
```
Therefore the PrometheusRule requires:
```yaml
metadata:
  labels:
    release: kps
```

This was discovered when Argo reported the rule `Synced` but Prometheus `/api/v1/rules` did not load it. GitOps convergence does not prove downstream controller selection.

## Alerts
```text
PolicyControllerTargetDown
PolicyControllerReconcileFailures
PolicyControllerWebhookCertificateFailures
```

Reconcile failure alerts use `increase(...[10m])` rather than historical counter totals to avoid alerting forever on old startup failures.

## Official References
- https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/
- https://prometheus-operator.dev/docs/api-reference/api/
- https://prometheus.io/docs/prometheus/latest/querying/functions/#increase

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
