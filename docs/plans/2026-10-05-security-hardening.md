<!-- regular-plan-v1 -->
# Security discovery and remediation

## Goal
Repeat security discovery, remediation, and verification until no confirmed
in-scope security finding remains unresolved. Do not claim proof of the absence
of all vulnerabilities; record the inspected attack surfaces and verification
limits, including unavailable production credentials.

## Scope
OpenRouter MCP server, Node launcher and credential handling, shipped and
development dependencies, and repository security checks. No global Python
environment changes, credential rotation, or package publishing. After the
remediation review, the user authorized commits, a merge into `develop`, and a
push to `origin/develop`.

## Approach
Keep development in `security-hardening-20261005`. Reproduce through real local
MCP transports where possible, add meaningful regression coverage, fix causes,
then repeat manual review and current advisory checks. Test artifacts and
scanner environments stay in ignored paths or outside the repository.

## Steps
1. Confine benchmark report paths and prevent linked-file overwrite.
2. Validate runtime dependency versions before importing/starting the server;
   update vulnerable dependency floors and the npm lockfile.
3. Correct credential detection and inspect adjacent credential operations.
4. Review remaining tool inputs, output files, image processing, error logging,
   transport exposure, and supply-chain controls; fix demonstrated findings.
5. Run current dependency and source scans, focused regression tests, real
   stdio security checks, static quality gates, and the assurance suite.
6. Inspect final evidence against the original scope; preserve this worktree
   while the work is unmerged and report any required unverified area.

## Verification
- Traversal, absolute paths, symlinks, and hardlinks cannot redirect report I/O.
- A valid report export still works over real stdio without a provider call.
- The launcher rejects missing or outdated declared runtime dependencies.
- Quoted, spaced, exported, and duplicate dotenv assignments are interpreted
  consistently by retrieval, auditing, rotation, and deletion.
- Runtime, development, and scanner dependency findings are resolved or have
  explicit applicability evidence; scanners must not silently skip failures.
- Security regressions and assurance pass. Run project quality gates and
  distinguish inherited failures from any newly introduced failure.
- No developer credentials, primary checkout files, or protected branches are
  changed. Remaining limitations are stated, never treated as passing checks.

## Remediation and evidence — 2026-10-05

Worktree: `.worktrees/security-hardening-20261005`; branch:
`security-hardening-20261005`. Development writes were confined to this task
worktree and branch. The authorized integration uses a clean-primary merge into
`develop`, followed by a push to `origin/develop`. Remove the clean task worktree
and its local branch once integration and pushing are complete. No package
release or credential rotation is part of this work.

### Confirmed findings addressed

- Report export accepted absolute and parent-relative input/output paths.
  Reproduced over the real Node launcher and MCP stdio transport. Restrict file
  names to the benchmark directory, reject symlinks, and publish reports by
  atomic replacement so hardlinks cannot overwrite another file.
- Startup imported packages without checking their versions, permitting old
  FastMCP/MCP/Pillow dependencies. Check declared versions before server imports,
  fail closed, and require an explicit dependency installation in a virtual
  environment. The actual older system interpreter is now refused.
- Credential auditing, retrieval, rotation, and deletion disagreed on quoted,
  spaced, exported, duplicate, and multiline dotenv values. Share parsing and
  replacement logic; reject API-key and setting newline injection.
- Credential writes could follow links or expose new content through an old
  permissive file. Use exclusive private temporary files and atomic replacement;
  reject symbolic-link destinations. Permission repair retains directory search
  permission with mode 0700; regular credential files use 0600 on POSIX.
- Provider error messages leaked arbitrary response content. A real local HTTP
  echo service reproduced the issue. Return only the HTTP status and standard
  status text. The local provider in this regression is synthetic, not OpenRouter.
- Deferred batches created world-readable prompt artifacts and reused predictable
  paths. Use unique 0700 directories, atomic 0600 files, and collision-free group
  filenames. Restrict image decoding to JPEG, PNG, WEBP, and GIF.
- Both HTTP transports accepted remote plaintext API base URLs. Require HTTPS
  remotely, with explicit loopback HTTP allowed for local development. Reject URL
  userinfo, query strings, and fragments; correct the unimplemented certificate
  pinning claim in the security documentation.

### Verification

- `python run_tests.py assurance -v`: 1,186 passed; 808 outside the selected
  markers; branch coverage 77.58% (required 70%). Node security tests also passed.
- Real MCP stdio: valid export works; traversal, absolute paths, and symlinks are
  rejected; overwriting a hardlink leaves the outside file unchanged.
- `npm audit`: zero findings across production and development dependencies.
  Registry signatures verified for all 183 packages; 10 attestations verified.
