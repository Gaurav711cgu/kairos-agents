# Delivery provenance

Build007 remains a sealed historical software/evaluation release. Its original source archive, manifest, publication index and receipt are preserved byte-for-byte. Source changes for clearer website presentation, professional documentation and opt-in live reviewer execution are declared separately under `evidence/docs008`.

The new overlay includes:

- README, compact context and decision records; architectural, operating and visitor guides.
- Website copy and active-state presentation, with updated browser acceptance.
- Explicit reviewer inference startup, preflight, identity-bound reuse and failure cleanup, plus focused tests.
- Current browser, live execution, release acceptance and download receipts.

The API contracts, authorization, worker repair protocol, frozen cases, model profiles and original public captures remain unchanged. The local runtime startup helper has a declared cleanup change; an ownership-receipt failure now stops the model instead of leaving an untracked process. Existing study source freezes and failed results are retained; the locked evaluation is not rerun.

```bash
python3 -m scripts.verify_ci009
```

This current command checks the original008 archive and permitted CI009 correction fingerprints. Unexpected files or changes outside the declared delta fail verification. These local references establish byte consistency, not signing or administrator-proof provenance. The original `scripts.verify_showcase008` command applies to the unchanged008 archive after extraction. [CI correction and hosted acceptance](CI_009.md).

New acceptance and browser-submitted execution are separate from historical build007 evidence. The actual interactive Django development run passed four tests with two model calls; it is excluded from fresh validation totals. Credentials, browser authentication state and weights remain private and outside the publication.

For the original release, extract `evidence/build007/publication.tar.gz` into a new directory and run `python3 -m scripts.package_release007 --verify --source-only` from its `kairos` folder. The older source verifier applies to that unchanged snapshot.
