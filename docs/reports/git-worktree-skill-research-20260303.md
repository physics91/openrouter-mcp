# Research Report: Local Skill for `git worktree`

## Executive Summary
- **Key Finding 1:** `git worktree`는 단일 저장소에서 여러 작업 트리(working tree)를 연결해 동시에 여러 브랜치를 다룰 수 있게 하며, 메타데이터는 `$GIT_DIR/worktrees` 아래에 관리된다.[1][6]
- **Key Finding 2:** Git은 기본적으로 동일 브랜치의 다중 worktree 체크아웃을 안전장치로 막고, 우회는 `--force`(add) 또는 `--ignore-other-worktrees`(checkout/switch)로만 허용한다.[1][3][4][11]
- **Key Finding 3:** 운영 안정성은 `remove/prune/lock/repair` 조합과 `gc.worktreePruneExpire`, `extensions.worktreeConfig` 설정에 크게 좌우된다.[1][5][8]
- **Key Finding 4:** 자동화 스크립트는 경로를 하드코딩하지 말고 `git rev-parse --git-dir/--git-common-dir/--git-path`를 사용해야 worktree 환경에서 안전하다.[1][7]

**Primary Recommendation:** 로컬 스킬은 `안전 기본값(브랜치 1개=worktree 1개)`과 `운영 복구(runbook)`를 중심으로 설계하고, 위험 옵션은 "예외 상황에서만" 사용하도록 명시한다.

**Confidence Level:** High. 핵심 결론 대부분이 Git 공식 매뉴얼과 Git 릴리즈 노트의 일치된 진술에 기반한다.[1][5][11]

---

## Introduction

### Research Question
`git worktree` 사용을 표준화하는 로컬 스킬을 만들 때, 어떤 명령 시퀀스/안전 규칙/운영 규칙을 포함해야 실무에서 재현 가능하고 안전한가?

이 질문은 단순 명령어 나열이 아니라, 브랜치 충돌 방지, 메타데이터 누적 방지, 이동/삭제 이후 복구까지 다루는 실행 가능한 운영 규약이 필요하다는 점에서 중요하다.

### Scope & Methodology
본 연구는 Git 공식 문서(`git-worktree`, `git-config`, `gitrepository-layout`, `git-branch`, `git-checkout`, `git-switch`, `git-rev-parse`, `git-gc`, `git-sparse-checkout`, `git-clone`)와 Git 공식 릴리즈 노트를 중심으로 분석했다.[1][2][3][4][5][6][7][8][9][10][11][12]

포함 범위:
- worktree 생성/삭제/정리/복구 명령의 정확한 동작
- 동일 브랜치 동시 체크아웃 관련 안전장치와 우회 옵션
- per-worktree 설정, sparse-checkout 연계, 경로 해석 규칙
- clone 대안과의 운용 관점 비교

제외 범위:
- GUI 클라이언트별 UX 차이
- 특정 CI 서비스별 커스텀 통합 예제

### Key Assumptions
- 로컬 스킬 사용자는 CLI 기반 Git 워크플로를 사용한다.
- 저장소 구조를 스크립트로 다룰 가능성이 높아 경로 안정성 지침이 필요하다.
- 팀 단위 운영을 고려해 "위험 옵션 기본 금지"가 바람직하다.

---

## Main Analysis

### Finding 1: `git worktree`는 "공유 저장소 + 분리된 작업 트리 상태" 모델이다
공식 문서는 worktree를 "같은 저장소에 연결된 복수 working tree"로 정의하고, `add`로 새 작업 트리를 연결한다고 설명한다.[1] 이때 새 worktree는 객체/refs 등 공통 저장소 자원을 공유하면서도 `HEAD`, `index` 같은 파일은 worktree별로 분리된다.[1]

저장소 레이아웃 문서도 이를 뒷받침한다. `worktrees/<id>/` 아래에 linked worktree의 관리 파일이 저장되고, `gitdir`, `locked`, `config.worktree` 등 관리 포인트가 명시되어 있다.[6]

이는 스킬 설계에 직접적인 의미가 있다.
- 단순 "폴더 복제"가 아니라 Git 내부적으로 linked relationship을 갖는다.
- 잘못된 수동 이동/삭제는 관리 파일 불일치를 만들 수 있다.
- 따라서 스킬에 `git worktree move`/`repair`/`prune`를 필수 운영 명령으로 포함해야 한다.[1]

**Sources:** [1], [6]

### Finding 2: 동일 브랜치 다중 체크아웃은 기본 금지이며, 우회는 예외 처리로 제한해야 한다
`git worktree add`는 이미 다른 worktree에서 사용 중인 브랜치에 대해 기본적으로 생성 거부한다(강제 시 `--force`).[1] 또한 `git checkout`과 `git switch`는 기본적으로 다른 worktree에 체크아웃된 ref를 거부하고, `--ignore-other-worktrees`로만 우회한다.[3][4]

