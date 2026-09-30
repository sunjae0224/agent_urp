# agent_urp 설계 스펙 — LLM Agent 의존성 기반 선택적 재실행 Runtime

- 작성일: 2026-09-30 (연구기간 2026-08-31 ~ 2026-12-18, 남은 기간 약 11주)
- 상태: **v1 skeleton 구현 반영 (2026-09-30)**. 구현 계획은 `docs/superpowers/plans/2026-09-30-skeleton-v1.md`이고, 구현 중 내려진 판정은 §2(v1 주의)·§4·§5·§6·§8.3에 반영했다. §13 열린 질문은 여전히 사용자 결정 대기.
- 관련 문서: [research-landscape.md](../../research-landscape.md) (관련 연구·차별화), [study-guide.md](../../study-guide.md) (선행 학습), [roadmap.md](../../roadmap.md) (주차 계획)

---

## 1. 우리가 이해한 목표 (검토 요청)

### 1.1 사용자가 말한 것 (계획서 + 대화)

- LLM 호출, tool call, 중간 결과, memory, context block 사이의 **의존성을 기록**하고, 무언가 바뀌었을 때 **영향받은 단계만 무효화·재실행**하는 prototype을 만든다.
- 변경 시나리오: 사용자 조건 수정, tool 실패·결과 변경, memory 교정.
- 비교 대상: full rerun, suffix rerun.
- 측정: task success, stale reuse, LLM·tool 호출 수, 입력 token, prefill 시간, TTFT, 전체 실행 시간, GPU 메모리.
- 계획서를 100% 따를 필요는 없다. 규모가 있어도 된다. **당장은 GPU 없는 환경**에서 시작하고 나중에 확장한다.
- 결과물: runtime prototype + 수정·실패 시나리오 workload + 성능 분석 보고서.

### 1.2 우리가 추가로 가정한 것 (틀리면 고쳐 주세요)

- **A1.** 프로토타입 에이전트는 우리가 직접 작성하는 3~8단계 tool-using 에이전트다. 실제 서비스 에이전트(Claude Code, SWE-agent 등)를 그대로 올리는 것은 범위 밖이다.
- **A2.** "정확성"의 기준은 *같은 편집을 가한 full rerun의 결과*다. 우리 runtime의 결과가 full rerun과 (의미적으로) 같으면 정확하고, full rerun이라면 바뀌었을 결과를 옛 값으로 재사용했으면 "stale reuse"다.
- **A3.** 12월 결과물은 (i) 동작하는 runtime 라이브러리 + CLI, (ii) 재현 가능한 실험 스크립트와 결과, (iii) 보고서(워크숍 논문 수준의 구조)다. 논문 투고 자체는 목표가 아니지만 그 형식을 따라 쓴다.
- **A4.** GPU 단계(vLLM Automatic Prefix Caching 실측)는 **선택적 확장**이다. 핵심 주장(호출 수·token·비용 절감, 정확성 유지)은 GPU 없이 API 기반으로 입증하고, TTFT/prefill 실측은 4090이 가능해지면 붙인다.
- **A5.** 팀 3명이 병렬로 일할 수 있도록 컴포넌트 경계를 나눈다 (runtime core / workload·eval / context·cache layer).

### 1.3 성공 기준 (12월 중순)

| 기준 | 목표 |
|---|---|
| 정확성 | 6개 시나리오 × N회 반복에서 full rerun 대비 task success 저하 ≤ 2%p, stale reuse rate 측정·보고 (목표 0, 의미적 cutoff 사용 시 정량 보고) |
| 효율 | suffix rerun 대비 LLM 호출 수·입력 token 유의미 감소 (시나리오별로 다르며, "부분 의존" 시나리오에서 30% 이상, no-op 편집 시나리오에서 90% 이상이 목표) |
| 재현성 | 기록된 LLM 응답(cassette)만으로 GPU·API 없이 전체 실험 재생 가능, `pytest` 통과 |
| 확장성 | 동일 코드가 API 백엔드(Anthropic/OpenAI)와 vLLM 백엔드(OpenAI 호환 서버)에서 실행되고, prefix cache 관련 지표(cached tokens, 나중엔 TTFT)를 같은 스키마로 기록 |

---

## 2. 문제 정의 (정확히)

에이전트 실행은 step의 시퀀스(일반적으로 DAG) `s_1 … s_n` 이다. step 종류:

