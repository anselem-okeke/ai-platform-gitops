# Monitoring GitOps

## Purpose

This document records how monitoring resources are managed in Git and reconciled by Argo CD, with special focus on Policy Controller observability.

## GitOps Path

```text
platform/monitoring/
├── base/
└── overlays/dev/
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

The development cluster uses kube-prometheus-stack.

Observed Prometheus version:

```text
v3.13.2-distroless
```

Observed Prometheus Pod:

```text
prometheus-kps-kube-prometheus-stack-prometheus-0
```

## GitOps-Managed Monitoring Resources

Important resources include:

```text
ConfigMap/monitoring/grafana-dashboard-ai-platform-api
ServiceMonitor/monitoring/policy-controller
PrometheusRule/monitoring/policy-controller
```

## Render

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/monitoring/overlays/dev \
  >/tmp/monitoring.yaml
```

## Validate

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/monitoring.yaml
```

## Argo

```bash
argocd app get \
  ai-platform-monitoring \
  --refresh
```

Expected:

```text
Synced
Healthy
```

## Policy Controller ServiceMonitor

Git file:

```text
platform/monitoring/base/policy-controller-servicemonitor.yaml
```

Resource:

```text
ServiceMonitor/monitoring/policy-controller
```

It selects the Policy Controller metrics service in:

```text
cosign-system
```

Service:

```text
policy-controller-webhook-metrics
```

Port:

```text
9090
```

Scrape interval:

```text
30s
```

Timeout:

```text
10s
```

## Prometheus ServiceMonitor Discovery

Validated Prometheus configuration:

```yaml
serviceMonitorNamespaceSelector: {}
serviceMonitorSelector: {}
```

This allows the ServiceMonitor to be discovered across namespaces without a special release label.

## PrometheusRule

Git file:

```text
platform/monitoring/base/policy-controller-prometheusrule.yaml
```

Resource:

```text
PrometheusRule/monitoring/policy-controller
```

Prometheus rule selector:

```yaml
ruleSelector:
  matchLabels:
    release: kps
```

Therefore the rule requires:

```yaml
metadata:
  labels:
    release: kps
```

## Important Operational Lesson

Initially:

```text
PrometheusRule existed
Argo = Synced
kubectl = resource present
Prometheus = rules absent
```

Root cause:

```text
metadata labels did not match Prometheus ruleSelector
```

Fix:

```yaml
release: kps
```

This proves that Argo convergence is not enough; always validate the downstream controller.

## Alerts

```text
PolicyControllerTargetDown
PolicyControllerReconcileFailures
PolicyControllerWebhookCertificateFailures
```

## Metrics

Validated metrics include:

```text
policy_controller_client_latency
policy_controller_client_results
policy_controller_reconcile_count
policy_controller_reconcile_latency
policy_controller_request_count
policy_controller_request_latencies
```

## Port-Forward Prometheus

```bash
kubectl port-forward \
  -n monitoring \
  svc/kps-kube-prometheus-stack-prometheus \
  19091:9090
```

If Service name differs:

```bash
kubectl get svc -n monitoring | grep prometheus
```

## Scrape Validation

```bash
curl -fsSG \
  'http://127.0.0.1:19091/api/v1/query' \
  --data-urlencode 'query=up{namespace="cosign-system"}'
```

Expected Policy Controller target:

```text
1
```

## Metric Validation

```bash
curl -fsSG \
  'http://127.0.0.1:19091/api/v1/query' \
  --data-urlencode 'query=policy_controller_reconcile_count'
```

Expected:

```text
non-empty vector
```

## Rule Validation

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

Prometheus API:

```bash
curl -fsS \
  'http://127.0.0.1:19091/api/v1/rules' \
  | grep -E \
  'PolicyControllerTargetDown|PolicyControllerReconcileFailures|PolicyControllerWebhookCertificateFailures'
```

## Troubleshooting

### ServiceMonitor exists but no target

Compare:

```bash
kubectl get servicemonitor \
  policy-controller \
  -n monitoring \
  -o yaml
```

with:

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system \
  --show-labels
```

Check port name matches.

### PrometheusRule exists but no rule

Inspect Prometheus selector:

```bash
kubectl get prometheus \
  -n monitoring \
  -o yaml \
  | grep -A15 -B3 -E \
    'ruleSelector|ruleNamespaceSelector'
```

Ensure `release=kps`.

## Official References

- Prometheus Operator: https://prometheus-operator.dev/
- Prometheus Operator API: https://prometheus-operator.dev/docs/api-reference/api/
- Prometheus query API: https://prometheus.io/docs/prometheus/latest/querying/api/
- Alerting rules: https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/
- Grafana: https://grafana.com/docs/grafana/latest/
