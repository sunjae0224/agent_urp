# docs/ — 문서 지도

## 역할

설계·연구·학습·일정 문서. 코드에 대한 "왜"는 여기, "무엇을 어떻게 쓰나"는 각 폴더의 CLAUDE.md에 있다.

## 문서 지도

| 문서 | 내용 |
|---|---|
| `docs/superpowers/specs/2026-09-30-agent-urp-design.md` | **설계 스펙**(단일 진실 공급원) — 목표·문제 정의·접근법 비교·아키텍처·데이터 모델(§5)·실행 모델(§6, DEP/SUFFIX/MEMO/FULL·동등성 L0~L4)·context/cache 레이어(§7)·워크로드·시나리오·지표(§8)·테스트 전략·범위 밖·리스크·열린 질문. |
| `docs/superpowers/plans/2026-09-30-skeleton-v1.md` | v1 뼈대 구현 계획 — Task 1~8 각각의 파일·인터페이스·TDD 단계, Global Constraints, Review Focus. 맨 위 "실행 후 메모": 실행 중 판정(ledger)이 계획의 참조 코드보다 우선한다. |
| `docs/research-landscape.md` | 관련 연구 5개 분야 지도, 계획서 인용 검증, 최근접 선행 연구 2편 대조, 우리 기여·위협과 대응, 필독 논문, 프레임워크·벤치마크 판정. |
| `docs/study-guide.md` | 에이전트 경험 없는 팀원용 선행 학습 — 주차별 학습, 세미나 순서, 도구·개념 체크리스트. |
| `docs/roadmap.md` | 12/18까지 주차 계획, 팀 역할, GPU-free→GPU 확장 경로, 데모 체크포인트. |
| `docs/overview.html` | 연구 개요 artifact 페이지 원본(한국어, 논문 용어). Claude Code에서 `docs/overview.html`을 Artifact로 publish하면 그 세션 계정 소유로 생성됨. |

## 갱신 규칙

**설계를 바꿀 때는 코드보다 먼저 스펙(`docs/superpowers/specs/`)에 반영한다** — 새 스펙 파일을 추가하거나 기존 스펙에 절을 덧붙인다(기존 문장을 지우지 않는 한 옛 판단도 남긴다). 계획 변경은 `docs/superpowers/plans/`에 새 계획 파일로 남긴다. `research-landscape.md`/`roadmap.md`/`study-guide.md`는 스펙과 어긋나면 스펙을 기준으로 고친다.

## 하위 폴더

코드가 없는 하위 폴더에는 CLAUDE.md를 두지 않는다 — 그 안의 문서는 위 "문서 지도" 표에 있다.

- docs/superpowers/
