<!-- regular-plan-v1 -->
# Feature evaluation fixes

## Goal
Fix the functional defects reproduced in the feature evaluation without adding
runtime dependencies or changing credentials, publishing, or merging branches.

## Scope
Cross-model validation, its request/response contracts, API-key usage reporting,
and benchmark quality reporting; include their callers, docs, and regression tests.
The user's repeated discovery/correction request also covers execution, free model
routing, and image transport defects reproduced through the public MCP tools.

## Current evaluation outcome (2026-10-06)
- Completed the local discovery/correction cycles and exercised all 19 registered
  tools through the real Node launcher → Python → MCP stdio path. The user supplied
  the key in the primary checkout's ignored `.env`; it was read for subprocess
  authentication, never printed, copied into the task tree, or changed by the agent.
- Real OpenRouter checks covered chat, streaming, catalogs, usage, consensus,
  ensemble, correct/incorrect cross validation, collaborative solving, free chat,
  vision, benchmark generation/history/CSV/JSON/Markdown export, category and
  weighted comparisons, and local deferred-batch artifacts. Batch export generated
  files only; no remote batch job was submitted. Actual model judgments are still
  not calibrated correctness measurements, and this is not an all-model quality
  benchmark or deployment acceptance.
- Current functional verification: `run_tests.py all -v` passed 2,179 tests, with
  10 real-API tests deselected; `run_tests.py assurance -v` passed 1,381 tests and
  Node security checks; branch-inclusive coverage is 80.28% (gate 70%). These suites
  simulate providers; the separate live MCP checks above exercise real providers.
- Full static gates remain red from existing debt: Ruff 1,302 findings versus
  1,356 on the unchanged primary; Black 29 untouched files; isort 5 untouched files.
  No additional Ruff findings remain, and changed Python files pass Black/isort.
  Runtime requirements and all 87 installed-package dependency checks passed.
- Remaining observed external limitations: Nano misidentified a 64×64 red image;
  direct-provider controls reproduce it (details below). One catalog-selected free
  provider returned HTTP 429; comparisons now expose that failure explicitly, and
  the successful category path was also verified with a different category.
- No commit, merge, push, release, or deployment was requested or performed. The
  primary `develop` checkout is clean. Keep the uncommitted task worktree/branch;
  merged-worktree cleanup does not apply.

## Approach
- Treat unavailable or unparseable validators as incomplete evidence. Require the
  configured minimum of successful validators before returning a valid result.
- Request and validate structured review scores/issues. Preserve custom criteria,
  generation parameters, and failure metadata through the complete call path.
- Use OpenRouter's authenticated GET /key for API-key spending totals. Reject
  unsupported arbitrary date ranges explicitly instead of returning unrelated data.
- Keep response-shape heuristics separate from evaluated answer quality. Without
  an evaluator, quality stays unknown and cannot justify a quality recommendation.

## Steps
1. Add failing regressions for the observed defects and realistic failure modes.
2. Implement validation evidence handling and propagate request parameters.
3. Correct usage reporting against the official API contract.
4. Preserve unknown benchmark quality through aggregation, ranking, and exports.
5. Run targeted tests, static gates, integration, assurance, and stdio smoke checks.

## Verification
- Reproduce all-provider failure, partial failure, Korean/unstructured rejection,
  malformed scores, custom criteria, token caps, and concurrent request isolation.
- Assert the exact HTTP endpoint and scope of usage data with a mocked transport.
- Assert that neither a short correct answer nor a repetitive wrong answer receives
  an invented correctness score; unknown quality remains unknown in public reports.
- Exercise real stdio transport and real providers when a locally configured key
  is available; mocked providers are not live acceptance.
- Security focus: fail closed on untrusted review output; do not leak credentials,
  loosen transport rules, or allow caller token limits to disappear.
- After any future deployment, monitor incomplete-validation rates and usage API
  failures; rollback consists of reverting this isolated change set.

## Initial implementation and verification outcome (2026-10-05)
- Implementation is complete in `.worktrees/fix-feature-evaluation`, branch
  `fix/feature-evaluation`. No commit, merge, publish, or credential changes.
- Peer review now validates structured scores and issues, honors caller criteria
  and generation limits, and exposes complete/degraded/incomplete evidence. Failed
  or incomplete reviews do not update validator performance history.
