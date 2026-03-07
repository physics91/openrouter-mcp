# Research Report: Local Skill Needs for `openrouter-mcp`

## Executive Summary

- 이 레포는 Node.js CLI와 Python MCP 서버가 결합된 하이브리드 구조이며, 테스트/보안/배포 게이트가 이미 상당히 성숙해 있다. 따라서 로컬 스킬은 "새 기능을 많이 만드는 것"보다 "이미 있는 운영 복잡도를 표준화하는 것"에 초점을 맞춰야 한다.
- 현재 로컬 스킬 4개(`build`, `test`, `deploy`, `git-worktree`)는 기반이 좋다. 다만 실제 레포 운영 복잡도에 비해 `test`와 `deploy`의 책임 범위가 좁고, 보안/운영 정책을 다루는 전용 스킬이 부재하다.
- 최우선 과제는 신규 스킬 남발이 아니라 `test`와 `deploy`를 확장해 레포의 사실상 표준 워크플로를 하나로 고정하는 것이다.
- 신규 스킬이 꼭 필요하다면 3개가 현실적이다: `security-ops`, `mcp-config-ops`, `resilience-policy`.
- 별도 스킬 후보였던 `publish-metadata-validator`는 독립 스킬보다 `deploy` 스킬의 pre-flight 단계로 흡수하는 편이 더 낫다.

**Primary Recommendation:**
이 프로젝트의 적정 로컬 스킬 포트폴리오는 총 6~7개다.

1. 유지: `build`
2. 강화: `test`
3. 강화: `deploy`
4. 유지: `git-worktree`
5. 신규: `security-ops`
6. 신규: `mcp-config-ops`
7. 선택적 신규: `resilience-policy`

---

## Research Question

이 프로젝트에 어떤 로컬 스킬이 실제로 필요하며, 기존 스킬 확장과 신규 스킬 생성 중 어디에 우선순위를 둬야 하는가?

---

## Scope

포함 범위:
- 현재 레포의 구조, 테스트 체계, 배포 흐름, 보안 운영 패턴
- 이미 존재하는 로컬 스킬 4개의 커버리지와 갭
- MCP/FastMCP/OpenRouter/npm 공식 문서 기반 외부 검증

제외 범위:
- 코드 수정 구현
- CI 워크플로 전면 개편
- npm 실제 배포 실행

---

## Evidence Base

### Repository evidence
- [README.md](/home/physics91/dev/openrouter-mcp/README.md)
- [package.json](/home/physics91/dev/openrouter-mcp/package.json)
- [run_tests.py](/home/physics91/dev/openrouter-mcp/run_tests.py)
- [.github/workflows/assurance-required.yml](/home/physics91/dev/openrouter-mcp/.github/workflows/assurance-required.yml)
- [.github/workflows/assurance-extended.yml](/home/physics91/dev/openrouter-mcp/.github/workflows/assurance-extended.yml)
- [.github/workflows/ci.yml](/home/physics91/dev/openrouter-mcp/.github/workflows/ci.yml)
- [.github/workflows/test-coverage.yml](/home/physics91/dev/openrouter-mcp/.github/workflows/test-coverage.yml)
- [docs/ASSURANCE.md](/home/physics91/dev/openrouter-mcp/docs/ASSURANCE.md)
- [docs/TESTING.md](/home/physics91/dev/openrouter-mcp/docs/TESTING.md)
- [tests/README.md](/home/physics91/dev/openrouter-mcp/tests/README.md)
- [src/openrouter_mcp/server.py](/home/physics91/dev/openrouter-mcp/src/openrouter_mcp/server.py)
- [src/openrouter_mcp/mcp_registry.py](/home/physics91/dev/openrouter-mcp/src/openrouter_mcp/mcp_registry.py)
- [src/openrouter_mcp/cli/mcp_manager.py](/home/physics91/dev/openrouter-mcp/src/openrouter_mcp/cli/mcp_manager.py)
- [src/openrouter_mcp/collective_intelligence/operational_controls.py](/home/physics91/dev/openrouter-mcp/src/openrouter_mcp/collective_intelligence/operational_controls.py)
- [bin/secure-credentials.js](/home/physics91/dev/openrouter-mcp/bin/secure-credentials.js)
- [.agents/skills/build/SKILL.md](/home/physics91/dev/openrouter-mcp/.agents/skills/build/SKILL.md)
- [.agents/skills/test/SKILL.md](/home/physics91/dev/openrouter-mcp/.agents/skills/test/SKILL.md)
- [.agents/skills/deploy/SKILL.md](/home/physics91/dev/openrouter-mcp/.agents/skills/deploy/SKILL.md)
- [.agents/skills/git-worktree/SKILL.md](/home/physics91/dev/openrouter-mcp/.agents/skills/git-worktree/SKILL.md)

