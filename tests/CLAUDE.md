# tests/ — 회귀 테스트

## 역할

`agent_urp`의 계약을 고정한다. `uv run pytest -q`로 전부 실행; `uv run pytest -k <이름>`으로 일부만.

## 파일별로 고정하는 것

- `test_hashing.py` — canonical JSON 키 정렬, model/enum/tuple/유니코드 처리, hash 안정성·32-hex·충돌 없음, 직렬화 불가 타입과 `str`이 아닌 dict 키에 TypeError(강제 변환 없음).
- `test_models.py` — Artifact/Block content-addressing, `Usage.__add__`, `StepRecord` JSON 왕복, `Edit.of`/`Run` 기본값.
- `test_context.py` — block 렌더링, naive 순서 유지+`[input]` 추가, stable_prefix가 durability로 안정 정렬, 잘못된 layout 이름 거부.
- `test_dep_graph.py` — `readers_of`/`first_dirty_seq`/`dirty_from`(artifact 경유 포함), `orchestration_reads`도 read로 잡힘, `to_dot`.
- `test_equivalence.py` — L0(id 동일)/L1(공백·숫자 정규화) 판정, L1도 kind는 구분.
- `test_policies.py` — `choose_reuse`: FULL은 항상 None, SUFFIX는 위치만, MEMO는 상태 해시 완전 일치, DEP는 old 우선·검증 실패시 memo.
- `test_trace_store.py` — artifact/block/env/run/edit SQLite 왕복, step이 seq순 정렬, memo 후보가 최신순, 파일 저장 지속성(`tmp_path`).
- `test_runtime.py` — record/replay 엔진 전체: 정책별 REUSE/RERUN/LIVE, `(name, occurrence)` 추적, 분기 후 위치 재사용·새 step LIVE·옮겨진 step의 memo 재사용, orchestration_reads의 SUFFIX-보임/DEP-무시, fresh(SUFFIX 위치 재사용·DEP 재샘플·memo 미등록), env mutate 금지, closure 금지(`ClosureNotAllowed`), ctx 상태 private, layout 가드·`Run.level`/`block_meta` 기록과 복원, parent만 준 SUFFIX의 입력 diff, L1 backdating, canonicalization(tuple/pydantic), swapped artifact 인자.
- `test_llm_scripted.py` — 첫 매칭 규칙 승리, 단어 수 usage, Protocol 준수.
- `test_llm_cassette.py` — auto/record/replay 3모드, params 다르면 다른 키, 디스크 영속, replay 미스시 예외, 손상 파일 ValueError, `.tmp`+`os.replace` 원자적 저장.
- `test_tools.py` — VersionedEnv 버전·경로 get/set·snapshot/restore, dict 아닌 중간 경로 set은 ValueError(state 불변), search 랭킹, db_query 필터.
- `test_trip_planner.py` — S1 end-to-end: 예산 2000→Ocean Grand, 1200(또는 `1,200`)→Seaside Suites, no-op 재표현은 pick_hotel만 RERUN; 예산 없음·`[input]` 없음·항공편 없음은 명확한 ValueError.
- `test_metrics.py` — `audit`: 컨테이너(dict/list) 안의 artifact도 내용으로 비교, `matches_full`은 주어진 level로 판정(L1 공백 차이).
- `test_run_matrix.py` — S1/S5의 정확한 executed/over_rerun/llm_calls 수치, CLI 출력, `run_scenario`가 level을 audit에 전달, 모르는 시나리오/정책/layout 거부(유효 이름 나열), `--db` 부모 폴더 생성.
- `test_claude_md.py` — 이 문서 체계 자체: `.py` 있는 모든 폴더에 CLAUDE.md 존재, 전부 50줄 이하, 루트에 갱신 규칙 언급.

## 규칙

새 모듈을 추가하면 같은 PR/커밋에서 `test_<module>.py`를 새로 만든다(기존 파일에 얹지 않는다). 테스트는 `ScriptedLLM`과 `:memory:` `TraceStore`를 기본으로 쓰고 네트워크는 쓰지 않는다. 파일이 필요한 테스트(trace_store 지속성, cassette, run_matrix `--db`)는 pytest `tmp_path` 안에서만 읽고 쓴다.
