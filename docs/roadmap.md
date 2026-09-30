# agent_urp 로드맵 (2026-09-30 ~ 2026-12-18)

설계 근거는 [설계 스펙](superpowers/specs/2026-09-30-agent-urp-design.md), 읽을거리는 [study-guide.md](study-guide.md), 관련 연구는 [research-landscape.md](research-landscape.md).

## 원칙

1. **GPU 없이 핵심 주장을 끝낸다.** 호출 수·token·비용·정확성은 API + 기록된 응답(cassette)으로 입증한다. GPU(vLLM APC, RTX 4090)는 TTFT/prefill 실측을 더하는 부록이다.
2. **2주마다 돌아가는 것을 보여준다.** 각 phase 끝에 CLI 데모 + 결과표 한 장.
3. **기록이 곧 실험이다.** 모든 실행은 TraceStore에 남고, cassette만으로 재생된다. 실험을 다시 돌릴 때 API 비용이 들지 않아야 한다.
4. 팀 역할은 컴포넌트 경계와 일치시킨다 (아래 표). 격주로 코드 리뷰를 교차한다.

## 팀 역할 제안 (3명)

| 역할 | 담당 컴포넌트 | 산출물 |
|---|---|---|
| R1 Runtime core | `core/` (TraceStore, DepGraph, policies, Runtime; Memo는 TraceStore의 `key_static` 색인) | 선택적 재실행 엔진, 속성 테스트 |
| R2 Workload & Eval | `tools/`, `workloads/`, `eval/` | mock 환경(버전 있음), S1~S6, 베이스라인 실행 매트릭스, 지표·그림 |
| R3 Context & Cache | `core/context.py`, `core/cost.py`, `llm/` | block layout 정책, 비용 모델, API 캐시 실측, (후반) vLLM 백엔드 |

## 주차 계획

| 기간 | Phase | 목표 | 완료 기준 (Definition of Done) |
|---|---|---|---|
| ~10/5 | W0 준비 | 스펙 검토·확정, repo·uv·API 키·pre-commit 세팅, 역할 확정 | 스펙 승인, `uv run pytest` 빈 테스트 통과 |
| 10/6–10/17 | **Phase 0 학습** | study-guide 1~2주차 완료. 각자 *프레임워크 없이* ReAct 루프 + mock tool 2개 구현(≤150 LOC). LangGraph persistence/time-travel 튜토리얼 1회 실습. 리딩 세미나 4편 | 3명 모두 toy 에이전트 동작, 세미나 노트 `docs/notes/` |
| 10/20–10/31 | **Phase 1 Runtime core** | `@step(kind)`(read/write 실행 중 자동 기록), TraceStore(SQLite), DepGraph, ContextAssembler(naive), scripted LLM + cassette, FULL/SUFFIX 정책, S1·S2 워크로드 v0 — **2026-09-30 완료(S2 워크로드 제외)** | 기록된 run을 cassette로 재생 가능; FULL/SUFFIX 결과표 1장 |
| 11/3–11/14 | **Phase 2 선택적 재실행** | policies/Runtime(DEP: 기록된 read 검증, backdating early cutoff), Memo(constructive trace), Equivalence L0~L2, DEP 정책, 구조 분기 시 LIVE 전환, S1~S6, stale audit | 속성 테스트(DEP==FULL, no-op→호출≤1, undo 즉시 복원) 통과; S1~S6 × FULL/SUFFIX/DEP 결과표 |
| 11/17–11/28 | **Phase 3 Cache-aware** | block layout 정책(naive/stable_prefix), CostModel, Anthropic/OpenAI cached_tokens 실측, probe 순서 정책, Equivalence L3/L4 실험(절감 vs stale 곡선). **선택**: 4090에 vLLM APC 올려 TTFT/prefill 실측 | DEP+cache(+layout) 축 추가된 결과표; 캐시 실측이 비용 모델과 ±20% 이내 |
| 12/1–12/12 | **Phase 4 평가·집필** | 전체 매트릭스(시나리오×정책×동등성 수준×N회), ablation, 그림, 보고서 초고(워크숍 논문 구조) | 12/12 초고 완성, 재현 스크립트 1개로 전 결과 재생 |
| 12/15–12/18 | 마감 | 리뷰 반영, 데모 영상/README, 코드 정리 | 12/18 제출 |

버퍼는 Phase 4 안의 1주. Phase 3의 GPU 항목이 밀리면 부록으로 내린다.

**진행 현황(2026-09-30)**: v1 skeleton(`feat/skeleton-v1`)으로 Phase 1 핵심 항목을 끝냈다(S2 워크로드 제외). Phase 2 중 DEP 정책·Memo·Equivalence L0/L1·LIVE 전환·stale audit·S1/S5 시나리오·MEMO 베이스라인도 이미 들어가 있다. 일정은 다시 짜지 않았다 — 남은 항목(S2~S4·S6, Equivalence L2, 실제 API 백엔드, 비용 모델)은 원래 phase에서 한다.

## GPU-free → GPU 확장 경로

| 지표 | GPU 없이 (10~11월) | GPU 있을 때 (선택, 11월 말~) |
|---|---|---|
| LLM/tool 호출 수, 입력·출력 token | provider usage 필드 / cassette 메타 | 동일 |
| prefix cache 효과 | Anthropic `cache_read_input_tokens`, OpenAI `cached_tokens` 실측 + 가격표 기반 $ | vLLM APC hit 지표(`/metrics`) |
| prefill 시간 / TTFT | 스트리밍 첫 token까지 시간(노이즈 큼, 상대 비교만) | vLLM 서버 로그/metrics의 TTFT, prefill 시간 |
| GPU 메모리 | 측정 불가(보고 안 함) | vLLM KV 블록 사용량 |
| 정확성, stale reuse | scripted/실 API 모두 가능 | 동일 |

vLLM 백엔드는 OpenAI 호환 서버라 `llm/openai_compat.py` 하나로 API·로컬을 모두 덮는다. 4090은 EC2 relay 터널로 원격 접근 가능하므로 팀원 누구나 붙을 수 있다.

## 매주 리듬

- 월: 30분 진행 점검(막힌 것, 이번 주 DoD)
- 수: 리딩 세미나 (2편, 각 15분 발표 + 토론; study-guide 순서)
- 금: PR 리뷰 교차, 결과표 갱신

## 데모 체크포인트

- 10/17: toy ReAct 에이전트 3개 시연
- 10/31: 기록 → cassette 재생 → SUFFIX rerun 시연
- 11/14: 예산 편집(S1) 시 DEP가 호텔 step만 재실행하는 것을 trace로 보여주기; no-op 편집(S5)에서 호출 1회
- 11/28: 같은 편집에서 cache-aware layout이 cached token을 늘리는 것을 API usage로 보여주기
- 12/12: 보고서 초고 + 전체 결과 그림
