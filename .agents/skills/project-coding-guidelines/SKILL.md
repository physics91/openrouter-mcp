---
name: project-coding-guidelines
description: "Project-local coding guidance generated from repository evidence. Use when writing, changing, or reviewing code in this repository to preserve module boundaries, reuse existing design, run project-native verification, and gate performance complexity on measurements."
---

<!-- clean-code:managed:start -->
<!-- clean-code:sync format=3 evidence=8cc3c4cf2786757641f19ab1f2658f419d37e2ac3ebc2769a9d957c924d27fd0 manual=23e45c0fb4b9dd7a3c82af5a99977f46ee4908b77a8a2ca1f7a4a2045211814e ledger=b0d985c3e83633c968d73b6730e4606e77c2f85c02244e969dc9f969e2dde0fe managed=7d4af75dc5a6dd8ea3290fcdc414757f4555a83712ef30526cbba0805d6c50b5 -->
# Project Coding Guidelines

Use these rules with the controlling repository instructions. Active instructions and current repository evidence win every conflict.

## Applicability Map

| Path | Stack | Evidence |
|---|---|---|
| `.` | Node.js, Python | `@source-stack:Python`, `package.json`, `requirements-dev.txt`, `requirements-security.txt`, `requirements-semgrep.txt`, `requirements.txt` |
| `benchmarks` | Python | `@source-stack:Python` |
| `bin` | Node.js | `@source-stack:Node.js` |
| `examples` | Python | `@source-stack:Python` |
| `scripts` | Python | `@source-stack:Python` |
| `src` | Python | `@source-stack:Python` |
| `tests` | Node.js, Python | `@source-stack:Node.js`, `@source-stack:Python` |

## Architecture and Maintainability

- [EVIDENCE-001] Verify a project-specific claim against the linked evidence ledger before treating it as mandatory [generic baseline: base clean-code workflow]
- [ARCH-001] Keep responsibilities inside the applicable module boundary; preserve public contracts, dependency direction, validation, error, concurrency, and persistence behavior [generic baseline: base clean-code workflow; project applicability only from the evidence map]
- [MAINT-001] Split code when mixed responsibilities, repeated coupled changes, obscured control flow, or duplication with real change cost makes maintenance harder; treat numeric size limits as sourced soft signals only [generic baseline: base clean-code workflow]
- [REUSE-001] Search existing modules and abstractions before adding a helper; extract only for demonstrated reuse, domain meaning, or duplicated change cost [generic baseline: base clean-code workflow]

## Stack-Aware Rules

- [STACK-NODE-JS] For `.`, `bin`, `tests`, Keep synchronous CPU or filesystem work out of latency-sensitive request paths; measure event-loop or CPU pressure before adding workers, queues, or caches [stack evidence: `package.json`, `@source-stack:Node.js`]
- [STACK-PYTHON] For `.`, `benchmarks`, `examples`, `scripts`, `src`, `tests`, Keep package responsibilities explicit and isolate side effects at adapters; profile CPU, allocation, and I/O behavior before adding concurrency or caching [stack evidence: `@source-stack:Python`, `requirements-dev.txt`, `requirements-security.txt`, `requirements-semgrep.txt`, `requirements.txt`]

## Project-Native Verification

- [VERIFY-001] Run `npm run build` when its module and change type apply [evidence: `package.json`]
- [VERIFY-002] Run `npm run format` when its module and change type apply [evidence: `package.json`]
- [VERIFY-003] Run `npm run init` when its module and change type apply [evidence: `package.json`]
- [VERIFY-004] Run `npm run lint` when its module and change type apply [evidence: `package.json`]
- [VERIFY-005] Run `npm run migrate` when its module and change type apply [evidence: `package.json`]
- [VERIFY-006] Run `npm run postinstall` when its module and change type apply [evidence: `package.json`]
- [VERIFY-007] Run `npm run prepublishOnly` when its module and change type apply [evidence: `package.json`]
- [VERIFY-008] Run `npm run security:audit-signatures` when its module and change type apply [evidence: `package.json`]
- [VERIFY-009] Run `npm run start` when its module and change type apply [evidence: `package.json`]
- [VERIFY-010] Run `npm run test` when its module and change type apply [evidence: `package.json`]
- [VERIFY-011] Run `npm run test:all` when its module and change type apply [evidence: `package.json`]
- [VERIFY-012] Run `npm run test:assurance` when its module and change type apply [evidence: `package.json`]
- [VERIFY-013] Run `npm run test:collective` when its module and change type apply [evidence: `package.json`]
- [VERIFY-014] Run `npm run test:contract` when its module and change type apply [evidence: `package.json`]
- [VERIFY-015] Run `npm run test:coverage` when its module and change type apply [evidence: `package.json`]
- [VERIFY-016] Run `npm run test:handlers` when its module and change type apply [evidence: `package.json`]
- [VERIFY-017] Run `npm run test:integration` when its module and change type apply [evidence: `package.json`]
- [VERIFY-018] Run `npm run test:property` when its module and change type apply [evidence: `package.json`]
- [VERIFY-019] Run `npm run test:replay` when its module and change type apply [evidence: `package.json`]
- [VERIFY-020] Run `npm run test:runtime` when its module and change type apply [evidence: `package.json`]
- [VERIFY-021] Run `npm run test:security` when its module and change type apply [evidence: `package.json`]

## Performance

- [PERF-001] Use the repository measurement sources before optimizing, require measured benefit, and run regression verification [evidence: `benchmarks/benchmark.py`, `benchmarks/performance_benchmark_comprehensive.py`, `benchmarks/performance_benchmark_fixed.py`, `examples/benchmark_example.py`, `src/openrouter_mcp/handlers/benchmark.py`, `src/openrouter_mcp/handlers/benchmark_analyzer.py`, `src/openrouter_mcp/handlers/benchmark_cleanup.py`, `src/openrouter_mcp/handlers/benchmark_exporter.py`, `src/openrouter_mcp/handlers/mcp_benchmark.py`, `tests/benchmarks/test_benchmark.py`, `tests/benchmarks/test_mcp_benchmark_simple.py`, `tests/fixtures/benchmark_samples.py`, `tests/test_benchmark.py`, `tests/test_benchmark_analyzer_comparison.py`, `tests/test_benchmark_analyzer_ranking.py`, `tests/test_benchmark_concurrency_cancellation.py`, `tests/test_benchmark_exporter_csv.py`, `tests/test_benchmark_exporter_json.py`, `tests/test_benchmark_exporter_markdown.py`, `tests/test_benchmark_handlers.py`, `tests/test_benchmark_optional_averages.py`, `tests/test_benchmark_response_parsing.py`, `tests/test_collective_intelligence/test_performance_benchmarks.py`, `tests/test_enhanced_benchmark_optional_averages.py`, `tests/test_mcp_benchmark.py`, `tests/test_mcp_benchmark_category_selection.py`, `tests/test_mcp_benchmark_data_building.py`, `tests/test_mcp_benchmark_report_deserialization.py`, `tests/test_mcp_benchmark_success_selection.py`]

## Evidence and Precedence

Read the [evidence ledger](references/evidence.md) before applying a project-specific rule
<!-- clean-code:managed:end -->

<!-- clean-code:manual:start -->
<!-- Add project-owned rules here. Keyed rules that conflict with managed IDs remain visible but inactive. -->
<!-- clean-code:manual:end -->
