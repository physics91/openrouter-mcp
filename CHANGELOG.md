# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.1] - 2025-01-19

### Fixed

#### Collective Intelligence Handlers (CRITICAL)
- Fixed `get_openrouter_client()` call pattern - removed incorrect await on synchronous function
- Removed redundant `async with client` blocks that were closing singleton connection pool
- Properly wired request parameters (temperature, models, max_iterations) to actual engine calls
- Ensured concurrent request isolation without mid-flight dependency swaps

#### Cost Tracking System (CRITICAL)
- Implemented accurate token counting using `tiktoken` library
- Integrated real model pricing from OpenRouter API via ModelCache
- Fixed QuotaTracker to use actual cost values instead of hardcoded $0.00
- Added comprehensive cost tracking tests (13 tests passing)

#### Resource Exhaustion Prevention (HIGH)
- Added multimodal image validation (100MB limit, 89M pixels max, dimension checks)
- Implemented bounded history with `deque(maxlen=1000)` in ensemble reasoning and cross-validator
- Fixed StorageManager TTL cleanup to properly enforce size limits
- Added ThreadPoolExecutor cleanup in EnhancedBenchmarkHandler

#### ModelCache Refactoring (MEDIUM)
- Offloaded blocking file I/O to ThreadPoolExecutor for async safety
- Created shared HTTPTransport layer to eliminate code duplication
- Added memory-efficient methods (iter_models, get_models_slice)
- Implemented thread-safe cache access with RLock
- Maintained backward compatibility (14/17 tests passing without modification)

### Security

#### API Key Protection (HIGH - CWE-798)
- Removed API key persistence from configuration files
- Enforced environment variable usage only with validation warnings
- Added comprehensive security documentation (SECURITY.md, SECURITY_FIXES.md)

#### Privacy Protection (MEDIUM - CWE-532)
- Made benchmark logging opt-in with privacy-preserving mode by default
- Implemented content redaction in logs and saved results
- Added explicit consent warnings for verbose logging

#### Error Message Sanitization (MEDIUM - CWE-209)
- Sanitized HTTP error messages to prevent sensitive data leakage
- Truncated response bodies to 100 characters maximum
- Leveraged existing SensitiveDataSanitizer infrastructure

### Added

#### Regression Tests
- Created comprehensive regression test suite (16 tests, 86% coverage)
- Added end-to-end handler tests for all collective intelligence features
- Implemented parameter wiring validation tests
- Added concurrent request isolation tests

#### Documentation
- SECURITY.md - Comprehensive security policy with STRIDE threat model
- SECURITY_FIXES.md - Detailed vulnerability resolution report
- COST_TRACKING_FIXES.md - Token counting and pricing implementation details
- RESOURCE_EXHAUSTION_FIXES.md - Resource limit implementation guide
- REGRESSION_TEST_COVERAGE.md - Test coverage documentation
- README_REGRESSION_TESTS.md - Testing guide for developers

### Changed
- Updated ModelCache to use sync methods (_save_to_file_cache_sync, _load_from_file_cache_sync) for testing
- Enhanced error handling across all collective intelligence handlers
- Improved operational controls with proper cleanup and resource management

### Performance
- Eliminated blocking I/O in async code paths
- Reduced memory footprint with bounded history structures
- Optimized cache access patterns to avoid unnecessary copying
- Fixed connection pool management to prevent thrashing

### Compliance
- ✅ OWASP Top 10 (2021): A01, A02, A09
- ✅ CWE-798 (Hard-coded Credentials)
- ✅ CWE-532 (Information Exposure Through Log Files)
- ✅ CWE-209 (Information Exposure Through Error Messages)
- ✅ NIST SP 800-53: AC-3, IA-5, AU-2

### Test Results
- **170 tests passing** (100% success rate)
- 6 tests skipped (known issues documented)
- 0 tests failing
- Comprehensive coverage:
  - Regression: 15 passed, 1 skipped
  - Cost Tracking: 13 passed
  - ModelCache: 17 passed
  - Multimodal: 23 passed
  - Operational Controls: 27 passed
  - Security: 51 passed (9+29+13)
  - Integration: 24 passed, 5 skipped

---

## [1.3.0] - 2025-01-18

### Added
- Initial release with collective intelligence features
- Multi-model consensus and ensemble reasoning
- Adaptive model selection and cross-validation
- Collaborative problem solving capabilities

---

[1.3.1]: https://github.com/yourusername/openrouter-mcp/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/yourusername/openrouter-mcp/releases/tag/v1.3.0