### External evidence
- MCP Security Best Practices: <https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices>
- MCP Tools Specification: <https://modelcontextprotocol.io/specification/2025-06-18/server/tools>
- FastMCP docs summary via Context7 (`/jlowin/fastmcp`)
- npm Trusted Publishing: <https://docs.npmjs.com/trusted-publishers/>
- npm package.json docs: <https://docs.npmjs.com/cli/v11/configuring-npm/package-json/>
- npm scoped public packages: <https://docs.npmjs.com/creating-and-publishing-scoped-public-packages/>
- OpenRouter Authentication docs: <https://openrouter.ai/docs/api/reference/authentication>
- OpenRouter Limits docs: <https://openrouter.ai/docs/api/reference/limits>

---

## Current Project Profile

### Structural signals
- `src/openrouter_mcp` 아래 Python 소스가 약 50개이고, 테스트 파일은 약 69개다.
- GitHub Actions 워크플로는 최소 4개이며, `required`, `extended`, `legacy CI`, `coverage`로 역할이 분화되어 있다.
- 현재 로컬 스킬은 `build`, `test`, `deploy`, `git-worktree` 네 개뿐이다.

### Operational signals
- 로컬 테스트의 canonical entrypoint는 실질적으로 [run_tests.py](/home/physics91/dev/openrouter-mcp/run_tests.py)다.
- 하지만 문서와 스크립트에는 `python3 run_tests.py assurance -v`와 `npm run test:assurance`가 혼재한다.
- 배포는 여전히 수동 `npm publish --access public` 중심이며, `prepublishOnly`는 사실상 무효화 메시지만 출력한다.
- 보안 자격증명 운영은 [bin/secure-credentials.js](/home/physics91/dev/openrouter-mcp/bin/secure-credentials.js)에 집중되어 있지만, 이를 표준 운영 절차로 묶는 전용 로컬 스킬은 없다.

---

## Assessment of Existing Skills

### 1. `build`

강점:
- 현재 CI 필수 정적 게이트(`ruff`, `black`, `isort`)와 잘 맞는다.
- "빌드가 곧 정적 품질 게이트"라는 레포 현실을 정확히 반영한다.

한계:
- 실제 워크플로에서 `mypy`, 보안 정적 분석, pre-commit과의 관계는 분리돼 있다.
- 독립 신규 스킬이 필요할 정도는 아니지만, `optional profile` 문맥은 더 명확해질 여지가 있다.

판정:
- **유지**

### 2. `test`

강점:
- `run_tests.py` 중심이라는 사실을 반영하고 있다.
- `assurance`를 PR readiness 기본값으로 잡은 점이 맞다.

한계:
- 레포 현실은 단순 "테스트 실행"보다 "로컬에서 CI-required 게이트를 어떻게 재현할 것인가"가 더 중요하다.
- `commit message validation`, `security test`, `coverage threshold`, `node_modules auto-install`, `pytest-cov missing` 같은 운영 판단이 산재해 있다.
- 현재 설명은 "무슨 suite가 있나"에 머물고, "PR 직전 표준 순서"를 충분히 강제하지 않는다.