- **LLM step**: context block 집합을 읽고 artifact(텍스트, tool-call 결정, 계획)를 만든다.
- **Tool step**: 인자 artifact + 외부 상태(검색 인덱스, DB, 파일)를 읽고 결과 artifact를 만든다. 부작용(파일/DB 쓰기)은 외부 상태 artifact에 대한 write로 기록한다.
- **Memory step**: memory store 항목을 읽거나 쓴다.
- **Assemble step**: 여러 block/artifact를 결정적으로 합쳐 prompt나 중간 결과를 만든다 (LLM·tool 호출 없음).

> **v1 주의(구현 제약)**: tool의 env 부작용(파일/DB 쓰기)은 v1에서 **기록하지 않는다**. step 안에서 env를 바꾸면 runtime이 실행 전후 env 버전을 비교해 `EnvMutatedInStep`을 던진다. orchestration 코드(step 밖)도 env를 바꾸면 안 된다 — 이는 규약이고 v1은 강제하지 않는다(`VersionedEnv.set`은 공개 API). env write의 기록·검증은 후속 계획이다.

**편집(edit)** 은 source 노드의 변경이다: 사용자 조건 block, tool의 외부 결과(환경 변경·실패로 모사), memory 항목, system prompt/tool schema.

**목표**: 편집 후 full rerun이 만들었을 trajectory와 같은 결과를, 가능한 한 적은 step만 실행해서 만든다.

**핵심 관찰 (설계를 지배하는 사실)**:

1. *prompt에 들어있다 ≠ 의미적으로 의존한다.* memory block이 모든 prompt에 들어가면, memory 교정은 보수적으로 모든 LLM step을 dirty로 만든다 → suffix rerun과 다를 게 없다. 정밀한 의존성은 **runtime이 context 조립을 통제해서 step마다 필요한 block만 넣을 때** 생긴다. 따라서 "선택적 context 조립"은 부가 기능이 아니라 이 연구의 전제다.
2. *에이전트 그래프는 동적이다.* 재실행된 LLM step이 다른 tool을 고르면 하위 구조가 바뀐다. 그래프 기반 재사용은 구조가 유지되는 부분에만 적용되고, 구조가 갈라진 뒤에는 **content-addressed memoization**(같은 tool+인자, 같은 prompt bytes → 기록된 결과 재사용)이 남은 재사용 수단이다.
3. *재실행 비용은 token 수가 아니라 캐시되지 않은 token 수에 비례한다.* prefix cache(vLLM APC, API prompt caching)가 있으면 편집 지점 앞의 prompt는 싸다. 그래서 "무엇을 재실행할지"뿐 아니라 "재실행할 prompt를 어떤 순서로 조립할지"가 비용을 좌우한다.
4. *dirty ≠ 재계산.* 편집으로 더러워진 step이라도 최종 결과(답변, 사용자에게 보이는 artifact, 커밋되는 memory)가 요구하지 않으면 다시 돌릴 이유가 없다 (Adapton의 demand-driven 원칙). 재실행은 "요구된 출력의 조상" 안에서만 일어난다.
5. *트리거는 세 종류다.* 실제 에이전트 trace에서 prefix cache를 깨는 패턴은 (a) 이전 내용 편집, (b) tool 결과 삽입, (c) context 재배열로 분류된다 ("Don't Break the Cache", arXiv:2601.06007). 우리 편집 시나리오와 layout 정책은 이 세 축으로 정리한다.

---

## 3. 접근법 비교와 결정

| | A. LangGraph 위에 구현 | **B. 얇은 자체 runtime (권장)** | C. 자체 runtime + LangGraph 어댑터 |
|---|---|---|---|
| 개요 | LangGraph checkpointer/node cache를 확장해 의존성 추적 | step을 read/write 선언이 있는 Python 함수로 정의하는 ~1k LOC 커널 | B를 만든 뒤 LangGraph 노드를 래핑해 올림 |
| 장점 | 생태계·튜토리얼, time-travel(=suffix rerun) 베이스라인 무료, "실제 프레임워크에서 동작" 설득력 | 완전한 통제, build-system 관점으로 깔끔하게 형식화, 테스트 쉬움, GPU-free | 둘의 장점 |
| 단점 | 노드가 전체 state를 받아 read set이 숨겨짐, 동적 그래프·버전 변화, 내부와 싸우게 됨, 논문에서 설명 어려움 | 베이스라인 직접 구현(쉬움), "장난감 에이전트" 비판 가능 | 작업량 최대 |
| 판단 | 학습용 + **suffix rerun 베이스라인의 독립 구현체**로만 | **채택** | Phase 2가 일찍 끝나면 stretch |

