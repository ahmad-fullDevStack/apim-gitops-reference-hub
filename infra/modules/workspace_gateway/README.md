# `workspace_gateway` module

> **Reference source:** the "Workspace Consolidation Strategy" treats workspace
> gateways as the unit of capacity planning. A large domain may run ~10 active
> workspaces per service today, scaling up to 30 per gateway and 100 per service.

This module provisions one **workspace gateway** under an existing APIM
service. A workspace gateway is a dedicated gateway compute unit allocated
to a single workspace (or a small set of workspaces) for blast-radius
isolation and capacity scaling. The default ("built-in") gateway is shared
across all workspaces.

## Limitations carried over from the platform

- Workspace gateways do **not yet support user-assigned managed identities**
  attached at the workspace MI scope (PDF §"Identified Gaps and Mitigations").
  Until that lands, secret access for workspaced backends still flows through
  the service-level system-assigned MI.
- Premium-only.
- Counts against the per-service capacity ceiling.

## Inputs

| Name | Description |
|---|---|
| `apim_id` | Resource ID of the parent APIM service |
| `gateway_name` | Short name of the gateway resource (e.g. `gw-pensions-core`) |
| `workspace_id` | Workspace resource ID this gateway is bound to |
| `sku_capacity` | Number of gateway units (default 1) |
| `region` | Azure region (must match APIM service region for v1) |

## Cost

A workspace gateway adds **one Premium-v1 unit of cost** on top of the base
service (~€2500/month at westeurope list price as of 2024). Provision
sparingly; the platform team should review every new gateway request.