판정:
- **강화 필요, 신규 분리보다 확장 우선**

### 3. `deploy`

강점:
- 수동 publish 정책을 잘 반영한다.
- `build`와 `assurance`를 pre-flight로 강제하는 방향이 적절하다.

한계:
- 실제 배포 리스크의 상당수는 테스트 미실행보다 메타데이터/문서 정합성 문제다.
- [package.json](/home/physics91/dev/openrouter-mcp/package.json)의 `author`, `homepage`, `repository`, `bugs`는 placeholder 상태고, [CHANGELOG.md](/home/physics91/dev/openrouter-mcp/CHANGELOG.md)는 `yourusername` 링크를 유지한다.
- npm 공식 문서상 `package.json` 메타데이터는 패키지 신뢰성과 직접 연결되며, scoped public package는 `npm publish --access public`이 필요하다. 이 레포는 scoped package라서 배포 skill이 메타데이터 검증을 포함하는 편이 자연스럽다.

판정:
- **강화 필요, 특히 metadata/placeholder validation 내장**

### 4. `git-worktree`

강점:
- 이미 연구 보고서와 상세 참조 문서를 가진 상태다.
- 병렬 브랜치 작업, hotfix interruption, linked worktree recovery 같은 실전 시나리오를 잘 커버한다.

한계:
- 현재 프로젝트의 가장 큰 병목은 worktree보다 test/deploy/security 쪽이다.

판정:
- **유지**

---

## Skill Needs by Priority

## Priority 0: Existing Skills to Strengthen First

### A. `test` → 사실상 `local assurance` 스킬로 확장

왜 필요한가:
- [run_tests.py](/home/physics91/dev/openrouter-mcp/run_tests.py), [package.json](/home/physics91/dev/openrouter-mcp/package.json), [docs/ASSURANCE.md](/home/physics91/dev/openrouter-mcp/docs/ASSURANCE.md), [tests/README.md](/home/physics91/dev/openrouter-mcp/tests/README.md), [assurance-required.yml](/home/physics91/dev/openrouter-mcp/.github/workflows/assurance-required.yml) 사이에 실행 진입점이 분산돼 있다.
- 사용자는 "무슨 테스트를 돌릴까?"보다 "PR 전에 정확히 무엇을 돌리면 되나?"가 더 중요하다.

확장 범위:
- 기본 모드: `python3 run_tests.py assurance -v`
- 프리체크: Python/Node 존재 여부, `pytest-cov`, `node_modules`
- 결과 요약: 실패 suite, coverage shortfall, Node security stage 진입 여부
- 선택 프로필: `quick`, `regression`, `coverage`, `real`
- 선택적으로 `commit message validation`과 연결

권고:
- 새로운 `local-assurance` 스킬을 따로 만들기보다 `test`를 그 수준까지 확장하는 편이 낫다.

### B. `deploy` → metadata-aware release skill로 확장

왜 필요한가:
- 릴리스 절차는 [README.md](/home/physics91/dev/openrouter-mcp/README.md), [CONTRIBUTING.md](/home/physics91/dev/openrouter-mcp/CONTRIBUTING.md), [package.json](/home/physics91/dev/openrouter-mcp/package.json), [CHANGELOG.md](/home/physics91/dev/openrouter-mcp/CHANGELOG.md)에 분산돼 있다.
- placeholder 메타데이터가 남아 있어 발행 품질 신뢰도를 떨어뜨린다.
- npm 공식 문서는 trusted publishing/provenance와 `package.json` 메타데이터의 중요성을 분명히 한다.

확장 범위:
- `package.json` 필드 검증: `author`, `homepage`, `repository`, `bugs`
- placeholder 스캔: `yourusername`, `yourproject.com`, `Your Name`, `your-domain-here`
- changelog/release tag 링크 검증
- scoped package publish 확인: `npm publish --access public`
- 향후 trusted publishing/provenance 전환 시 체크리스트 포함