**결정**: B. 조사 결과(연구 지도 §5) LangGraph의 상한은 "토폴로지 인식 suffix rerun + 노드 입력 pickle 해시 기반 memo(`CachePolicy`)"이고, 노드별 read/write 명세·코드 버전 반영·값 기반 early cutoff가 없어 핵심 메커니즘은 어차피 새로 짜야 한다. LangGraph는 (1) 팀 학습, (2) **같은 step 함수를 `StateGraph`로 감싸 time-travel fork로 돌리는 suffix rerun 베이스라인**(우리 구현과 교차 검증), (3) 선택적으로 `Store` API를 memory 저장소로만 쓴다. Week 3 체크포인트에서 자체 코어가 크게 밀리면 LangGraph `CachePolicy`에 content-hash `key_func`를 끼우는 것이 비상 대안이다.

---

## 4. 아키텍처

```
┌──────────────────────────────────────────────────────────────────┐
│ agent programs (workloads/)  : trip_planner, research_pipeline… │
│   step 함수 = @step(kind=...)  (reads/writes는 실행 중 자동 기록)  │
└───────────────┬──────────────────────────────────────────────────┘
                │ step 호출
┌───────────────▼──────────────────────────────────────────────────┐
│ runtime core (agent_urp/core)                                    │
│  Runtime(program 재실행) ── policies.choose_reuse + backdating    │
│     │              │                                             │
│  ContextAssembler  │   Memo(constructive trace: key_static→기록) │
│     │              ▼                                             │
│  TraceStore (SQLite): Artifact / Block / StepRecord / Edit       │
│  DepGraph (NetworkX, TraceStore에서 재구성)                      │
└───────┬──────────────────────────┬───────────────────────────────┘
        │ LLM 호출                  │ tool 호출
┌───────▼───────────┐    ┌─────────▼───────────┐
│ llm backends      │    │ tools (mock)        │
│  scripted / cassette│   │  search / db / file │
│  anthropic / openai │   │  env snapshot 버전   │
│  vllm (OpenAI 호환) │   └─────────────────────┘
│  + usage/cache 지표 │
└───────────────────┘
        ▲
┌───────┴────────────────────────────────────┐
│ eval (agent_urp/eval): scenarios, edits,   │
│  baselines(FULL/SUFFIX/DEP), metrics, plots│
└────────────────────────────────────────────┘
```

컴포넌트별 "무엇을 하나 / 어떻게 쓰나 / 무엇에 의존하나":

| 컴포넌트 | 역할 | 인터페이스 | 의존 |
|---|---|---|---|
| `TraceStore` | 모든 artifact·block 버전·env snapshot·run·편집·step 기록을 append-only로 저장, memo 색인 | `put/get_artifact`, `put/get_block`, `put/get_env_snapshot`, `put/get_run`, `put/get_edit`, `record_step`/`get_steps`, `memo_put(rec)`/`memo_candidates(key_static)` (`new_version` 없음) | SQLite |
| `DepGraph` | run의 의존성 그래프 (block/env/artifact → step → artifact/block, orchestration_reads 포함) | `readers_of(name)`, `first_dirty_seq(names)`, `dirty_from(names)`, `to_dot()` (`topo_order` 없음) | NetworkX, StepRecord |
| `ContextAssembler` | step이 넘긴 block 이름 목록으로 prompt 조립, **layout 정책** 적용 (`naive` / `stable_prefix`: durability 순 안정 정렬) | `assemble(blocks, extra) -> Prompt` | models(Block) |
| Memo | constructive trace — 별도 클래스 없음: `key_static`으로 색인한 StepRecord 후보(최신순) 중 reads가 검증되는(DEP) / `state_hash`가 같은(MEMO) 기록을 재사용. 검색 범위는 현재 run + 조상 run | `TraceStore.memo_put`/`memo_candidates(key_static)` + runtime의 lineage 필터 | TraceStore |
| `policies` | 정책(FULL/SUFFIX/MEMO/DEP)별로 "이 step 호출을 어떤 기록으로 재사용할 수 있나" 판정 | `choose_reuse(policy, key_static, old, first_dirty_seq, memo_candidates, verify, state_hash) -> StepRecord \| None` | DepGraph, TraceStore |
| `Equivalence` | pluggable 동등성 oracle: exact / normalized / toolcall-canonical / embedding / llm-judge (v1은 L0·L1만) | `equivalent(a, b, level) -> bool` | 선택적으로 LLM backend |
| `Runtime` | 워크로드 프로그램을 실행·재실행하며 step 호출마다 REUSE/REBUILD/RERUN/LIVE 결정, 동등성 backdating, 기록 | `run(program, blocks, envs, policy, parent_run=None, edit=None)`, `replay(program, parent_run_id, edit, policy)` (부모 run과 layout이 다르면 `ValueError`) | 위 전부 |
| `LLMBackend` | 통일된 호출 + usage(입력/출력/cached token) 기록 | `complete(prompt, params) -> LLMResponse{text, usage}` | provider SDK |
| `CostModel` | 예상 비용(uncached prefill, decode) 계산, probe 여부·layout 선택에 사용 (v1 미구현, 후속 `cost.py`) | `estimate(prompt, cache_state)` | tokenizer, 실측 usage |

