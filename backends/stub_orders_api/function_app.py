"""HTTP-triggered Azure Function returning a static list of orders.

Tiny on purpose: the customer demo focuses on the gateway and CI/CD path,
not on backend complexity.
"""

from __future__ import annotations

import json

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


_SAMPLE_ORDERS = [
    {"id": "ORD-1001", "customer": "Acme Pensions", "amount_eur": 12_500.00, "status": "settled"},
    {"id": "ORD-1002", "customer": "Beta Trust", "amount_eur": 5_400.00, "status": "pending"},
    {"id": "ORD-1003", "customer": "Gamma Co-op", "amount_eur": 320.55, "status": "rejected"},
]


@app.route(route="orders", methods=["GET"])
def list_orders(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps({"orders": _SAMPLE_ORDERS}),
        mimetype="application/json",
        status_code=200,
        headers={"x-source": "stub-orders-api"},
    )


@app.route(route="orders/{order_id}", methods=["GET"])
def get_order(req: func.HttpRequest) -> func.HttpResponse:
    order_id = req.route_params.get("order_id")
    match = next((o for o in _SAMPLE_ORDERS if o["id"] == order_id), None)
    if match is None:
        return func.HttpResponse(
            body=json.dumps({"error": "not found", "id": order_id}),
            mimetype="application/json",
            status_code=404,
        )
    return func.HttpResponse(
        body=json.dumps(match),
        mimetype="application/json",
        status_code=200,
    )
