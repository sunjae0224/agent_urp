# 관련 연구 지도와 차별화 전략

작성 2026-09-30. 출처 검증 등급: **[전문]** = 초록/본문 직접 확인, **[스니펫]** = 검색 결과로 제목·저자·ID만 확인, **[제목만]** = 존재만 확인. 2026년 7월 이후 논문은 대부분 [스니펫]이므로 인용 전에 본문을 읽을 것. 설계 스펙은 [superpowers/specs/2026-09-30-agent-urp-design.md](superpowers/specs/2026-09-30-agent-urp-design.md).

---

## 0. 한 문단 요약

우리 문제("에이전트 trajectory에서 무언가 바뀌면 영향받은 step만 다시 돌린다")는 **다섯 연구 분야가 만나는 지점**이다: (1) 증분 계산·빌드 시스템, (2) 데이터 provenance/lineage, (3) LLM 서빙의 KV/prefix 캐싱, (4) 에이전트 복구·메모리·컨텍스트 관리, (5) 워크플로 엔진(durable execution). 2026년 5월과 9월에 우리와 매우 가까운 preprint 두 편(Execution Lineage, Incremental Consistency Execution)이 나왔으므로 "의존성 그래프로 선택 재실행" 자체는 더 이상 새롭지 않다. 우리가 잡을 빈자리는 **(a) 에이전트 특유의 동적 제어 흐름·tool 실패·memory 교정을 트리거로 다루고, (b) 재실행 결정을 prefix cache 비용까지 포함해 hardware-aware하게 내리며, (c) 의미적 early cutoff의 절감–stale 위험 곡선을 정량화하고, (d) 재현 가능한 perturbation 벤치마크를 내는 것**이다.

---

## 1. 계획서 인용 5편 검증 결과

| # | 계획서 표기 | 실제 | 우리와의 거리 |
|---|---|---|---|
| 1 | Li et al., GASR, EMNLP 2025 | **GA-Rollback**: "Generator-Assistant Stepwise Rollback Framework for LLM Agent", Xingzuo Li 외, EMNLP 2025 main, arXiv:2503.02519, 코드 공개 [전문] | 낮음~중간. assistant LLM이 generator의 잘못된 행동을 감지해 *선형* rollback. 트리거가 "오류 판단"이지 "상위 입력 변경"이 아니고 의존성 그래프가 없다. → "rollback ≠ dependency invalidation" 대비 베이스라인 |
| 2 | Kang et al., ACON, 2025 | "ACON: Optimizing Context Compression for Long-horizon LLM Agents", Minki Kang 외(Microsoft), arXiv:2510.00615, 코드 공개 [전문] | 낮음. 손실 압축이지 의존성·무효화 개념 없음. context 관리 클러스터 인용 |
| 3 | Luo et al., Autellix, 2025 | "Autellix: An Efficient Serving Engine for LLM Agents as General Programs", Michael Luo 외(Berkeley), arXiv:2502.13965 [전문]. **venue 주의**: 조사 A는 OSDI'25, 조사 B는 NSDI'26 camera-ready에서 "Agentix"로 개명(usenix 페이지·저자·초록 일치 확인)이라 보고 → 인용 전 확인 | 중간, 다른 계층. 프로그램 단위 스케줄링(서빙 계층). 호출을 *다시* 실행하지 않음. "에이전트 구조를 시스템이 활용한다"는 명분의 앵커 |
| 4 | Rosen and Rosen, Execution Lineage, 2026 | "From Agent Loops to Deterministic Graphs: Execution Lineage for Reproducible AI-Native Work", Josh & Seth Rosen (ThruWire Inc., 산업체), arXiv:2605.06365, 2026-05-07, 미심사, 코드 없음 [전문]. 자매 논문 "Intermediate Artifacts as First-Class Citizens" arXiv:2605.12087 | **매우 가까움 — 최우선 차별화 대상** (아래 §3) |
| 5 | Kwon et al., PagedAttention, SOSP 2023 | 정확. arXiv:2309.06180 [전문] | 배경. GPU 비용이 왜 중요한지의 근거 |

---

## 2. 연구 분야 지도

### 2.1 증분 계산 · 빌드 시스템 (이론적 뼈대)