권고:
- `publish-metadata-validator`를 별도 스킬로 두기보다 `deploy` pre-flight에 흡수

---

## Priority 1: New Skills That Are Worth Adding

### 1. `security-ops`

필요성:
- [bin/secure-credentials.js](/home/physics91/dev/openrouter-mcp/bin/secure-credentials.js), [docs/SECURITY.md](/home/physics91/dev/openrouter-mcp/docs/SECURITY.md), [docs/SECURITY_BEST_PRACTICES.md](/home/physics91/dev/openrouter-mcp/docs/SECURITY_BEST_PRACTICES.md), [README.md](/home/physics91/dev/openrouter-mcp/README.md) 전반에 자격증명 저장, 회전, 삭제, 감사 로그, 공유 환경 탐지가 넓게 퍼져 있다.
- OpenRouter 공식 문서는 API key가 단순 토큰 이상으로 강한 권한과 credit-limit 의미를 가진다고 설명한다.
- MCP 공식 보안 가이드는 네트워크 egress 통제, SSRF 방어, 명시적 보안 설명을 강조한다.
- MCP tools spec은 tool invocation에 human-in-the-loop와 명확한 도구 노출을 권고한다.

권장 범위:
- 저장 위치 우선순위 점검
- `security-audit` / `rotate-key` / `delete-credentials` 실행 기준
- 공유 환경 감지 시 경고
- 문서 내 보안 연락처 placeholder 점검
- 민감정보 로그/보고서 출력 규칙

이 스킬이 중요한 이유:
- 이 레포의 "배포 성공"보다 더 큰 리스크는 API key 오운영이다.

### 2. `mcp-config-ops`

필요성:
- [src/openrouter_mcp/cli/mcp_manager.py](/home/physics91/dev/openrouter-mcp/src/openrouter_mcp/cli/mcp_manager.py)와 [src/openrouter_mcp/cli/commands.py](/home/physics91/dev/openrouter-mcp/src/openrouter_mcp/cli/commands.py)에 백업/복원, preset, Claude Desktop/Code 설치, overwrite 정책이 모여 있다.
- [bin/openrouter-mcp.js](/home/physics91/dev/openrouter-mcp/bin/openrouter-mcp.js)와 [src/openrouter_mcp/server.py](/home/physics91/dev/openrouter-mcp/src/openrouter_mcp/server.py)는 Node/Python 하이브리드 부트스트랩을 형성한다.
- 설치 문서에는 scoped/unscoped package 명칭 혼선이 존재한다.

권장 범위:
- 환경 프리체크: Node/Python/CLI 경로
- `install-claude`, `install-claude-code`, `status` 표준 순서
- 설정 파일 백업/복원/runbook
- 설치 문서와 실제 명령 정합성 검사

이 스킬이 중요한 이유:
- 사용자 온보딩 실패와 설정 드리프트를 가장 직접적으로 줄인다.

### 3. `resilience-policy`

필요성:
- [src/openrouter_mcp/collective_intelligence/operational_controls.py](/home/physics91/dev/openrouter-mcp/src/openrouter_mcp/collective_intelligence/operational_controls.py), [src/openrouter_mcp/collective_intelligence/consensus_engine.py](/home/physics91/dev/openrouter-mcp/src/openrouter_mcp/collective_intelligence/consensus_engine.py), [src/openrouter_mcp/handlers/mcp_benchmark.py](/home/physics91/dev/openrouter-mcp/src/openrouter_mcp/handlers/mcp_benchmark.py)는 동시성 제한, 회로 차단, quota, cleanup, 파일 I/O 오프로드, 실행 슬롯 정리 등 운영 정책이 높은 결합도로 얽혀 있다.
- FastMCP 공식 문서는 인증, 프록시, server mounting 등 운영 난이도를 높이는 패턴을 이미 지원한다.