- `pip-audit`: zero findings for the 77-package lowest-direct runtime resolution
  targeting Python 3.10, and zero for the actual 94-package worktree environment.
  `uv pip check` reports no installed dependency conflicts.
- Semgrep dependency audit: 65 packages, zero database findings. Manual SDK
  advisory review remains necessary because newly published advisories can lag
  scanner databases; see the applicability note below.
- Bandit: zero findings. Semgrep OWASP: zero findings. Combined security-audit
  rules report three existing child-process findings: the executable comes from
  fixed Python probing or local CLI install builders, arguments are passed as
  arrays, and shell execution is not enabled. This assumes a trusted local PATH.
- Gitleaks 8.30.1: zero findings in the current source snapshot and Git history;
  reports were redacted. npm dry-run includes all new launcher helpers and no
  virtual environment or node_modules.
- `git diff --check` passes. Full style gates remain red from the baseline:
  Ruff 1,359 baseline / 1,356 current, with no new finding; Black 42 baseline
  files; isort eight baseline files. Unrelated style repairs are out of scope.

Raw reports are temporary local artifacts under
`/tmp/openrouter-security-wl7o5vcn/`; they contain no live credential values.

### Residual scanner dependency findings and applicability

- Safety 3.7.0 introduces NLTK 3.10.3. Both the 220-package development resolution
  and the 64-package security-tool resolution still report
  [CVE-2026-81726 / GHSA-8mgp-746c-j5xp](https://github.com/advisories/GHSA-8mgp-746c-j5xp).
  The advisory lists no patched version. Its prerequisite is an application
  allowing attacker-controlled paths through NLTK model-artifact APIs under
  pathsec enforcement. This project does not call those APIs. Inspection of
  checksum-verified official Safety 3.7.0 and 3.8.1 wheels found only
  `nltk.edit_distance` in `safety/tool/typosquatting.py:42`, plus a package-name
  constant. This is evidence for non-applicability to our scanner invocation,
  **not** a patched dependency or a clean scanner result. No ignore rule or
  weakened gate was introduced. The user explicitly chose to retain Safety and
  report the non-applicability evidence and residual CVE on 2026-10-05. This does
  not turn the scanner's nonzero finding count into a clean CI result.
- Semgrep 1.179.0 pins MCP 1.29.0. Recent upstream advisories affecting HTTP
  servers, OAuth clients, redirects, and remote schema references are fixed in
  MCP 1.30.0, used by our application. Our isolated Semgrep invocation only runs
  `semgrep scan`; it does not expose an MCP HTTP server or connect to a remote MCP
  server. Reassess before enabling Semgrep's MCP server/client features.
  Sources: [body limits](https://github.com/modelcontextprotocol/python-sdk/security/advisories/GHSA-fmmv-w9g8-j3gc),
  [session retention](https://github.com/modelcontextprotocol/python-sdk/security/advisories/GHSA-84m7-p3x7-pcfv),
  [OAuth](https://github.com/modelcontextprotocol/python-sdk/security/advisories/GHSA-qx49-fqc8-xw99),
  [redirects](https://github.com/modelcontextprotocol/python-sdk/security/advisories/GHSA-5h93-6whr-6q8j),
  [schema references](https://github.com/modelcontextprotocol/python-sdk/security/advisories/GHSA-rwrf-2pqf-9j8j).
- The minimum-runtime audit caught cryptography 49.0.0 still affected by
  [CVE-2026-69247](https://github.com/advisories/GHSA-g6cj-pr64-35w5); require
  50.0.0 or later. This keeps the existing Apache-2.0/BSD-3-Clause dependency;
  no replacement cryptography implementation or new runtime library was added.

### Limits, deployment checks, and rollback

No live OpenRouter request was made because a usable API key was unavailable.
The native keytar module could not be loaded, so no OS-keystore acceptance is
claimed. Linux/Python 3.12/Node 24 were exercised; Python 3.10 resolution was
checked, but Windows/macOS ACLs and their native keystores were not exercised.

Deployment is not authorized and has not occurred. After an authorized release,
verify dependency status, MCP initialization, a valid report export, and normal
provider calls in the actual client environment. Older environments now stop;
configure a virtual environment with the updated requirements. Remote plaintext
proxies need HTTPS, and symlink credential destinations must be regular files.
Rollback consists of reverting these task changes or restoring the previous
package release; doing so also restores the documented vulnerabilities. Private
batch/report files should retain their restrictive permissions.

Local remediation and verification are complete with the user's explicit
decision to retain Safety and disclose its residual CVE. The literal scanner
count remains nonzero for that dependency. No claim of universal vulnerability
absence is made; reassess when NLTK/Safety releases a fix or its usage changes.