| 개념 | 출처 | 우리에게 주는 것 |
|---|---|---|
| scheduler × rebuilder 분해, verifying/constructive trace, early cutoff, **minimality**(필요한 것만, 필요한 것은 반드시 재빌드) | Build Systems à la Carte (Mokhov·Mitchell·Peyton Jones, ICFP'18/JFP'20) | 런타임을 (scheduler, rebuilder)로 형식화. LLM 비결정성 아래서는 **constructive trace**(입력 해시→기록된 출력)만이 유효한 memo. minimality = 우리 정확성 명세 |
| revision, red/green 검증, **durability 등급**, backdating(=equality 기반 early cutoff) | Salsa (rust-analyzer) | block마다 durability 등급, 재검증 순서 |
| demand-driven: dirty ≠ 재계산, 관찰될 때만 계산 | Adapton (PLDI'14) | 최종 결과의 조상만 재실행 |
| trace + change propagation, trace stability("작은 편집 ⇒ 작은 재실행" 보장) | Self-adjusting computation (Acar) | 편집 거리로 blast radius 사전 추정 |
| IVM / Differential Dataflow / DBSP | DB 커뮤니티 | 파생 artifact(요약, plan)를 "view"로 보고 delta만 재유도 |

### 2.2 데이터 provenance · lineage

- **Motion** (Shankar & Parameswaran, SIGMOD Companion 2024) [전문]: LLM 파이프라인에 **IVM**을 적용한 "reactive prompt". 우리 계보의 학술적 조상. tool 호출·memory·비용은 없음.
- **Execution Lineage** (§1 #4) + **Intermediate Artifacts** (arXiv:2605.12087): artifact DAG + identity-based replay.
- **From Agent Traces to Trust** (Yiqi Wang 외, arXiv:2606.04990, 2026, v5 활발히 개정 중) [전문]: 에이전트 실행 provenance 서베이. 참고문헌 캐기용 진입점. 초록 기준 "선택적 재실행"은 다루지 않음 → 우리가 지목할 빈칸.
- MemLineage (arXiv:2605.14421): memory 파생 DAG를 **보안**(poisoning 방어)에 사용 — 같은 그래프, 다른 목적.
- BLIP (Lin 외, VLDB 2026, arXiv:2608.25210): "어떤 입력 텍스트가 답을 만들었나"(입력 provenance) — 우리의 "어떤 step이 어떤 step에 의존하나"와 다른 층위.
- 실패 원인 추적 클러스터 (FALAT 2606.00765, EDGE 2609.01360, GraphTracer 2510.10581) [스니펫]: trajectory 위에 의존/인과 그래프를 세우지만 사후 원인 분석용. 그래프 *구성* 기법은 빌려 쓸 수 있다.

### 2.3 LLM 서빙 · KV/prefix 캐싱 (hardware-aware의 근거)

| 논문 | 핵심 | 빌릴 것 |
|---|---|---|
| vLLM APC (docs, v0.30 기준) | block 단위 chained hash(parent hash 포함) → 앞쪽 편집은 뒤 전부 miss; LRU eviction; `--prefix-caching-hash-algo`, 2026년 `--prefix-match-unit` | chained hash 구조를 우리 block 체인에 그대로; `vllm:prefix_cache_hits_total` 로 실측 |
| SGLang RadixAttention (arXiv:2312.07104) | radix tree로 LCP 매칭 + cache-aware scheduling | "이미 따뜻한 것부터 실행"을 재실행 순서 휴리스틱으로 |
| **CacheBlend** (EuroSys'25 best paper, arXiv:2405.16444) [전문] | context **중간**이 바뀌어도 non-prefix KV를 재사용하고 편차 큰 토큰(HKVD)만 선택 재계산; TTFT 2.2–3.3× | 우리 문제의 KV 층위 아날로그. "전부 아니면 전무" 무효화를 피하고, 싼 편차 추정기 → 최소 재계산 집합 |
| PromptCache (MLSys'24, arXiv:2311.04934) | 스키마(PML)로 선언한 모듈 단위 attention 재사용, 불연속 position id | "block을 1급 객체로" 스키마 우선 설계 |
| AttentionStore (ATC'24) | 다층(GPU→CPU→디스크) KV 계층 | hot/warm/cold artifact 계층 |
| **Parrot** (OSDI'24, arXiv:2405.19888) [전문] | Semantic Variable로 앱 수준 dataflow를 서빙 계층에 노출 | 우리 논지의 한 층 아래 선례: "의존성 그래프를 실행 계층에 노출하면 최적화가 열린다" |
| Autellix/Agentix (§1 #3) | 프로그램 단위 스케줄링, 4–15× | "step 하나가 아니라 하위 critical path 전체의 재실행 비용을 보고 결정" |
| KVFlow (NeurIPS'25, arXiv:2507.07400) [스니펫] | Agent Step Graph + steps-to-execution 기반 eviction | "언제 다시 필요해질지"를 artifact 보존 정책에 |
| **"Don't Break the Cache"** (arXiv:2601.06007, 2026) [전문] | 실제 에이전트 trace에서 캐시를 깨는 3패턴: 내용 편집 / tool 결과 삽입 / 재배열. 10턴 이후 캐시 효율 급락 | **동기 섹션의 직접 인용**. 우리 트리거 분류의 근거 |
| Workload-Aware Caching for Multi-Agent Systems (arXiv:2607.20495) [전문] | DAG 노드 결과를 재계산 비용·의존 수·빈도로 점수화한 eviction; 요청 *간* 재사용 | 비용 모델 비교 대상. 편집 트리거 무효화는 없음 |
| TOPAS (2608.25523), GraniKV (2608.15584), EPIC (ICML'25, 2410.15332) | prefix-aware 스케줄러, 비대칭 페이징, position-independent caching | 부록 수준 |

### 2.4 에이전트 복구 · 메모리 · 컨텍스트

- 복구/rollback: GA-Rollback(§1), **AgentRewind** (arXiv:2608.14380) — checkpoint로 되감고 재개 [전문], AgentR (2608.15264) — 재시도/재개 아키텍처, KAIJU (arXiv:2604.02375) — "dependency resolution"을 하는 executive kernel(실패 시 선택 재실행인지 지역 재시도인지 본문 확인 필요), **ToolMaze** (arXiv:2606.05806) — DAG 구조 task + tool perturbation 2×2 분류 벤치마크(우리 평가에 차용 가능).
- 재사용/경험 메모리: Agent Workflow Memory (ICML'25, 2409.07429), Agentic Plan Caching (NeurIPS'25, 2506.14852), AgentReuse (2512.21309), LifeMem (EMNLP'26, 2609.12655) — 모두 *과제 간* 유사도 기반 재사용. 우리는 *trajectory 내* 의존성 기반.
- 메모리 교정/stale: **STALE** (arXiv:2605.06527) [전문] — "memory가 낡았음을 아는가" 벤치마크 + 전파 인식 검색 프로토타입(CUPMem). **Invalidation Contracts** (arXiv:2609.00243) — 버전 스탬프로 cross-episode 캐시 무효화, token 29–33% 회수(평가 방법론 차용). All-Mem (2603.19595) — 편집 가능한 그래프 메모리. **Agent-Editing World Model** (arXiv:2609.28416) — "task-state contamination"을 LLM 판단으로 교정(우리는 구조적으로).
- 컨텍스트 관리: ACON(§1), ACE (ICLR'26, 2510.04618), PEEK (2605.19932). "압축"과 "구조적 추적"의 대비.
- 제약 유실 진단: Governance Decay (2606.22528), Constraint Weakening (2608.24569) — 압축 중 조건이 사라지는 병리. 우리 S1/S5 시나리오의 동기.

### 2.5 워크플로 엔진 · 실무 도구

- Temporal(결정적 replay, activity 격리), Dagster(asset staleness, data/code version), LangGraph(checkpoint·time-travel = suffix rerun), Prefect cache key — 조사 C 결과를 §5에 합침.
- 비학술 선행: `incremental-agent-builds` (GitHub, make식 증분 LLM 파이프라인, 호출 92.7% 절감 주장, 스타 0), **`reactifact`** (typed artifact의 consumes/produces로 의존성을 *암묵적으로* 추론, "그래프를 그리지 않는다"가 세일즈 포인트) — 우리가 *명시적 기록 그래프*를 택하는 이유(검사 가능성, 비용 모델이 그래프를 필요로 함)를 설명할 때 대비용.
- 의미적 캐시: GPTCache(임베딩 유사도 임계값, 0.9 근처에서 튜닝), SemanticALLI (2601.16286, 추론 trace 캐시), Statistical Independence Aware Caching (2511.22118) [스니펫] — 일부러 독립 샘플이 필요한 호출은 캐시하면 안 된다는 경고 → `sampling_intent` 플래그.

---

## 3. 차별화 — 무엇이 이미 있고, 무엇이 비어 있나

### 3.1 가장 가까운 두 편과의 대조

| 축 | Execution Lineage (2605.06365) | Incremental Consistency Execution (2609.24090, 9/21 공개) | **agent_urp** |
|---|---|---|---|
| 그래프 | artifact 생산 계산의 DAG, 명시적 의존성 | field-level dependency mask | LLM/tool/memory/context block을 **타입이 다른 노드**로, 실행 시 기록 |
| 트리거 | artifact(문서) 편집 | 입력 변화(일반) | 조건 편집 **+ tool 실패·결과 변경 + memory 교정** (3축, "Don't Break the Cache" 분류와 정렬) |
| 동적 제어 흐름 | 불명(문서 편집 도메인) | 불명 | **LIVE 전환 + constructive-trace memo**로 명시 처리 |
| 동등성 | identity 기반 replay | "equivalence barrier"(상세 미공개) | L0~L4 pluggable oracle, **절감–stale 곡선 정량화**, 비용 게이트된 LLM-judge |
| 비용 모델 | 없음(순차 구현, wall-clock 이득 없음) | 호출 수·지연 감소 보고 | **prefix cache 인지**: uncached token 기준 비용, layout 정책, probe 순서 |
| 평가 | 1 도메인 2 task, 3반복, 코드 없음 | 3 도메인, 상세 미공개 | 6 시나리오 템플릿 × 시드, stale reuse ground truth, API 캐시 실측, (선택) vLLM APC 실측, 코드 공개 |

### 3.2 우리가 주장할 기여 (우선순위 순)

1. **Cache-aware selective re-execution.** 재실행 결정을 "몇 개의 호출을 피하나"가 아니라 "캐시되지 않은 prefill token을 얼마나 줄이나"로 내리고, block layout(stable prefix)과 probe 순서를 함께 최적화한다. 서빙 측(Parrot/Autellix/KVFlow)은 그래프를 스케줄링에만 쓰고, lineage 측(EL/Motion)은 비용을 보지 않는다. **그 사이 층이 비어 있다.**
2. **Semantic early cutoff의 정량화.** 동등성 수준을 올릴수록 절감은 늘고 stale 위험은 커진다. 이 곡선과 "judge 호출 비용 < 기대 절감일 때만 judge"라는 비용 게이트를 처음으로 측정한다.
3. **에이전트 특화 트리거와 동적 그래프.** tool 실패·결과 drift·memory 교정을 1급 트리거로, 제어 흐름 분기 시 memo 기반 LIVE 실행으로 처리. 빌드 시스템 이론(constructive trace, minimality)으로 정확성 명세를 세운다.
4. **Perturbation 벤치마크.** 편집이 정답에 영향을 주는 step 집합(ground truth)이 명시된 시나리오 스위트 → stale reuse rate를 처음으로 직접 측정. STALE·ToolMaze의 분류를 차용.
5. (선택) **실제 하드웨어 실측.** RTX 4090 + vLLM APC에서 TTFT/prefill 개선을 보임 — EL은 wall-clock 이득이 없었다.

한 줄 포지셔닝: *"Motion의 IVM과 Execution Lineage의 artifact DAG를 tool·memory가 있는 동적 에이전트 trajectory로 일반화하고, Parrot/Autellix가 스케줄링에 쓴 앱 수준 의존성을 prefix-cache-aware 재실행 결정에 쓴다."*

### 3.3 위협과 대응

| 위협 | 대응 |
|---|---|
| ICE(2609.24090)가 equivalence barrier + 비용까지 이미 했을 수 있음 | **1주차에 본문 정독** 후 §3.1 표 갱신. 우리는 prefix cache·layout·probe 순서까지 가므로 최소 1번 기여는 유지 |
| KAIJU가 "dependency resolution"으로 리뷰어를 혼동시킴 | 본문 확인 후 "실패 시 지역 재시도 vs 하위 그래프 선택 재실행" 차이를 related work에 명시 |
| 창이 좁아짐 (5월·9월 근접 논문) | 12월 중순 보고서를 arXiv preprint 수준으로 쓰고, 2027 상반기 워크숍(예: EuroSys/MLSys 워크숍, 국내 학회)을 목표로 조기 공개 |
| "장난감 에이전트" 비판 | 시나리오를 STALE/ToolMaze/τ-bench류 구조에 맞추고, LangGraph time-travel과 동일 의미론의 suffix 베이스라인으로 공정 비교 |

---

## 4. 필독 논문 (읽는 순서 = 우선순위)

1. Execution Lineage — arXiv:2605.06365 (+ 자매 2605.12087). 전문 정독, related work의 축.
2. Incremental Consistency Execution — arXiv:2609.24090. v2 추적.
3. Motion — SIGMOD Companion 2024. IVM 프레이밍.
4. Build Systems à la Carte — ICFP'18. §1–5.
5. Don't Break the Cache — arXiv:2601.06007. 동기.
6. CacheBlend — arXiv:2405.16444. KV 층위 아날로그.
7. Parrot — OSDI'24 / Autellix — arXiv:2502.13965. 시스템 앵커.
8. Workload-Aware Caching for Multi-Agent Systems — arXiv:2607.20495. 비용 모델 비교.
9. GA-Rollback — EMNLP'25 / AgentRewind — arXiv:2608.14380. 복구 베이스라인 대비.
10. STALE — arXiv:2605.06527 / Invalidation Contracts — arXiv:2609.00243. 평가 방법론.
11. Salsa 알고리즘 문서 + rust-analyzer "durable incrementality" 블로그. 구현 감각.
12. From Agent Traces to Trust 서베이 — arXiv:2606.04990. 참고문헌 채굴.

배경(에이전트 입문): ReAct (Yao 외, ICLR'23), CoALA (Sumers 외, 2023, 메모리·행동 어휘), Agent Workflow Memory, ACE — [study-guide.md](study-guide.md) 참조.

---

## 5. 프레임워크·벤치마크 (조사 C, 2026-09-30 공식 문서·저장소 기준)

### 5.1 LangGraph가 주는 것과 못 주는 것 (1.x, 2025-10 GA)

| 기능 | 사실 | 우리에게 |
|---|---|---|
| Checkpoint | `channel_values`(전체 값), `channel_versions`(채널별 단조 버전), `versions_seen`(노드별 소비 버전); append-only 체인; SQLite/Postgres 백엔드 | 채널 = versioned block의 원시 형태. 하지만 채널이 dict 하나면 필드 단위 추적 불가 |
| Time travel | `update_state`로 fork → fork 지점 이후 노드 **무조건** 재실행("LLM 호출이 다시 발생, 결과 달라질 수 있음" 공식 경고). Pregel이 채널 버전으로 트리거하므로 독립 분기는 안 돌아감 = **토폴로지 인식 suffix rerun**. 값이 같아도 하위 전파(early cutoff 없음) | **SUFFIX-LG 베이스라인**으로 그대로 사용 |
| `CachePolicy` (2025-05-29 추가) | 키 = 노드 입력의 pickle 해시(`key_func` 교체 가능), TTL, 별도 `BaseCache` 저장소(checkpointer와 자동 결합 안 됨, #5980). **코드/프롬프트 버전 미반영** → 템플릿을 고쳐도 stale 결과 반환. 초기 버그 다수 | MEMO-only 베이스라인의 의미론. 비상 대안: content-hash `key_func` |
| Functional API `@task` | 재개 시 완료된 task 결과를 복원(Temporal activity 개념) — crash 복구용, 편집 무효화 아님 | 개념만 |
| `Store` API | namespace/key JSON + 임베딩 검색 | memory 저장소로 재사용 가능(선택) |
| 없는 것 | 노드별 read/write 명세 객체, code_version, 값 기반 early cutoff, 필드 단위 버전 | **이게 우리 기여 지점** |

### 5.2 대안 프레임워크 한 줄 평

PydanticAI `pydantic_graph`(타입 그래프 + `iter()` 수동 진행 + Temporal/DBOS/Prefect/Restate durable 연동, 가장 근접하나 편집 인식 없음) · DSPy(요청 전체 canonical JSON→SHA256 캐시, `rollout_id`로 강제 재계산 — **키 설계 그대로 차용**) · LlamaIndex Workflows 2.x(이벤트 그래프 검증·시각화, 캐시 없음) · Microsoft Agent Framework(조건/fan-in DAG, AutoGen은 2025-10 유지보수 모드) · AG2 1.x(classic `cache_seed` 캐시, 신 API 지속 여부 미확인) · smolagents, OpenAI Agents SDK(관련 훅 없음) · Claude Agent SDK(hooks + session fork, DAG/캐시 없음).

### 5.3 빌릴 개념 (구현은 직접, 의존성 추가 없이)

- **Dagster** `code_version`/`data_version`: `data_version = hash(code_version, 상위 입력 버전들)`, staleness는 **비전이적**(실제 소비한 버전이 바뀌었을 때만) → 우리 `input_hash` 정의 그 자체.
- **Prefect** `CachePolicy` 합성(`INPUTS + TASK_SOURCE - 휘발 필드`) → 타임스탬프 등 제외 규칙.
- **Temporal** workflow/activity 분리 → 모든 LLM/tool 호출은 "해시 계산 → 저장소 조회 → miss면 실행 후 *기록하고* 반환"하는 단일 경계 통과. 단, Temporal의 위치 기반 replay 매칭은 복사하지 않는다. DBOS(in-process, SQLite)가 가벼운 참조.
- **OTel GenAI / LangSmith / Langfuse**: span tree = 호출 순서 트리, fan-in 표현 불가 → 의존성 DAG는 별도 1급 구조로.
- cassette: 성숙한 LLM VCR 라이브러리 없음(pytest-llm-vcr 0.6, 2026-09; Cassette 스타 1) → `hash(정규화 요청)→응답` 직접 구현.

### 5.4 벤치마크 적합성 (기준: 3~10 step, mock 가능, GPU-free, 3종 perturbation 주입 가능)

| 벤치마크 | 라이선스 | 판정 | 비고 |
|---|---|---|---|
| **BFCL v3 multi-turn** (Gorilla) | Apache-2.0 | **좋음** | 1,000 task, mock 상태 백엔드, "Missing Functions/Parameters"가 tool 변경/조건 변경과 대응, 가장 저렴 |
| **ToolSandbox** (Apple, arXiv:2408.04682) | Apple 자체(permissive, 비-OSI) | **좋음** | 1,032 시나리오, "State Dependency/Insufficient Info/Tool Augmentation" 분류가 우리 트리거 3종과 거의 1:1, world-state 객체 monkeypatch 용이 |
| τ²-bench (Sierra, arXiv:2506.07982, v1.0.1 2026-07) | MIT | 좋음(후순위) | dual-control 공유 상태; "k턴에서 멈추고 주입" 훅이 없어 포크 필요 |
| WorkBench (COLM'24) | MIT | 부분 | tool 실패·DB 교정은 쉬움, 대화 중 조건 변경은 부자연 |
| AgentBench OS/DB | Apache-2.0 | 부분 | Docker 비용, 조건 변경 없음 |
| GAIA / SWE-bench-lite / WebArena | 다양 | 부적합 | 실 도구·인프라 부담, 주입 지점 없음 (SWE-lite ~$75–120/30ep) |

**결론**: 주 평가는 **자체 시나리오 스위트**(ground-truth 의존성 그래프와 "돌면 안 되는 control step"을 우리가 정의) — 기존 벤치마크는 전부 최종 정답만 채점하므로 stale reuse·과잉 재실행을 채점할 수 없다. BFCL v3·ToolSandbox는 tool 스키마·시나리오 몇 개를 이식해 외부 타당성 앵커로 쓴다. 주의: "τ³-bench" 리더보드 수치는 SEO 사이트에만 있는 **가짜**였다 — 이 분야는 검색 결과 검증이 필수.