`git branch -f`조차 다른 worktree에서 체크아웃 중인 브랜치는 변경을 거부한다는 점은 강한 안전 의도를 보여준다.[2] Git v2.44 릴리즈 노트 역시 `-B` 동작 관련 규칙을 강화하며, 우회에 `--ignore-other-worktrees`가 필요하다고 명시한다.[11]

스킬 정책으로는 다음이 타당하다.
- 기본 규칙: 브랜치 하나를 동시에 하나의 worktree에서만 사용.
- 우회 옵션(`--force`, `--ignore-other-worktrees`)은 "복구/긴급" 시나리오로 한정.
- 우회 수행 전후 점검(`git worktree list --porcelain`, `git branch -vv`)을 체크리스트에 포함.

**Sources:** [1], [2], [3], [4], [11]

### Finding 3: 장기 운영 품질은 `remove/prune/lock/repair`와 GC 정책에서 결정된다
문서상 `remove`는 clean worktree만 제거 가능하고, unclean/submodule 포함 worktree는 `--force`가 필요하다.[1] 수동 폴더 삭제가 발생하면 stale 관리 파일이 남을 수 있으며, 이는 `git worktree prune` 및 `gc.worktreePruneExpire` 정책으로 정리된다.[1][5][8]

반대로 이동식 디스크/네트워크 공유 등 비상시나리오에서는 `lock`이 prune 방지에 필요하고, 레이아웃 문서의 `worktrees/<id>/locked`가 이를 구조적으로 보장한다.[1][6]

또한 main/linked worktree 이동 시 연결 손상은 `repair`로 복구 가능한 시나리오가 명시되어 있다.[1]

실무적으로 스킬에 필요한 것은 "명령"보다 "운영 순서"다.
1. 정상 종료: `worktree remove`.
2. 비정상 삭제 복구: `worktree prune` + 필요 시 `repair`.
3. 휴대 스토리지: `worktree lock --reason` 후 사용.
4. 보존 기간 정책: `gc.worktreePruneExpire` 조직 기본값 명시.

**Sources:** [1], [5], [6], [8]

### Finding 4: per-worktree 설정과 경로 해석 규칙을 스킬에 내장해야 자동화가 안전해진다
`extensions.worktreeConfig`를 활성화하면 `$GIT_DIR/config.worktree`가 로드되고 공통 config를 override할 수 있다.[5] `git sparse-checkout set`도 worktree별 sparsity를 위해 이 메커니즘 사용을 유도한다.[9]

또한 worktree 내부에서 `$GIT_DIR`과 `$GIT_COMMON_DIR`의 의미가 달라지고, Git은 경로 직접 추측 대신 `git rev-parse --git-path` 사용을 권고한다.[1][7]

결론적으로 스킬에는 다음이 필요하다.
- `git config --worktree` 사용 패턴
- `extensions.worktreeConfig` 전환 시 이동해야 하는 설정(`core.worktree`, `core.bare`) 경고
- 스크립트 템플릿에서 `rev-parse` 기반 경로 조회 강제

**Sources:** [1], [5], [7], [9]

### Finding 5: worktree는 "다중 clone"의 실용 대안이지만 완전 대체는 아니다
`git clone --shared/--reference` 계열은 객체 공유로 비용 절감을 제공하지만, 원본 저장소 객체 상태에 의존성이 남을 수 있고 주의가 필요하다고 문서가 경고한다.[10] 반면 worktree는 단일 저장소 내에서 공식적으로 다중 작업 트리를 지원하며 관리 명령이 통합돼 있다.[1]

따라서 스킬에는 선택 기준이 들어가야 한다.
- 같은 저장소에서 동시 브랜치 작업: worktree 우선
- 권한/원격/격리 요구가 강한 경우: 별도 clone 검토

**Sources:** [1], [10]

---

## Claims-Evidence Table
| Claim | Evidence | Confidence |
|---|---|---|
| 브랜치 동시 체크아웃에는 기본 안전장치가 있다 | `worktree add` 거부, `checkout/switch` 거부, 릴리즈 노트 규칙 강화 [1][3][4][11] | High |
| 수동 삭제/이동에 대비한 운영 명령이 필수다 | `prune`, `repair`, `lock`, `gc.worktreePruneExpire` [1][5][8] | High |
| per-worktree config가 스킬 핵심이다 | `extensions.worktreeConfig`, `config.worktree`, sparse-checkout 연계 [5][9] | High |
| 자동화는 `rev-parse` 기반 경로 해석이 안전하다 | `--git-dir`, `--git-common-dir`, `--git-path` + worktree details [1][7] | High |

---

## Synthesis & Insights
핵심 패턴은 "작업 디렉터리 다중화"가 아니라 "상태 분리와 공유 경계의 명시"다. worktree는 working tree 상태(HEAD/index/config 일부)를 분리하면서 저장소 본체를 공유한다.[1][6] 이 구조 때문에 사용자 실수는 주로 경계 위반에서 발생한다. 예를 들어 동일 브랜치 다중 점유를 강제로 허용하면 참조 이동/작업 디렉터리 상태가 분기되어 사고가 난다.[3][4][11]