권장 범위:
- concurrency/quota/circuit breaker 변경 시 체크리스트
- load/perf 관련 테스트 진입점
- cleanup/shutdown invariants
- replay/property/performance 테스트와 연결

이 스킬이 중요한 이유:
- 일반 기능 변경보다 집단지성 계층의 운영 정책 변경이 회귀 리스크가 더 크다.

---

## Priority 2: Candidates Better Treated as Extensions, Not Standalone Skills

### `publish-metadata-validator`
- 가치 자체는 높다.
- 하지만 release 전용 pre-flight 성격이 강해 `deploy` 안에 넣는 편이 운영 비용이 낮다.

### `install-doc-sync`
- 설치 문서 정합성 문제는 실제로 존재한다.
- 다만 scope가 좁고, `mcp-config-ops` 혹은 `deploy`의 문서 검증 단계로 흡수 가능하다.

### `runtime-bootstrap`
- Node/Python 하이브리드 부트스트랩은 중요하다.
- 하지만 설치/상태/설정/백업과 함께 묶는 편이 더 재사용성이 높아 `mcp-config-ops` 하위로 넣는 편이 낫다.

---

## Recommended Portfolio

### Minimal, practical portfolio

1. `build`
   유지. 정적 품질 게이트 전담.

2. `test`
   확장. 실질적인 `local assurance` 표준 진입점으로 승격.

3. `deploy`
   확장. metadata/placeholder/release-link 검증 포함.

4. `git-worktree`
   유지. 병렬 개발/중단 대응 전담.

5. `security-ops`
   신규. 자격증명 lifecycle, audit, shared environment, disclosure contact 점검.

6. `mcp-config-ops`
   신규. CLI integration install, backup/restore, bootstrap, config drift 대응.

### Optional seventh skill

7. `resilience-policy`
   집단지성 계층 변경 빈도가 높거나 장애 비용이 커질 때 추가.

---

## Why This Set Is Right-Sized

- 스킬 수가 과도하게 늘어나면 사용자와 에이전트 모두 호출 기준이 흐려진다.
- 이 레포는 이미 `build/test/deploy/git-worktree`의 뼈대가 있으므로, 이를 보강하는 편이 신규 스킬 난립보다 비용 대비 효과가 높다.
- 신규 스킬은 "반복적이고, 실수 비용이 높고, 여러 파일/문서/명령에 걸친 운영 절차"에만 쓰는 것이 맞다.

이 기준을 적용하면:
- `security-ops`: 반복적이고 비싸고 문서/명령/코드가 분산됨
- `mcp-config-ops`: 온보딩/설정 드리프트 비용이 큼
- `resilience-policy`: 특정 고위험 subsystem 전용

반대로 단독 스킬로 약한 후보:
- package metadata 검사만 하는 스킬
- 설치 문서 정합성만 보는 스킬
- 단순 테스트 래퍼 스킬

---

## Action Plan

1. 먼저 [test/SKILL.md](/home/physics91/dev/openrouter-mcp/.agents/skills/test/SKILL.md)를 확장해 `assurance`를 로컬 PR 게이트의 유일한 표준 진입점으로 고정한다.
2. 다음으로 [deploy/SKILL.md](/home/physics91/dev/openrouter-mcp/.agents/skills/deploy/SKILL.md)에 metadata/placeholder/link 검증을 넣는다.
3. 세 번째로 `security-ops`를 신규 생성해 `init`, `rotate-key`, `delete-credentials`, `security-audit` runbook을 표준화한다.
4. 네 번째로 `mcp-config-ops`를 추가해 Claude Desktop/Code 설치와 설정 백업/복원 절차를 정리한다.
5. 마지막으로 집단지성 기능 변경이 빈번해질 때 `resilience-policy`를 추가한다.

---

## Final Conclusion