---

## 5. 데이터 모델

모두 content-addressed (blake2b). 저장은 SQLite 테이블 + JSONL export.

```
Artifact   { id=hash(kind, content), kind: text|toolcall|toolresult|json (v1: 만든 step의 kind), content, created_by: step_id|null }
Block      { name (system, tools, goal, constraint.budget, memory.units, history.3, doc.2 …),
             version=hash(content), content, kind: static|user|memory|derived, derived_from: [artifact_id],
             durability: high|medium|low }   # Salsa식 등급: system/tools=high, 문서·memory=medium, 방금 편집된 조건=low
StepRecord { id, run_id, seq, name, occurrence(같은 name의 몇 번째 호출), kind: llm|tool|memory|assemble,
             key_static = hash(name, kind, code_version, {artifact 인자 이름: id}, 일반 인자값),   # §6.2
             reads: [(block_name, version) | artifact_id | env_id@version],
             orchestration_reads: [직전 step 이후 program(step 밖)이 읽은 block/env 버전],
             params: {args, state_hash, llm: [{blocks, params(model, temperature, seed…)}]},
             sampling_intent: stable|fresh,
                     # fresh = self-consistency처럼 일부러 독립 샘플을 원하는 호출 → MEMO/DEP 재사용 금지, memo에 넣지 않음
             code_version: hash(step 함수 자신의 소스),   # Dagster의 code_version (helper 함수는 포함 안 됨, §6.1)
             input_hash = hash(key_static, reads),        # Dagster의 data_version; 인자는 key_static(args)에, llm params는 params에
             writes: [artifact_id | (block_name, new_version)],
             usage: {input_tokens, output_tokens, cached_tokens, latency_ms, ttft_ms?},
             decision: REUSE|REBUILD|RERUN|LIVE, equivalent_to: step_id|null, reused_from: step_id|null }
Edit       { id, kind: constraint|tool_result|memory|system, target, target_kind: block|env, content,
             old_version, new_version }
Run        { id, parent_run_id, edit_id, policy: FULL|SUFFIX|MEMO|DEP, layout: naive|stable_prefix, level: 0|1,
             initial_blocks: {name: version}, initial_envs: {name: version},
             block_meta: {name: {kind, durability}}, metrics }
```

- **verifying trace** = StepRecord의 `reads` 버전 목록. "모든 read 버전이 현재와 같으면 up-to-date".
- **constructive trace** = `Memo[key_static] → StepRecord 후보`(최신순). DEP는 후보의 reads가 현재 버전으로 검증되면, MEMO는 `state_hash`가 같으면 재사용한다. 검색 범위는 현재 run + 조상 run이다(형제 replay끼리는 공유하지 않는다). 편집을 되돌리면(undo) 즉시 복원되고, 구조가 갈라진 뒤에도 같은 tool 호출을 재사용한다.
- **Run의 layout·level·block_meta**: `layout`은 run을 만든 assembler의 layout, `level`은 runtime의 동등성 수준이다. `replay`(와 `run(parent_run=…)`)를 부모 run과 layout이 다른 runtime에서 부르면 아무것도 저장하기 전에 `ValueError`다(prompt 바이트가 달라져 정책 비교가 무의미해진다). 초기 block의 kind/durability는 run마다 `block_meta`에 저장해 replay 때 그대로 복원한다 — store의 block 행은 (name, version)마다 처음 들어온 메타데이터만 남기 때문이다. 같은 이유로 재사용된 step의 block write도 `set_block`과 같은 규칙(현재 run의 같은 이름 block의 kind/durability, 없으면 derived/medium)으로 다시 만든다.
- 외부 상태(mock DB, 검색 인덱스, 파일)는 `env_id@version` 노드다. tool 결과 변경 시나리오는 env 버전을 올려서 모사한다.

---

## 6. 실행 모델

### 6.1 기록 (첫 실행)

