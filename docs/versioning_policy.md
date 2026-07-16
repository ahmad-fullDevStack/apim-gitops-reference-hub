# API Versioning Policy

> **Source.** This document operationalises the reference architecture
> (Workspace Consolidation, API Governance & Deduplication Strategy),
> specifically the sections on *API Governance and Standards → Versioning
> Policy* and *Deduplication Strategy → Canonical APIs and Version Sets*.

## Principles

1. **A single canonical API per business capability.** Duplicates do not get
   their own version line; they get merged into the canonical API and
   redirected. Discovery happens via
   [`.github/scripts/inventory.py`](../.github/scripts/inventory.py) (report
   uploaded by `extractor-drift.yml`).
2. **Breaking changes always create a new version.** The previous version
   continues to serve traffic for the support window of its tier (below).
3. **Non-breaking changes ship in place.** Additive fields, new optional
   query parameters, new endpoints — these go into the current version with
   a minor bump in `info.version` only.
4. **Header-based version routing.** APIM version sets are configured with
   `versioningScheme: "Header"` and `versionHeaderName: "Api-Version"`. URL
   paths stay clean (`/orders` not `/v1/orders`), which keeps developer
   portal documentation stable when versions roll forward.

## What counts as a breaking change

- Removing or renaming a response field.
- Changing the type or shape of an existing request/response field.
- Removing or renaming an endpoint.
- Tightening a previously-optional request field to required.
- Adding a new required request field without a default.
- Changing the meaning of an enum value already in use.
- Changing authentication / authorization requirements.

Anything not in this list is non-breaking. When in doubt, treat as breaking.

## Support windows per tier

The tier is set in `workspace.json` (`"tier": "gold|silver|bronze"`) and
validated by [`.github/scripts/tier_check.py`](../.github/scripts/tier_check.py).

| Tier | Min support window after a new major version | Notes |
|---|---|---|
| **Gold** | 12 months | SLA-bearing. Both N and N-1 must stay green during the window. |
| **Silver** | 6 months | Best-effort. Breaking changes need 30-day prior notice in the developer portal. |
| **Bronze** | None | Experiments. `active=true` is rejected by CI (see `tier_check.py`). |

Deprecation dates live in the OpenAPI spec as:

```yaml
info:
  version: "1.0.0"
  x-deprecated: true                # or 'deprecated: true' at operation level
  x-deprecation-date: "2025-12-31"  # ISO date, parsed by versioning.py
```

The [`.github/scripts/versioning.py`](../.github/scripts/versioning.py) check
fails the PR if `deprecated:true` is set without a parseable
`x-deprecation-date`.

## How to add a new major version

1. Copy the existing API folder, e.g.
   `apim-config/workspaces/pensions-core/shared/apis/contoso-orders-canonical-v1/`
   to `contoso-orders-canonical-v2/`.
2. Bump `info.version` in the spec and apply the breaking changes.
3. Add the new API to the existing version set
   (`shared/version-sets/contoso-orders.json`); do not create a parallel
   version set.
4. Update any **internal** product (`shared/products/...`) that should
   expose v2 — typically all internal products. **External / partner**
   products usually stay on v1 until the deprecation window is reached.
5. Mark v1 deprecated:
   ```yaml
   info:
     version: "1.0.0"
     x-deprecated: true
     x-deprecation-date: "2026-06-30"  # = today + tier support window
   ```
6. Update the developer portal release notes (out-of-band; not in this repo).
7. Open the PR. CODEOWNERS routes the version-set + canonical-API changes
   through the domain leads team.

## How to retire a deprecated version

1. Confirm with the metric for "Requests by Api Version" that traffic on the
   old version is under the retirement threshold (gold: 0 prod traffic for 7
   consecutive days; silver: under 1% of total for 7 days).
2. Delete the API folder for the old version.
3. Remove it from every product `apis[]` list.
4. The publisher workflow will remove the API from APIM on next apply.
5. Keep the **version-set** alive — it still anchors the surviving versions.

## Why no URL versioning

This policy prefers header-based routing because:

- The published URL never changes across versions, so external docs / OpenAPI
  contracts stay stable.
- Clients can opt into a specific version by adding one header, without
  routing rewrites.
- Default-version fallback (`Api-Version` absent → latest stable) is built
  into APIM version sets and gives a soft on-ramp for partners.

We will revisit URL versioning only if a regulator requires it for a specific
external API; in that case it would be set on that single version set, not
platform-wide.

## Quick reference: scripts that enforce this policy

| Concern | Script | Failure mode |
|---|---|---|
| Tier valid + bronze not active | [`.github/scripts/tier_check.py`](../.github/scripts/tier_check.py) | PR check fails |
| Workspace listed in `domains` | [`.github/scripts/freeze_workspace.py`](../.github/scripts/freeze_workspace.py) | PR check fails |
| Version present + deprecation date parseable | [`.github/scripts/versioning.py`](../.github/scripts/versioning.py) | PR check fails |
| Duplicate backends / policies | [`.github/scripts/inventory.py`](../.github/scripts/inventory.py) | Report-only, uploaded as artifact |
