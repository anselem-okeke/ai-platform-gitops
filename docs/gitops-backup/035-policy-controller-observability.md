# Policy Controller Observability

## Purpose

Documents Prometheus scraping of Policy Controller metrics.

## Metrics Service
Namespace: `cosign-system`
Service: `policy-controller-webhook-metrics`
Port: `9090`

GitOps ServiceMonitor: `platform/monitoring/base/policy-controller-servicemonitor.yaml`

Prometheus uses `serviceMonitorNamespaceSelector: {}` and `serviceMonitorSelector: {}`, so the ServiceMonitor is discoverable across namespaces.

Validated metrics include:
```text
policy_controller_client_latency
policy_controller_client_results
policy_controller_reconcile_count
policy_controller_reconcile_latency
policy_controller_request_count
policy_controller_request_latencies
```

`up{namespace="cosign-system"}` returned `1`, proving actual scraping. `policy_controller_reconcile_count` returned live series with `reconciler`, `success`, and `namespace_name` labels.

## Official References
- https://docs.sigstore.dev/policy-controller/overview/
- https://prometheus-operator.dev/docs/getting-started/introduction/
- https://prometheus.io/docs/prometheus/latest/querying/basics/

## Documentation Note

Commands, versions, resource names, and behavior in this document reflect the implemented AI Platform development environment. Re-validate version-specific upstream behavior before applying the same procedure to a later release or production environment.
