# Assessment Materials Manifest

Provenance of every file copied from the original Sezzle take-home package.

- Source: original package as received (flat directory, kept untouched outside this repo).
- Copied on: 2026-09-27. Content is byte-identical; only file names/locations changed to match the paths documented in `assessment/PROMPT.md` (`data/policies/`, `data/orders.json`, `cases/golden_visible.jsonl`).
- Missing from the package although referenced by PROMPT.md: `llm.py`, `data/mock_orders_api.py` (see `specs/assumptions.md`, A-01).
- Verify integrity from the repo root: `sha256sum -c assessment/SHA256SUMS`

| Original file name | Repository path | SHA-256 |
|---|---|---|
| `CASES_-_golden_visible.jsonl` | `cases/golden_visible.jsonl` | `aedd3b37fcf10893d70645cf604ffbd54bd1d706a4329c536d66cfa602999e5d` |
| `DATA-orders.json` | `data/orders.json` | `1f3306d51396133f19ac5b2e31fc7601369e63949fafa86e4b07ad8e2ec0e30c` |
| `POLICY_-02-rescheduling-payments.md` | `data/policies/02-rescheduling-payments.md` | `b3b39db54aa2416dba507e648406c31adab1159ae6fccffcb7057e31685912b6` |
| `POLICY_-03-failed-payments.md` | `data/policies/03-failed-payments.md` | `43865228fea445af6caffbba2c6186330830a8fa06181540e51775f9f7da5a6f` |
| `POLICY_-04-refunds-returns.md` | `data/policies/04-refunds-returns.md` | `b7c506a4dda81a23ead92c44249415a65776a1385a2e8525c3f4f88931c2c7e8` |
| `POLICY_-05-disputes.md` | `data/policies/05-disputes.md` | `bc0b744fb70d8b90ee9de32f780eaffd474b99c461bbfc5082a187c016befed2` |
| `POLICY_-06-account-reactivation.md` | `data/policies/06-account-reactivation.md` | `460a0b7feeff868a934d41ab4dd2c7f0e8dce33c0ecb5010cd240ddf29e43121` |
| `POLICY_-07-sezzle-up-credit-reporting.md` | `data/policies/07-sezzle-up-credit-reporting.md` | `d21c266d955dfb20df7fd5451f994ea8869124fa1c7c25f005029758d4c28928` |
| `POLICY_-08-virtual-card.md` | `data/policies/08-virtual-card.md` | `af15e20ccf9251ddaa089f05c8d90af04bfb6d26eb178eaaf2d28728450e751f` |
| `POLICY_-09-hardship-assistance.md` | `data/policies/09-hardship-assistance.md` | `46c43af5b432f0eeb522a049fa0abf969d9b71fb40efc06933324e6df8556062` |
| `POLICY_-10-fees-overview.md` | `data/policies/10-fees-overview.md` | `42fcb264aa9a53778054592f6ae9d47967654aa9bc5f1f2dbd1a3aff57ed023f` |
| `POLICY_-11-account-security-fraud.md` | `data/policies/11-account-security-fraud.md` | `36759d43d85a26b343c07abc1152c23eb8de63fd8e55f01a7e10683d691678b3` |
| `POLICY_-12-supported-merchants-limits.md` | `data/policies/12-supported-merchants-limits.md` | `7573a25d5fbb18eb6fab35e8bb51c4b36f0bea36fed928a75561fc9629bf2e7e` |
| `POLICY_-_01-payment-schedules.md` | `data/policies/01-payment-schedules.md` | `381a931001e1e5d16f8f3d99eb1331721d85d44d09babeb43bc9dd647514bcf1` |
| `PROMPT.md` | `assessment/PROMPT.md` | `f69613c03d8fff76c9f258abbdfb2017477daf954c6a0264844617f2d4b29cd4` |
| `SUBMISSION.md` | `assessment/SUBMISSION.md` | `329a7f1a18ad3d3cca0c42ae45cf32549bef03884cb054564926c883e7b2c5de` |
