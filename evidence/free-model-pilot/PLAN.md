# Separate free API development pilot

This pilot is optional and separate from the frozen build007 study. The user authorized one free external request containing public issue text and original public source excerpts. This authorization does not permit paid inference, quota upgrades, hidden verification material, private source, credentials or a rerun of locked evaluation cases.

## Entry point

The active checkout provides `python3 -m scripts.free_model_pilot doctor|prepare|run`. Python 3.12 and the existing locked backend environment provide its dependencies. This command starts no Docker container, database, inference server or website.

The private key file is `.runtime/free-model-pilot/environment.env`, with mode `0600`, containing only `GEMINI_API_KEY=...`. Do not put the key into a command argument, source file, screenshot, published receipt or chat. The command reads only the explicitly selected file; it does not discover credentials or inherit a key from the shell.

Before execution, use a free-tier Google AI Studio project without linked billing. The CLI requires `--free-tier-confirmed`. This records the operator's confirmation; the REST API does not attest billing state. Account quotas and availability may prevent the call. The command never retries a quota rejection or uncertain dispatch and never changes the model automatically.

```sh
python3 -m scripts.free_model_pilot doctor \
  --case django__django-11066 \
  --environment-file .runtime/free-model-pilot/environment.env

python3 -m scripts.free_model_pilot prepare --case django__django-11066

# Run only after doctor, offline tests and free-tier confirmation pass.
python3 -m scripts.free_model_pilot run \
  --case django__django-11066 \
  --environment-file .runtime/free-model-pilot/environment.env \
  --free-tier-confirmed
```

The default runtime permits one dispatch across the entire pilot, not one per case. A repeated command returns the captured outcome or an explicit unknown dispatch. Changing the runtime to evade that limit would require a separately authorized experiment.

## Input and output boundaries

Input is reconstructed from independently pinned published build007 development records. Only the first original-source selection contributes content. The outbound projection contains the public issue URL/text/title, source revision, numbered original Python excerpts, their captured handles and a one-call budget. It excludes prior model responses, candidate patches, verifier output, reference repairs, hidden tests, local runtime profiles and absolute machine paths. The three allowlisted previously exposed development cases are Django11066, pytest6197 and Requests2931. No build007 validation identifier is accepted.

The configured endpoint is the fixed Google `generateContent` REST endpoint for `gemini-3.8-flash`. The request supplies a JSON schema, 1,024 maximum output tokens, one candidate, temperature 1 and low thinking. These provider settings differ from the local sampling profile and are recorded explicitly. There are no provider tools or grounding requests. Redirects, inherited proxies and transport retries are disabled.

The request and its manifest are fsynced before the dispatch claim is committed to disk. The claim is created exclusively, preventing concurrent or repeated sends. A response is captured before parsing. A crash after complete response capture resumes local parsing; a claim without a complete capture remains unknown. The response limit is 512 KiB and the HTTP timeout is 60 seconds. Runtime files remain private and ignored.

The pilot validates action shape, permitted source handles, inclusive range bounds and overlaps. It does not execute a patch. `structurally_valid_not_verified` is never a repair success. Independent sandbox checks must be performed separately using the captured model proposal, not a reference patch. No model-quality result exists until an actual dispatch and separate verifier receipt have been recorded.

Raw provider responses may contain provider data and are not automatically published. Public summaries must be reviewed separately. Request fingerprints and captured provider `modelVersion` describe provenance; they do not attest remote weight bytes or provider-side reproducibility.

## Offline acceptance

`python3 -m pytest -q tests/test_free_model_pilot.py` checks public-only projections, rejected validation identifiers, pinned-capture corruption, private-file handling, read-only doctor behavior, immutable preparation, durable claims, concurrent calls, captured-response recovery, quota rejection, network uncertainty, invalid proposals and bounded HTTP output. The transport tests use an offline mock; they make no external call.

## Official API references checked on 2026-10-13

- [Model endpoint](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash)
- [REST generation and response format](https://ai.google.dev/api/generate-content)
- [Structured output schema](https://ai.google.dev/gemini-api/docs/structured-output)
- [Free-tier pricing and data use](https://ai.google.dev/gemini-api/docs/pricing)
- [Account-specific quota limits](https://ai.google.dev/gemini-api/docs/rate-limits)

Free-tier input/output is listed as free of charge. Google states free-tier content may be used to improve products. Actual quotas vary; the local command cannot establish provider availability or paid-tier eligibility.


## Adapter correction v2

The first provider request returned HTTP 400 INVALID_ARGUMENT because Gemini 3.8 Flash rejects MINIMAL thinking. No model proposal was generated. Its private v1 request and response bytes remain preserved. Official model documentation supports LOW, MEDIUM and HIGH. V2 uses LOW and a separate `.runtime/free-model-pilot-v2` dispatch ledger, while reading the original explicit private key file. This is one bounded corrected request after a known pre-inference rejection, not a retry of an uncertain dispatch or a change to frozen study007.