- Usage reporting uses GET /key with an allowlist of spending counters. Unsupported
  date ranges fail before HTTP; unavailable request/token counts remain null. Local
  savings are separately scoped and are not turned into a key-wide savings rate.
- Benchmark answer quality remains null without an evaluator. Unknown scores survive
  aggregation, report round trips, and exports. Unsupported quality comparisons fail
  before initializing billable work. Integration fixtures now implement the explicit
  reviewer protocol; these remain simulated providers, not live acceptance evidence.
- `.venv/bin/python run_tests.py all -v`: 2,020 passed; 10 real-API tests deselected.
- `.venv/bin/python run_tests.py assurance -v`: 1,222 passed; Node security tests
  passed; branch-inclusive coverage 78.47% (required 70%).
- Real Node launcher → Python → MCP stdio: 19 tools listed; unsupported usage date
  ranges and quality comparisons rejected through the real transport. The credential
  was a placeholder and the upstream URL deliberately offline; no live provider
  behavior was verified.
- Runtime dependency check passed using Python 3.14.2, FastMCP 3.2.4, MCP 1.30.0,
  and Node 24.14.0. No runtime dependencies or lockfiles changed.
- All changed Python files pass Black and isort. Full-repository static checks remain
  blocked by existing debt: the original checkout has 1,356 Ruff findings and 42
  Black formatting failures. Current checks have no newly introduced Ruff findings;
  unchanged files still fail full Black/isort checks. No broad formatting or lint
  cleanup was attempted.
- Live acceptance remains blocked by the missing OpenRouter API key. Model judgment
  scores are not calibrated correctness measurements. Historical report scores and
  non-peer-review heuristics were not redesigned in this change.

## Assurance timing regression
The first assurance run exposed an existing wall-clock timing defect in the consensus
engine: `processing_time` was -0.053244 seconds and violated the response schema.

- Loop: `.venv/bin/python -m pytest -q -o addopts='' -p no:cacheprovider
  tests/contracts/test_collective_contracts.py::test_collective_chat_duration_survives_clock_rollback`.
  A 50 ms clock rollback reproduced `assert -0.05 >= 0` before the fix and passes after it.
- Root cause: subtracting two `datetime.now()` readings to measure elapsed time.
  The consensus engine had no task changes when the failure was first observed.
- Ruled out: negative model timing propagation (a simulated model duration of -10
  seconds still gave +0.05 seconds with an advancing engine clock), and test-order
  or coverage leakage (the same failure reproduced in an isolated process).
- Fix: use `perf_counter()` for consensus elapsed time. Calendar timestamps remain
  unchanged. The affected tests, complete suite, and assurance gate pass after the fix.
- Residual risk: this was a focused consensus-duration correction, not an audit of
  every wall-clock use in the repository. No temporary instrumentation remains.

## Handoff
The primary `develop` checkout remains clean at
`5c59c45cb29baa97667b858915a02916a0e6efcb`. Development writes are confined to the
task worktree. Retain the worktree and branch because the changes are uncommitted
and unmerged; no cleanup is applicable yet. Future deployment should observe
incomplete-review rates, usage-endpoint errors, and consumers of newly nullable
quality/count fields. Rollback is limited to this isolated change set.

## Continued discovery and adjustment (2026-10-06, completed local audit)
The user requested repeated discovery and correction until nothing material remains
unaddressed. The earlier passing test counts are baseline evidence, not proof of
completion for this broader audit. The same task worktree remains active.

Confirmed findings from executable probes:
- [x] Empty responses still yield VALID/1.0 in adversarial, consensus-check,
  fact-check, and bias-detection strategies. Apply explicit evidence requirements
  throughout these strategies while preserving their distinct review purposes.
- [x] Opposing reviewer scores (0 versus 1) produce consensus 1.0. Agreement must
  reflect scores, not just equal issue counts.
- [x] Duplicate JSON score keys silently overwrite an earlier rejection.
- [x] Enhanced CSV exports replace measured latency, spending, throughput, and
  token counts with zeros.
- [x] Historical heuristic scores still select a highest-quality model. Reports
  need explicit evaluation provenance before treating stored numbers as quality.

Audit coverage (completed; historical checkpoints below are superseded above):
- [x] Request validation, model selection, self-validation, distinct reviewer counts,
  generation limits, malformed/truncated provider output, and concurrent requests.
- [x] Benchmark input validation, aggregation, serialization round trips, history
  filtering, missing metrics, and non-finite/negative values.
