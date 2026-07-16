# pensions-core / shared

Domain-shared canonical assets. Owned by the **`pensions-core-leads`** group per
`.github/CODEOWNERS`. The naming-convention check requires resources here to
use the `contoso-` prefix (see `config/ci.json` → `pensions-core-shared`).

This folder operationalises the reference architecture section
*API Deduplication Strategy → Canonical API + Versions + Products*:

- **`apis/contoso-orders-canonical/`** — one canonical API per backend, with a
  version set (`v1`, `v2`). Replaces what would otherwise be `teama-orders-v1`,
  `teamb-orders-v1`, `teamc-orders-v1` duplicates.
- **`backends/contoso-orders-canonical.json`** — one shared backend.
- **`version-sets/contoso-orders.json`** — header-based version set grouping
  `v1` and `v2` so consumers migrate at their own pace.
- **`products/contoso-pensions-internal.json`** /
  **`products/contoso-pensions-partner.json`** — per-consumer products with
  their own rate limits and access rules (reference architecture:
  *Consumer Separation via Products & Subscriptions*).
