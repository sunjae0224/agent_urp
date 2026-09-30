# agent_urp

Agent가 각 step(LLM 호출·tool 호출·memory 읽기/쓰기)의 읽기/쓰기를 기록해 두었다가, 편집 후 영향받은 step만 재실행하는 LLM agent runtime. 학부 연구학점제 팀 프로젝트(3명, 2026-08-31~2026-12-18).

## 원칙

1. **코드를 바꾸면 그 폴더의 CLAUDE.md를 같은 변경(같은 커밋)에서 갱신한다** — 무엇이 바뀌었는지, 어떻게 쓰는지, 다음에 할 일을 적는다. 코드와 CLAUDE.md가 어긋나기 시작하면 이 체계 전체가 무의미해진다.
2. **모든 CLAUDE.md는 50줄 이하**(빈 줄 포함)이고 상세는 하위 폴더 CLAUDE.md로 위임한다. `tests/test_claude_md.py`가 이를 강제한다 — CLAUDE.md를 추가/수정했으면 이 테스트도 통과해야 한다.
3. **TDD로 개발한다**: 실패하는 테스트를 먼저 쓰고 구현한다. `uv run pytest`와 `uv run ruff check .`가 모두 통과해야 그 작업을 "완료"라고 선언할 수 있다.
4. **커밋·푸시는 사용자가 명시적으로 지시할 때만** 한다. 새 커밋의 author는 `sunjae0224 <sunjae0224@gmail.com>`(전역 git config는 건드리지 않고 로컬 커밋에서만 지정한다).
5. **서브에이전트 위임은 sonnet/opus 모델로** 하고, 결과는 메인 세션이 검증한다. **설계를 바꿀 때는 먼저 `docs/superpowers/specs/`의 스펙 문서에 반영**한 뒤 코드를 고친다 — 코드가 스펙보다 앞서가지 않는다.

## 명령

- `uv sync` — 의존성 설치
- `uv run pytest -q` — 전체 테스트 실행
- `uv run ruff check .` — lint
- `uv run python -m agent_urp.eval.run_matrix` — S1/S5 시나리오 × 4개 정책 비교표 출력

## 폴더 지도

- agent_urp/ → agent_urp/CLAUDE.md
- tests/ → tests/CLAUDE.md
- docs/ → docs/CLAUDE.md