- [x] Usage response validation and the separation of local versus remote counters.
- [x] Shared elapsed-time measurements and required static gates (existing debt remains).
- [x] Repeat affected paths, full all/assurance, and actual stdio.
- [x] Live provider checks after the user confirmed local `.env` setup. Preserve the
  observed model/rate-limit limitations; no secret values were requested in chat.

Current iteration evidence and additional findings:
- All six review strategies now require strict scores/issues. Consensus generates
  independent answers followed by scored semantic review. The first widened run
  passed 317 collective tests; later edits still require fresh full verification.
- Eight failing persistence regressions were reproduced and corrected: measured CSV
  fields, JSON round trips, legacy score provenance, zero quality, malformed history,
  and filter-before-limit behavior. Quality provenance is caller-supplied, not a
  certificate of evaluator accuracy.
- Fourteen additional boundary failures were reproduced: self-review/availability
  bypass through specialized configuration, invalid quorum/timeout configuration,
  accepted truncated reviews, and invalid weights reaching billable setup.
- Twenty-six request/usage/pricing/timing failures were reproduced. Request bounds,
  distinct IDs/criteria, finite spending, catalog per-token cost, authoritative
  usage.cost, and monotonic elapsed clocks are corrected. A new zero-sample averaging
  regression also failed before adjustment. Current verification is in progress.
- Fresh official evidence: https://openrouter.ai/docs/guides/overview/models#pricing-object
  and https://openrouter.ai/docs/cookbook/administration/usage-accounting (2026-10-06).
- Remaining discovery target: collaborative solving still assigns fixed 0.8 quality
  in `_create_solving_result`; audit underlying solver/ensemble/consensus evidence
  and failure propagation before calling the broader feature audit finished.
- No live acceptance has run; API key setup status is still awaiting the user.

Further discovery cycle:
- Pre-solver-change full suite: 2,107 passed, 10 real-API tests deselected. It is not
  final-tip evidence for subsequent changes. The current targeted benchmark/boundary
  run passed 274 tests. Static gates still report existing repo-wide debt (Ruff
  1,310 at that checkpoint, Black 33 untouched files, isort 6 untouched files).
- Collaborative solving falsely returned a fixed 0.8 quality even after all parallel
  components failed, reviewed individual subtasks rather than assembled text, and
  always reported zero elapsed time. Five failing evidence regressions were fixed;
  the widened solver/contract slice passed 58 tests. Unknown final-answer quality is
  now nullable, backed by updated serialization and response schema.
- Empty/truncated model answers were treated as successful consensus and ensemble
  evidence. A shared completion guard now rejects them; incomplete independent
  references no longer trigger paid review. An inverted error-rate contribution
  that rewarded failures was corrected with a monotonicity regression.
- Consensus and ensemble ignored explicit model IDs and could call other models.
  Provider-call regressions reproduced both paths and now pass after filtering.
- Quota discovery reproduced phantom initial calls, reconciliation counted as an
  additional API attempt, and discarded quota-overage returns. Reservations occur
  per API attempt; observed usage is reconciled separately and retained on overage.
  Pending provider calls are cancelled, but already-dispatched calls may still cost
  money; local quota enforcement is not a provider-enforced hard spending limit.
- Quota/operational/consensus focused slice passed 61 tests before model-filter edits;
  cancellation/capacity recovery is separately exercised by a bounded event-driven
  test. Latest full all/assurance and stdio verification are still required.
- Continue auditing unfinished broader evidence (ensemble/consensus heuristic quality,
  zero/unknown provider accounting, input boundaries and deployment contracts) rather
  than claiming all features accepted from the simulated-provider suite.

Latest refinement evidence:
- The widened suite after solver changes had six failures. Five were obsolete mock
  contracts (immutable fake results, fixed 0.8 quality, empty response acceptance,
  and mocked quota reconciliation); the real regression was a two-model solver
  invoking the internal three-model default quorum. A request-local quorum bounded
  by the explicitly selected set fixes this without mutating the shared engine.
  The affected 41-test regression slice now passes, and concurrent request isolation
  is covered independently.
- Consensus/ensemble heuristic scores are now separated from measured answer quality
  at the MCP boundary. Built-in paths emit null quality and explicit provenance.
  The corresponding schema and serializer slice passed 25 tests.