워크로드는 `program(ctx)` 형태의 **결정적 Python 함수**(orchestration)이고, 비용이 드는 일은 전부 `@step(kind=...)`로 감싼 함수 호출로만 일어난다. step 함수는 `ctx.block(name)` / `ctx.env(name)` / `ctx.llm(blocks=[...], extra=...)` 로만 상태에 접근하므로 **read set이 실행 중 자동으로 발견·기록**된다(선언 누락 위험 없음; 같은 step이 방금 쓴 block을 다시 읽는 것은 read로 치지 않는다). LLM step의 prompt는 `ContextAssembler`가 block 이름 목록으로 조립한다(직접 문자열 결합 금지). 인자로 받은 artifact는 정적 read이고, 반환값은 content-addressed artifact가 된다. 실행 후 StepRecord를 남기고 Memo(constructive trace)에 넣는다(`sampling_intent=fresh` step의 기록은 넣지 않는다).

**값 정규화**: step 반환값, `set_block` 내용, run 입력(초기 block 내용·env 상태)은 모두 JSON canonical 왕복(`json.loads(canonical_json(x))`: tuple→list, pydantic 모델→dict, dict 키는 `str`만 허용)을 거친다 — 실행 경로와 재사용 경로가 항상 같은 값을 돌려주게 하기 위함이다.

**step 순수성 규약**: step의 결과는 **kwargs와 `ctx.block`/`ctx.env`/`ctx.llm` 읽기에만** 의존해야 한다 — program 지역 변수에 대한 closure, 전역 변수, 파일, 시계 금지. runtime은 step 함수의 closure 중 함수·클래스가 아닌 값(= program 지역 값)을 발견하면 `ClosureNotAllowed`로 거부한다(전역·파일·시계는 규약으로만 금지). `code_version`은 step 함수 **자신의 소스만** 해시하므로 step이 부르는 helper 함수를 고쳐도 기존 기록이 무효화되지 않는다 — helper를 바꾸면 새 base run부터 다시 기록한다.

### 6.2 편집 → 재실행: 프로그램 재실행 + trace 검증 (Temporal식 replay)

편집 후 runtime은 (1) 원 run의 초기 상태(block·env 버전)를 복원하고 편집을 적용한 뒤 (2) **프로그램을 처음부터 다시 실행**한다. orchestration은 싸고, 각 step 호출에서만 아래를 판정한다:

```
key_static = hash(step name, kind, code_version, {artifact 인자 이름: id}, 일반 인자값)   # 인자 이름 포함: 인자 교환을 구분
old        = 원 run에서 같은 (name, 등장 순서)의 기록   # 없으면 제어 흐름이 갈라진 것 → LIVE
DEP:
  0. sampling_intent=fresh → 재사용하지 않고 바로 3 (MEMO도 동일)
  1. verifying trace : old.key_static == key_static 이고 old.reads의 block/env 버전이 모두 현재와 같으면
                       → REUSE (함수 실행 없이 기록된 writes 적용)
     orchestration_reads는 검증하지 않는다: program이 읽은 값은 kwargs로만 step에 들어가고 kwargs는 key_static에
     들어 있으므로 값이 바뀌면 key가 달라진다(분기가 바뀌면 (name, 순서)가 달라진다). 값이 closure로 새는 경로는
     §6.1의 closure 금지가 막는다.
  2. constructive trace(Memo): 같은 key_static의 다른 기록 중 reads가 검증되는 것이 있으면 → REUSE
     (검색 범위는 현재 run의 조상 run들 — 같은 편집의 형제 replay끼리는 서로 재사용하지 않아 정책별 결과가 실행 순서와 무관)
  3. 실행: assemble → REBUILD, llm/tool → RERUN (old 없으면 LIVE)
  4. backdating(early cutoff): old가 있고 새 출력이 old 출력과 동등(6.3)하면 old artifact를 반환·기록(equivalent_to)
     → 하위 step은 같은 artifact id를 인자로 받으므로 1에서 자연히 REUSE된다
SUFFIX: 원 run에서 편집 대상 block/env를 처음 읽은 step의 seq 이전이면 위치(name, 순서)만으로 REUSE, 이후 전부 실행
        (LangGraph time-travel의 선형 판; 대상을 아무도 안 읽었으면 전부 REUSE)
        "읽음"에는 step의 reads와 orchestration_reads(그 step 직전에 program이 읽은 것)가 모두 들어간다.
        편집 대상 = edit.target ∪ 초기 버전이 부모와 다른 block/env 이름(edit 없이 parent_run만 줘도 동작한다).
        sampling_intent=fresh step도 위치로 REUSE한다(checkpoint-fork 의미론: fork 이전 샘플은 그대로 — LangGraph와 동일).
MEMO  : LangGraph CachePolicy 모사 — key = hash(name, code_version, 인자, 전체 현재 상태(모든 block·env 버전))가
        정확히 같은 기록이 있을 때만 REUSE (fresh step은 재사용하지 않는다)
FULL  : 항상 실행
```

