# Checkout Service SLOs

- p95 latency budget: 250ms
- Error rate budget: 0.5%
- Region: us-east-1 primary

## Incident #342 - 2026-06-28

Checkout latency spike to 420ms p95.
Root cause: Deploy v2.4.1 reduced DB connection pool from 25 to 10.
Fix: Revert pool_size to 25, add auto-scaling guardrail.

Runbook: checkout_latency_spike
1. Check Prometheus: checkout_latency_p95
2. Check recent deploys
3. Execute runbook_executor checkout_latency_spike
4. If confidence >0.8, open PR