- Additional red tests exposed basic-report export/reload losing the result entirely,
  ensemble totals reporting assignment estimates instead of observed result costs,
  and invalid token counters entering accounting. Those are corrected; the widened
  accounting/persistence/provider slice passed 98 tests.
- New quota-overage integration regression confirms pending provider cancellation
  and reacquisition of every model slot after failure. Four quota audit cases pass.
- All preceding full test numbers remain checkpoints, not final-tip acceptance.

## Live-driven corrections and diagnosis receipts

- Real `ensemble_reasoning(decompose=false)` executed three provider calls. The
  execution regression in `tests/test_feature_execution_audit.py` went red before
  the fix and now proves a single original task/response and `strategy_used=none`.
  Real MCP verification returned `4` from one subtask after the fix.
- Eleven execution/spending cases reproduced insufficient-quorum calls, lost zero
  catalog prices, guessed pricing units, and invalid comparison inputs. Quorum
  preflight, normalized per-token prices, and validation before handler construction
  correct these cases. Subsequent category probes reproduced invalid metrics being
  treated as zero and cost selection favoring an unmeasured quality score. Category
  preselection now uses valid measured values; cost orders catalog prompt prices.
- Live category benchmarking encountered `HTTP 429: Too Many Requests` and returned
  an unexplained empty result. Two failing wrapper regressions now prove preserved
  `benchmark_status=failed` and `failed_models`. The real MCP call reproduced that
  explicit status after correction; a reasoning-category run returned measured
  results successfully. Weighted comparison measured both selected models with
  null answer quality. One scratch verifier initially checked `quality_score`
  instead of `individual_scores.quality`; the captured real response was validated
  against the correct schema without another paid request.

Free-chat loop and diagnosis:
- Loop: `.venv/bin/python -B /tmp/openrouter_live_original_free.py`, matching the
  original Gemma preference and 128-token cap. Before adjustment, the broader real
  probe selected Lyria and returned whitespace while recording success. Afterward,
  the original request used the eligible Dots fallback, answered `4`, and reported
  `usage.cost=0`. A separate Liquid free-model call also answered `4` at zero cost.
- Root cause: non-positive/invalid/missing prices were classified as free; audio
  generators could enter text-chat fallback; empty responses were recorded as
  success. Cached free labels are now rechecked against explicit zero pricing and
  text-only output metadata. Empty text fails; a reported charge stops retries.
  Free request temperature/token bounds now match the other completion tools.
- Regression seam: `tests/test_free_live_findings.py` reproduced 19 failures
  including missing/dynamic/audio prices, invalid candidates, empty/charged
  responses, input bounds, and image MIME types. The widened free/media/metadata
  slice passed 346 tests. No provider responses were faked in the live checks.

Vision loop and diagnosis:
- Loop: the actual `chat_with_vision` tool with a synthetic solid red PNG and
  `temperature=0`, `max_tokens=32`. Nano answered `Blue` for 64×64. The source pixel
  was verified as `(255, 0, 0)` and the planner preserved the image content block.
- Probes ruled out adapter loss and MIME as the cause of that answer: adapter and
  direct HTTP requests, each with PNG and JPEG MIME labels, all produced `Blue` at
  64×64. Nano answered `Red` at 256×256; Gemini answered `Red` at 64×64, including
  real MCP follow-up calls. The fault is reproducible beyond this application's
  transport; the provider's internal reason is unknown.
- Independent format defect: every image was labeled JPEG. PNG/GIF/WebP regression
  cases went red and now pass with correct MIME labels and unchanged encoded data.
  Do not attribute the small-image model error to MIME or claim it was fixed.
- Scratch probes/logs stay outside Git. No diagnostic instrumentation remains in
  product code. Live-provider receipts are in `/tmp/openrouter-live-*-response.json`,
  `/tmp/openrouter-live-followup-results.json`,
  `/tmp/openrouter-live-original-free-results.json`, and
  `/tmp/openrouter-live-benchmark-modes-results.json` for this local session.

Security/deployment boundary: free-routing eligibility rejects unknown/dynamic costs,
reported charges are not presented as free success, review input/output is untrusted,
and credentials remain in the user's local environment. No dependency/lock changes
or deployment occurred. After any later deployment, observe incomplete validation,
provider failures, unexpected charges, and consumers of nullable quality fields.
Rollback is the isolated task change set; the primary has not received these edits.
