# stub_orders_api

Minimal Python Azure Function HTTP trigger that returns a static list of orders.
Used by the demo as Team A's backend so the customer can see the gateway
returning a real response over `https://{apim}.azure-api.net/teama-orders-v1/orders`.

## Why this exists

The reference architecture shows team-scoped backends behind the gateway.
Without a real backend, the demo would have to fake the response with a mock
policy, which obscures the wire-level flow the customer wants to see.
This stub is the cheapest possible proof point.

## Deploy

```powershell
cd backends/stub_orders_api
func azure functionapp publish func-apim-poc-stub-orders --python
```

(The Function App itself is **not** provisioned by the Terraform in this
reference repo — keep it out of the IaC so the customer focuses on the APIM
and CI/CD parts. Create one ad-hoc in your demo subscription before the
session if you want a live backend.)

## Local run

```powershell
pip install -r requirements.txt
func start
```

Then `curl http://localhost:7071/api/orders`.

## Hosting cost

A Consumption-plan Python Function App costs ~€0 for demo-level traffic
(€0.20 per million invocations + €0.000016/GB-s).