L0 동등성은 content-addressed id 덕분에 자동이다(같은 내용 → 같은 id → 하위 key_static 동일). 편집 undo는 원 버전으로 되돌아가므로 즉시 전부 REUSE된다. demand-driven(관찰 4)은 이 모델에서는 "프로그램이 호출하지 않는 step은 애초에 실행되지 않는다"로 실현되며, 요구되지 않는 분기의 명시적 skip은 후속 과제다.

### 6.3 동등성 oracle과 stale-risk

| 수준 | 방법 | 적용 대상 | 위험 |
|---|---|---|---|
| L0 | 바이트 동일 | 전부 | 없음 |
| L1 | 정규화(공백, JSON canonical, 숫자 포맷) | tool 인자, 구조화 출력 | 거의 없음 |
| L2 | tool-call canonical (같은 tool, 같은 인자 집합) | LLM의 tool 결정 | 낮음 |
| L3 | 임베딩 cosine ≥ τ (CPU sentence-transformers) | 자유 텍스트 요약 | 중간 |
| L4 | LLM-judge ("하위 step 관점에서 같은가?") | 자유 텍스트 | 중간, 비용 있음 |

실험 변수: cutoff 수준(L0~L4)에 따른 (절감량, stale reuse rate) 곡선. 이것이 "semantic early cutoff"의 정량 근거가 된다.

### 6.4 비결정성

- 재실행 시 temperature 0 + seed(지원 provider). 그래도 다를 수 있으므로 시나리오당 N≥5회 반복, 평균·분산 보고.
- 정확성 판정은 "full rerun 결과와의 동등성"과 "task 정답 대비 success" 둘 다 보고한다.
- **stale reuse 판정**: 시나리오 설계 시 편집이 *정답으로* 영향을 주는 step 집합 `G`를 명시한다 (mock tool·task를 우리가 만드니 알 수 있다). 우리 runtime이 `G`의 step을 REUSE 했으면 stale reuse.

---

## 7. Context·cache 인지 레이어 (차별화의 핵심)

### 7.1 Block layout 정책

prompt = `[system][tools][memory.*][goal][constraint.*][history…][step-local]` 처럼 **변동성이 낮은 block이 앞에** 오도록 조립한다. 편집으로 어떤 block이 바뀌면, 그 block 이후 token만 캐시 미스가 난다. 정책은 pluggable (`naive`, `stable_prefix`, 나중에 `cost_optimal`).

### 7.2 비용 모델

```
cost(llm step) ≈ c_pre·(uncached prefill tokens) + c_hit·(cached tokens) + c_dec·(output tokens)
```

- GPU-free 단계: `c_*`는 API 가격표(Anthropic: cache read 0.1×, cache write 1.25× (5분 TTL) / 2× (1시간); OpenAI: cache read는 모델별 0.1~0.5× — 실행 시점 문서로 확정)와 provider가 돌려주는 실측 필드로 검증한다: Anthropic `usage.cache_read_input_tokens` / `cache_creation_input_tokens`, OpenAI `usage.prompt_tokens_details.cached_tokens`. **API prompt caching은 GPU 없이 prefix cache 동작을 실측하는 수단**이다.
- **Anthropic의 명시적 `cache_control` breakpoint(최대 4개, tools → system → messages 계층)는 통제 실험 도구다.** "tools 수정 / system 수정 / n번째 message 수정"을 각각 가해서 어느 계층부터 다시 과금되는지 읽어내면, 우리 DepGraph 무효화 결과와 1:1로 대조할 수 있다.
- **캐시 최소 토큰 제약**: breakpoint 앞 prefix가 모델별 최소 길이(Sonnet급 1,024 / Haiku 4.5 4,096 등, 문서 확인)보다 짧으면 캐시가 *조용히* 무시된다(`cache_*_tokens == 0`). 따라서 워크로드의 stable prefix(system + tool 스키마 + memory)는 현실적인 길이(≥ 2k tokens)로 설계하고, 캐시 실험은 최소 길이가 낮은 모델로 돌린다.
- GPU 단계: vLLM APC 켜고 TTFT·prefill 시간·cache hit 지표(`vllm:prefix_cache_hits_total` / `vllm:prefix_cache_queries_total`, `/metrics`)를 같은 스키마에 기록한다. `--enable-prefix-caching` 기본값은 문서가 서로 달라 **첫 실행에서 hit counter로 직접 확인**한다.

### 7.3 정책 결정에 쓰는 곳

