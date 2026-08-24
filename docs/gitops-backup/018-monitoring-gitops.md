# Monitoring GitOps

## Purpose

This document records how AI Platform monitoring integrations are represented in Git and reconciled through Argo CD.

## GitOps Path

```text
platform/monitoring/
├── base/
└── overlays/
    └── dev/
```

Argo Application:

```text
ai-platform-monitoring
```

Namespace:

```text
monitoring
```

## Monitoring Stack

The environment uses kube-prometheus-stack.

Observed Prometheus version:

```text
v3.13.2-distroless
```

Prometheus instance:

```text
kps-kube-prometheus-stack-prometheus
```

Observed Pod:

```text
prometheus-kps-kube-prometheus-stack-prometheus-0
```

## Existing GitOps-Managed Monitoring Resources

Important resources include:

```text
ConfigMap/monitoring/grafana-dashboard-ai-platform-api
ServiceMonitor/monitoring/policy-controller
PrometheusRule/monitoring/policy-controller
```

## Policy Controller ServiceMonitor

Git file:

```text
platform/monitoring/base/policy-controller-servicemonitor.yaml
```

Key configuration:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: policy-controller
  namespace: monitoring
spec:
  namespaceSelector:
    matchNames:
      - cosign-system
  selector:
    matchLabels:
      app.kubernetes.io/instance: policy-controller
      app.kubernetes.io/name: policy-controller
      control-plane: policy-controller-webhook
  endpoints:
    - port: metrics
      interval: 30s
      scrapeTimeout: 10s
```

The ServiceMonitor selects:

```text
cosign-system/policy-controller-webhook-metrics
```

Port:

```text
metrics / 9090
```

## Prometheus ServiceMonitor Discovery

The Prometheus configuration includes:

```yaml
serviceMonitorNamespaceSelector: {}
serviceMonitorSelector: {}
```

This allows ServiceMonitors across namespaces without requiring a matching release label.

## Policy Controller Metrics

Validated metrics include:

```text
policy_controller_client_latency
policy_controller_client_results
policy_controller_reconcile_count
policy_controller_reconcile_latency
policy_controller_request_count
policy_controller_request_latencies
```

Important reconcile labels:

```text
namespace_name
reconciler
success
```

Example query:

```promql
policy_controller_reconcile_count
```

## Scrape Validation

A direct Prometheus query was validated:

```promql
up{namespace="cosign-system"}
```

and returned:

```text
1
```

for:

```text
service="policy-controller-webhook-metrics"
```

This proves that Prometheus is scraping the Policy Controller target.

## PrometheusRule

Git file:

```text
platform/monitoring/base/policy-controller-prometheusrule.yaml
```

Prometheus rule discovery required:

```yaml
metadata:
  labels:
    release: kps
```

because the Prometheus custom resource uses:

```yaml
ruleSelector:
  matchLabels:
    release: kps
```

This was an important operational lesson: a `PrometheusRule` can exist and be `Synced` in Argo CD but still not be selected by Prometheus if its labels do not match `ruleSelector`.

## Policy Alerts

The rule set includes:

```text
PolicyControllerTargetDown
PolicyControllerReconcileFailures
PolicyControllerWebhookCertificateFailures
```

The intent is to detect:

- metrics target unavailable
- sustained/repeated reconciliation failures
- webhook certificate reconciliation failures

## Validation

Argo:

```bash
argocd app get ai-platform-monitoring --refresh
```

Kubernetes:

```bash
kubectl get servicemonitor,prometheusrule \
  -n monitoring
```

Labels:

```bash
kubectl get prometheusrule \
  policy-controller \
  -n monitoring \
  --show-labels
```

Expected:

```text
release=kps
```

Prometheus target:

```bash
curl -fsSG \
  'http://127.0.0.1:19091/api/v1/query' \
  --data-urlencode 'query=up{namespace="cosign-system"}'
```

Rule API:

```bash
curl -fsS \
  'http://127.0.0.1:19091/api/v1/rules' \
  | grep -E \
  'PolicyControllerTargetDown|PolicyControllerReconcileFailures|PolicyControllerWebhookCertificateFailures'
```

## GitOps Workflow

Monitoring changes follow:

```text
feature branch
  |
  v
GitOps PR
  |
  v
Validate GitOps
  |
  v
merge main
  |
  v
ai-platform-monitoring auto-sync
  |
  v
Prometheus discovers configuration
```

No root sync is needed for changes inside the already-existing `platform/monitoring/overlays/dev` source path.

A root sync is needed only when changing the child Application topology itself.

## Troubleshooting

### ServiceMonitor exists but target absent

Check:

- selector labels
- namespace selector
- service port name
- Prometheus ServiceMonitor selectors
- endpoint health

### PrometheusRule exists but rule missing

Check:

```bash
kubectl get prometheus -n monitoring -o yaml \
  | grep -A10 -E 'ruleSelector|ruleNamespaceSelector'
```

Then compare with:

```bash
kubectl get prometheusrule \
  policy-controller \
  -n monitoring \
  --show-labels
```

The implemented fix was:

```yaml
release: kps
```

### Argo says Synced but Prometheus behavior is absent

Remember that Argo validates Kubernetes desired-state convergence. It does not prove that another controller selected the resource.

Always validate the downstream consumer.

## Official References

- Prometheus Operator getting started: https://prometheus-operator.dev/docs/getting-started/introduction/
- Prometheus Operator API reference: https://prometheus-operator.dev/docs/api-reference/api/
- ServiceMonitor concept: https://prometheus-operator.dev/docs/developer/getting-started/
- Prometheus querying: https://prometheus.io/docs/prometheus/latest/querying/basics/
- Prometheus alerting rules: https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/
- Grafana documentation: https://grafana.com/docs/grafana/latest/

## Related Documentation

- [035-policy-controller-observability.md](035-policy-controller-observability.md)
- [036-prometheus-alerting.md](036-prometheus-alerting.md)
- [031-sigstore-policy-controller.md](031-sigstore-policy-controller.md)
