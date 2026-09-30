# agent_urp/core/ — 데이터 모델 + 실행 엔진

## 역할

읽기/쓰기를 자동으로 기록하는 step 실행기(`runtime.py`)와 그 기반 자료구조(hash, model, 저장소, 의존성 그래프, 동등성, 정책)를 담는다. 이 패키지가 프로젝트의 핵심이다.

## 실행 모델 (요약)

- 프로그램은 편집마다 처음부터 다시 실행된다; 각 step 호출은 부모 run의 같은 `(name, occurrence)` 기록과 비교된다.
- **FULL**: 절대 재사용하지 않는다 — 항상 실행.
- **SUFFIX**: `old.seq < first_dirty_seq`면 위치만 보고 재사용(내용 무관, LangGraph time-travel과 동일 의미).
- **MEMO**: `key_static` + 현재 block/env 전체 버전의 해시(`state_hash`)가 정확히 같아야 재사용.
- **DEP**: `key_static` 일치 + 실제로 읽은 block/env 버전이 모두 현재와 같은지 검증(`verify`); 실패하면 현재 run과 그 조상 run들(lineage)에서 온 memo 후보 중 검증되는 것을 찾는다.
- **backdating**: DEP + Level ≥ L1에서만, 새 출력이 old 출력과 동등하면 old artifact를 그대로 채택(`equivalent_to`, early cutoff). 최종 판정은 REUSE/REBUILD/RERUN/LIVE(`Decision`) 중 하나.

## 파일별

- `hashing.py` — `canonical_json`(키 정렬 JSON) + `content_hash`(blake2b, 32 hex)
- `models.py` — `Artifact`/`Block`/`StepRecord`/`Edit`/`Run` 등 pydantic 모델과 `StepKind`/`Decision`/`Policy`/`SamplingIntent`
- `context.py` — `ContextAssembler`: block 이름 목록 → prompt 텍스트(`naive`/`stable_prefix` layout)
- `dep_graph.py` — `DepGraph`: StepRecord들에서 read/write 그래프 재구성, `readers_of`/`first_dirty_seq`/`dirty_from`
- `equivalence.py` — `equivalent(a, b, level)`: L0(artifact id 동일)/L1(공백·숫자·키 순서 정규화)
- `policies.py` — `choose_reuse(...)`: 정책별 재사용 결정 (아래 표)
- `trace_store.py` — `TraceStore`: SQLite에 artifact/block/env/run/edit/step/memo 저장
- `runtime.py` — `Runtime`/`StepContext`/`@step`: 실제 실행·기록·재사용을 전부 담당

## 정책 표

| 정책 | 재사용 조건 |
|---|---|
| FULL | 없음(항상 실행) |
| SUFFIX | `old.seq < first_dirty_seq`(위치만, 내용 무관) |
| MEMO | `key_static` + 전체 상태 해시 정확히 일치 |
| DEP | `key_static` + 실제 읽은 reads 버전 검증(현재 run 우선, 그다음 조상 run의 memo) |

## 바꿀 때 주의

- artifact 인자는 **파라미터 이름으로 키가 잡힌다**(`key_static`의 `artifacts` 필드) — 인자를 바꿔치기하면 다른 key가 된다.
- step 밖에서의 읽기(`ctx.block`/`ctx.env`)는 다음 step의 `orchestration_reads`가 된다 — DepGraph·SUFFIX는 보지만 DEP의 `_verify`는 보지 않는다(의도적 설계).
- step 안에서 env를 바꾸면 `EnvMutatedInStep`. orchestration 코드(step 밖)의 env mutate는 **막혀 있지 않다**(`VersionedEnv.set`이 공개 API) — 규약으로만 금지한다.
- step 결과와 `set_block` 내용은 JSON canonical 왕복을 거친다(tuple→list 등) — 실행 경로와 재사용 경로가 항상 같은 값을 돌려주게 하기 위함.
- `sampling_intent=fresh`인 step은 절대 재사용되지 않는다.

## 구현된 것 · 안 된 것

- 구현: L0/L1 동등성, DEP/SUFFIX/MEMO/FULL, backdating, memo의 lineage(현재 run + 조상 run) 스코프.
- 안 됨: `cost.py`(스펙 §7.2 비용 모델), 동등성 L2~L4(tool-call/임베딩/LLM-judge), env write를 기록해 DEP가 검증하게 하는 것, demand-driven skip(현재는 "프로그램이 안 부르면 안 돈다" 이상은 없음).