1. **probe 결정**: dirty step 하나를 RERUN 해서 동등성이 나오면 하위 cascade를 막을 수 있다. probe 비용(캐시 덕에 싸다면)과 막을 수 있는 cascade 비용을 비교해 probe 순서를 정한다.
2. **layout 선택**: 여러 RERUN step이 prefix를 공유하도록 조립 순서를 고른다.
3. 비교 축: §8.3의 베이스라인(FULL / SUFFIX / SUFFIX-LG / MEMO-only / DEP) 각각에 cache 유무, DEP에는 layout 정책(naive / stable_prefix)을 곱한다.

---

## 8. 워크로드·시나리오·지표

### 8.1 시나리오 (v1, 모두 mock tool + API/스크립트 LLM)

| ID | 워크로드 | 편집 | 기대 동작 |
|---|---|---|---|
| S1 | 여행 계획 (항공/호텔/날씨 tool, 예산 constraint) | 예산 constraint 변경 | 날씨·항공 step REUSE, 호텔 선택·최종 계획 RERUN |
| S2 | 리서치 파이프라인 (search → fetch×3 → 요약×3 → 종합 → 포맷) | 소스 1개 내용 변경 (env 버전 up) | 해당 요약 + 종합 + 포맷만 RERUN |
| S3 | 사무 작업 (DB 조회 + 파일 작성, memory: 단위·언어 선호) | memory 교정 (단위 변경) | 포맷 step만 RERUN |
| S4 | S2 변형: fetch 하나 실패 → 재시도 시 다른 결과 | tool 실패/결과 변경 | S2와 같은 경로, 실패 처리 포함 |
| S5 | S1 변형: constraint를 같은 뜻으로 재표현 | no-op 편집 | probe 1회 후 전부 cutoff (호출 90%↓) |
| S6 | S1 변형: 편집이 다른 tool 선택을 유발 | control flow 분기 | LIVE 전환, 같은 검색은 Memo 재사용 |

시나리오는 템플릿 + 시드로 각 10~20 인스턴스 생성한다. **모든 시나리오는 "재실행되면 안 되는 control step"과 "반드시 재실행돼야 하는 step 집합 G"를 명시**한다 — 이것이 stale reuse와 과잉 재실행을 둘 다 채점하는 근거다. 여유가 있으면 두 템플릿을 추가한다: S7 코드 수정+테스트 실패(mock `run_tests`), S8 주문 처리 중 배송 옵션 번복. 외부 타당성 앵커로는 BFCL v3 multi-turn(Apache-2.0, "Missing Functions/Parameters"가 우리 트리거와 대응)과 ToolSandbox(Apple 자체 라이선스, "State Dependency" 분류)의 tool 스키마·시나리오 몇 개를 이식한다. τ²-bench는 MIT지만 주입 지점을 만들려면 하네스 포크가 필요해 후순위.

### 8.2 지표

호출 수(LLM/tool), 입력·출력·cached token, 예상 비용($), wall time, task success(정답 대비), full-rerun 동등성, stale reuse rate, (GPU) TTFT·prefill·GPU 메모리.

### 8.3 베이스라인

- **FULL**: 전부 재실행, memo 없음.
- **SUFFIX**: 편집 영향 지점 이후 전부 재실행 (자체 구현). **SUFFIX-LG**: 같은 step 함수를 LangGraph `StateGraph`로 감싸 time-travel fork로 돌린 독립 구현 — 두 결과가 같아야 한다(교차 검증).
- **MEMO-only**: 그래프 추적 없이 `key_static` + **전체 상태 키**(`state_hash` = 모든 block·env 버전)가 같으면 재사용 — LangGraph `CachePolicy` 의미론(노드 입력 = 전체 state). DEP와의 차이가 "의존성 그래프 + early cutoff"의 순수 기여다. prompt 바이트를 키로 하는 LLM-cache 베이스라인(LangChain LLM cache·DSPy식, LLM 호출만 캐시)은 후속으로 추가한다 — 키가 달라 v1 MEMO와는 별개의 베이스라인이다.
- **DEP**(ours) 및 +cache, +cache+layout 변형.

---

## 9. 테스트 전략

- **scripted LLM**: 테스트용 결정적 백엔드 (prompt 패턴 → 응답 규칙). 단위 테스트는 API 없이 돈다.
- **cassette**: 실제 API 응답을 `(input_hash → response)`로 기록·재생. CI와 재현 실험의 기반.
- **속성 테스트**: 결정적 LLM 하에서 `DEP(run, edit) == FULL(run, edit)` (출력 동일), `no-op 편집 → 호출 0~1회`, `편집 undo → 원 결과 즉시 복원`.
- **stale audit**: 시나리오의 `G` 집합과 REUSE 결정 대조.
- TDD로 진행 (superpowers:test-driven-development).

---

## 10. 저장소 구조와 스택