이 프로젝트는 "스킬이 없는 상태"가 아니라 "핵심 스킬은 있는데, 운영 리스크가 큰 부분까지 아직 스킬화되지 않은 상태"다.

따라서 가장 좋은 전략은:
- 기존 4개를 버리지 않는다.
- `test`, `deploy`를 먼저 강하게 만든다.
- 그 다음 신규 스킬은 `security-ops`, `mcp-config-ops` 두 개를 우선 추가한다.
- `resilience-policy`는 팀이 집단지성 기능을 더 밀어붙일 때 선택적으로 도입한다.

즉, 결론은 "많이 만들자"가 아니라:

**기존 4개를 중심으로 2개를 확실히 추가하고, 1개는 선택적으로 보강하자**이다.

---

## Bibliography

1. [README.md](/home/physics91/dev/openrouter-mcp/README.md)
2. [package.json](/home/physics91/dev/openrouter-mcp/package.json)
3. [run_tests.py](/home/physics91/dev/openrouter-mcp/run_tests.py)
4. [docs/ASSURANCE.md](/home/physics91/dev/openrouter-mcp/docs/ASSURANCE.md)
5. [tests/README.md](/home/physics91/dev/openrouter-mcp/tests/README.md)
6. [.github/workflows/assurance-required.yml](/home/physics91/dev/openrouter-mcp/.github/workflows/assurance-required.yml)
7. [.github/workflows/assurance-extended.yml](/home/physics91/dev/openrouter-mcp/.github/workflows/assurance-extended.yml)
8. [.github/workflows/ci.yml](/home/physics91/dev/openrouter-mcp/.github/workflows/ci.yml)
9. [.github/workflows/test-coverage.yml](/home/physics91/dev/openrouter-mcp/.github/workflows/test-coverage.yml)
10. [src/openrouter_mcp/server.py](/home/physics91/dev/openrouter-mcp/src/openrouter_mcp/server.py)
11. [src/openrouter_mcp/mcp_registry.py](/home/physics91/dev/openrouter-mcp/src/openrouter_mcp/mcp_registry.py)
12. [src/openrouter_mcp/cli/mcp_manager.py](/home/physics91/dev/openrouter-mcp/src/openrouter_mcp/cli/mcp_manager.py)
13. [src/openrouter_mcp/collective_intelligence/operational_controls.py](/home/physics91/dev/openrouter-mcp/src/openrouter_mcp/collective_intelligence/operational_controls.py)
14. [bin/secure-credentials.js](/home/physics91/dev/openrouter-mcp/bin/secure-credentials.js)
15. [.agents/skills/build/SKILL.md](/home/physics91/dev/openrouter-mcp/.agents/skills/build/SKILL.md)
16. [.agents/skills/test/SKILL.md](/home/physics91/dev/openrouter-mcp/.agents/skills/test/SKILL.md)
17. [.agents/skills/deploy/SKILL.md](/home/physics91/dev/openrouter-mcp/.agents/skills/deploy/SKILL.md)
18. [.agents/skills/git-worktree/SKILL.md](/home/physics91/dev/openrouter-mcp/.agents/skills/git-worktree/SKILL.md)
19. MCP Security Best Practices. <https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices>
20. MCP Tools Specification. <https://modelcontextprotocol.io/specification/2025-06-18/server/tools>
21. FastMCP documentation summary via Context7 (`/jlowin/fastmcp`)
22. npm Trusted Publishing. <https://docs.npmjs.com/trusted-publishers/>
23. npm `package.json` docs. <https://docs.npmjs.com/cli/v11/configuring-npm/package-json/>
24. npm scoped public packages. <https://docs.npmjs.com/creating-and-publishing-scoped-public-packages/>
25. OpenRouter Authentication docs. <https://openrouter.ai/docs/api/reference/authentication>
26. OpenRouter Limits docs. <https://openrouter.ai/docs/api/reference/limits>