또 하나의 패턴은 "명령 숙련도"보다 "운영 규약"의 중요성이다. 대부분 문제는 `add` 자체가 아니라 정리와 복구 단계(`remove` 누락, 수동 삭제, 이동 후 미복구)에서 생긴다.[1][5][8] 따라서 좋은 스킬은 커맨드 설명서가 아니라 runbook 형태(생성-작업-정리-복구)를 가져야 한다.

실행 가능한 설계 통찰:
- 스킬 본문은 기본 플로우를 짧게 유지하고, 위험 시나리오(우회 플래그, 수동 이동, 락/프룬 정책)는 별도 섹션으로 분리한다.
- 브랜치 점유 충돌 메시지는 실패가 아니라 보호장치로 해석하도록 문구를 설계한다.
- 팀 공통 정책(네이밍, 루트 디렉터리 규칙, prune 보존기간)을 스킬에서 강제하면 DRY/SSOT에 부합한다.

---

## Limitations & Caveats

### Counterevidence Register
- **Contradictory Finding:** `--ignore-other-worktrees`는 기술적으로 동일 ref의 다중 점유를 허용한다.[3][4]
  - Why it contradicts: "브랜치 1개=worktree 1개" 규칙을 깨는 예외다.
  - Resolution: 문서도 이를 기본이 아닌 예외 옵션으로 제시하므로, 정책상 제한적 허용이 타당하다.[3][4][11]
  - Impact: Moderate

### Known Gaps
- 본 연구는 대형 모노레포에서의 성능 측정(예: checkout latency)을 정량 비교하지 않았다.
- Windows 경로/권한 특이 케이스는 릴리즈 노트 일부 언급만 반영했고, 별도 실험 데이터는 없다.[12]

### Assumptions
- 팀이 Git 최신 버전군을 사용한다는 가정에 의존한다. (특히 v2.44 이후 안전장치 인식)[11]
- 스킬 사용자가 위험 플래그를 일관되게 통제한다는 운영 가정이 있다.

---

## Recommendations
1. 로컬 스킬의 기본 워크플로를 `add -> 작업 -> remove`로 고정하고, 수동 폴더 삭제를 금지한다.[1]
2. "브랜치 점유 충돌"을 정상 보호 동작으로 문서화하고, `--ignore-other-worktrees`/`--force`는 복구 절차 섹션에서만 노출한다.[1][3][4]
3. `extensions.worktreeConfig`와 `git config --worktree`를 기본 채택해 worktree별 설정을 분리한다.[5][9]
4. 스크립트 예제는 `git rev-parse --git-path/--git-common-dir` 기반으로 경로를 계산하게 한다.[7]
5. 정리 정책을 명문화한다: `git worktree prune`, `gc.worktreePruneExpire`, 이동식 경로는 `worktree lock --reason`.[1][5][8]
6. 스킬에 "worktree vs clone" 선택표를 넣어, 격리/권한 요구 시 clone 경로를 안내한다.[10]

---

## Bibliography
[1] Git Project (n.d.). "Git - git-worktree Documentation". https://git-scm.com/docs/git-worktree

[2] Git Project (n.d.). "Git - git-branch Documentation". https://git-scm.com/docs/git-branch

[3] Git Project (n.d.). "Git - git-checkout Documentation". https://git-scm.com/docs/git-checkout

[4] Git Project (n.d.). "Git - git-switch Documentation". https://git-scm.com/docs/git-switch

[5] Git Project (n.d.). "Git - git-config Documentation". https://git-scm.com/docs/git-config

[6] Git Project (n.d.). "Git - gitrepository-layout Documentation". https://git-scm.com/docs/gitrepository-layout

[7] Git Project (n.d.). "Git - git-rev-parse Documentation". https://git-scm.com/docs/git-rev-parse

[8] Git Project (n.d.). "Git - git-gc Documentation". https://git-scm.com/docs/git-gc

[9] Git Project (n.d.). "Git - git-sparse-checkout Documentation". https://git-scm.com/docs/git-sparse-checkout

[10] Git Project (n.d.). "Git - git-clone Documentation". https://git-scm.com/docs/git-clone

[11] Git Project (2024). "Git v2.44 Release Notes". https://raw.githubusercontent.com/git/git/master/Documentation/RelNotes/2.44.0.adoc

[12] Git Project (2024). "Git v2.45 Release Notes". https://raw.githubusercontent.com/git/git/master/Documentation/RelNotes/2.45.0.adoc

---

## Methodology
- Source retrieval: 공식 문서/릴리즈 노트를 `curl`로 직접 수집하고 핵심 문구를 라인 단위로 검증.
- Verification: 서로 다른 문서(`git-worktree`, `git-config`, `git-branch`, release notes) 간 교차 확인으로 주장 삼각검증 수행.
- Synthesis rule: 사실(문서 진술)과 해석(스킬 설계 제안)을 분리해 작성.
- Coverage: 기능, 안전장치, 운영, 설정, 자동화, 대안 비교까지 포함.