```
agent_urp/
  agent_urp/core/      hashing.py  models.py  trace_store.py  dep_graph.py  context.py  equivalence.py  policies.py  runtime.py  (후속: cost.py)
  agent_urp/llm/       base.py  scripted.py  cassette.py  (후속: anthropic.py  openai_compat.py — vLLM 겸용)
  agent_urp/tools/     env.py (버전 있는 mock 환경)  search.py  db.py  (후속: files.py)
  agent_urp/workloads/ trip_planner.py  (후속: research_pipeline.py  office_task.py)
  agent_urp/eval/      scenarios.py  metrics.py  run_matrix.py  (후속: plots.py)
  tests/
  docs/
```

스택: Python 3.11+, uv, pytest, pydantic, SQLite, NetworkX, blake2b, tiktoken/provider usage, sentence-transformers(CPU), Anthropic·OpenAI SDK, LangGraph(베이스라인·학습 전용), 나중에 vLLM(OpenAI 호환 서버, RTX 4090, Qwen2.5-7B-Instruct AWQ 급). cassette는 직접 만든다 — LLM용 VCR 라이브러리(pytest-llm-vcr 등)는 2026-09 기준 성숙하지 않고, `hash(정규화 요청) → 응답` 저장이면 충분하다. 관찰 가능성은 자체 TraceStore로 충분하며 Langfuse/OTel은 붙이지 않는다(YAGNI; 이들 span tree는 호출 트리이지 데이터 의존성 그래프가 아니다). 검토했으나 채택하지 않은 대안: PydanticAI `pydantic_graph`(타입 그래프 + durable execution 연동은 좋지만 편집 인식 무효화는 없음), DSPy(SHA256 full-request 캐시 패턴만 차용).

---

## 11. 범위 밖 (YAGNI)

- 멀티에이전트·병렬 실행, 실서비스 에이전트 이식, 웹 UI, LangGraph 어댑터(stretch), KV cache 내부 조작(CacheBlend류 재구현), 학습 기반 의존성 예측.

## 12. 리스크와 대응

| 리스크 | 대응 |
|---|---|
| 숨은 의미 의존성 → stale reuse | 보수적 read(선언 누락 시 prompt에 들어간 모든 block을 read로 기록), 동등성 수준을 실험 변수로 보고, stale audit |
| 모든 step이 모든 block을 읽어 DEP≈SUFFIX | runtime의 선택적 context 조립을 전제로 워크로드 설계, 그 가정을 문서화; history는 요약 block으로 분리 |
| 비결정성으로 동등성 판정 흔들림 | temp 0 + seed, N회 반복, 동등성 수준별 보고 |
| GPU 단계 지연 | API cached_tokens로 핵심 주장 입증, GPU는 부록 |
| toy prompt가 API 캐시 최소 토큰에 미달해 캐시 효과가 안 보임 | stable prefix ≥ 2k tokens로 워크로드 설계, 최소 길이 낮은 모델 선택, `cache_*_tokens == 0`을 테스트에서 assert |
| 의도적으로 확률적인 호출(self-consistency)을 Memo가 덮어씀 | `sampling_intent=fresh` 플래그로 Memo 재사용 차단 |
| 팀의 에이전트 경험 부족 | Phase 0 2주 학습 + 프레임워크 없이 ReAct 직접 구현 |

## 13. 사용자 결정이 필요한 열린 질문

1. LLM provider 기본값 — **권장: Anthropic 기본 + OpenAI 호환 어댑터**(vLLM과 공유). Anthropic은 명시적 `cache_control`로 캐시 실험을 통제할 수 있다. 단 모델 선택은 두 축으로: 대량 실험은 가장 싼 모델, **캐시 실험은 최소 캐시 토큰이 낮은 모델**(Haiku 4.5는 4,096이라 부적합; Sonnet급 1,024 — 실행 시점 문서 확인). 월 API 예산 상한을 정해 달라.
2. 워크로드 — **권장: 자체 시나리오 스위트가 주 평가**, BFCL v3 multi-turn·ToolSandbox 일부 이식은 외부 타당성용(연구 지도 §5.4). 동의하면 S1~S6 + (여유 시) S7·S8로 확정.
3. GPU 단계를 11월 말 로드맵에 고정할지, 부록으로 둘지 — **권장: 부록**(Phase 3의 선택 항목). 4090 접근(EC2 relay)은 이미 가능하므로 앞당길 수는 있다.
4. 12월 보고서를 arXiv preprint 수준으로 써서 2027 상반기 워크숍에 낼 생각이 있는지 (근접 선행 연구가 5월·9월에 나와 시간 창이 좁다).
