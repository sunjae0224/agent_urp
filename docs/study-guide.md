# 선행 학습 가이드 (에이전트 경험 없는 팀원 기준)

목표: 2주 안에 "우리 runtime을 설계·구현할 수 있을 만큼"만 배운다. 논문을 다 이해하는 게 아니라 **개념 체크리스트(§4)** 를 설명할 수 있으면 통과다. 각 항목은 읽기 + 30분~2시간짜리 손 실습으로 짝을 지었다. 관련 연구 전체 지도는 [research-landscape.md](research-landscape.md).

---

## 1주차 — 에이전트가 실제로 어떻게 도는지 몸으로 익히기

| 일 | 읽기 | 실습 (이게 핵심) |
|---|---|---|
| 1–2 | **ReAct** (Yao 외, ICLR 2023, arXiv:2210.03629) §1–3. Anthropic *tool use* 문서 또는 OpenAI *function calling* 문서 (메시지 포맷, tool_result 블록) | **프레임워크 없이** ReAct 루프를 100줄 안에 구현: 계산기·가짜 검색 tool 2개, 최대 6 step, 매 step의 *전체 prompt* 와 응답을 JSONL로 저장. 이 로그가 우리 TraceStore의 원형이다 |
| 3 | **CoALA** (Sumers 외, 2023, arXiv:2309.02427) §1–4: working/episodic/semantic/procedural memory, 행동 공간 | 내 ReAct 루프의 각 요소를 CoALA 어휘로 라벨링한 노트 1쪽 |
| 4–5 | LangGraph 문서: quickstart → *persistence(checkpointer)* → *time travel* 튜토리얼 | 같은 에이전트를 LangGraph로 다시 만들고, 체크포인트에서 fork해 **suffix rerun을 직접 경험**. "내 루프와 무엇이 다른가, 노드는 state의 어느 부분을 읽는가"를 노트로 남김 |
| 주말 | Anthropic *prompt caching* 문서 (breakpoint, `cache_read_input_tokens`, 최소 토큰 수) | system prompt 2k tokens에 breakpoint를 걸고 3번 호출 → usage 필드가 어떻게 변하는지 표로. 그 다음 system prompt 한 글자를 바꿔 다시 호출 → cache miss 확인. **GPU 없이 prefix cache를 관찰하는 법**을 익힌다 |

## 2주차 — 증분 계산과 서빙, 그리고 가장 가까운 논문

| 일 | 읽기 | 실습 |
|---|---|---|
| 1–2 | **Build Systems à la Carte** (Mokhov 외, ICFP 2018) §1–5. Salsa *algorithm* 문서 + rust-analyzer "durable incrementality" 블로그 | 파이썬 40줄로 **mini build system**: key→task, 입력 해시 기록(verifying trace), 바뀐 입력만 재빌드, 출력이 같으면 하위 전파 중단(early cutoff). 우리 runtime의 뼈대가 이것이다 |
| 3 | vLLM *Automatic Prefix Caching* 설계 문서, PagedAttention 논문 §1–3 (arXiv:2309.06180), SGLang RadixAttention 블로그, **"Don't Break the Cache"** (arXiv:2601.06007) | "prefix cache가 깨지는 조건 3가지"와 "prefill vs decode 비용"을 반 쪽으로 정리 |
| 4 | **Execution Lineage** (arXiv:2605.06365) 정독 + 자매 논문(arXiv:2605.12087) skim | 팀 토론 1시간: research-landscape §3.1 표를 근거를 들어 수정 |
| 5 | **Motion** (SIGMOD Companion 2024), **CacheBlend** (arXiv:2405.16444) §1–3, **Incremental Consistency Execution** (arXiv:2609.24090) 초록 | 각자 "우리 기여 1줄"을 써서 비교 |

## 3주차 이후 — 주 2편 세미나 순서 (수요일)

1. Parrot (OSDI'24) · Autellix (arXiv:2502.13965) — 앱 수준 의존성을 서빙에 노출
2. Workload-Aware Caching for Multi-Agent Systems (2607.20495) · KVFlow (2507.07400) — 비용 모델 비교 대상
3. GA-Rollback (EMNLP'25) · AgentRewind (2608.14380) — 복구/rollback 베이스라인
4. STALE (2605.06527) · Invalidation Contracts (2609.00243) — 평가 방법론
5. Adapton (PLDI'14) · Self-adjusting computation 요약 (선택, 이론 보강)
6. ACE (ICLR'26) · ACON (2510.00615) — 컨텍스트 관리와의 대비
7. ToolMaze (2606.05806) · Agent-Editing World Model (2609.28416) — 시나리오 설계 참고
8. From Agent Traces to Trust 서베이 (2606.04990) — 참고문헌 채굴

---

## 2. 도구 체크리스트 (1주차 안에)

- Python 3.11+, `uv` (가상환경·의존성), `pytest`, `ruff`, 타입힌트/`pydantic`
- `sqlite3` 기본 (테이블, 인덱스, 트랜잭션), `networkx` (DAG, 도달 집합, 위상 정렬)
- `hashlib.blake2b` 로 content-addressed id 만들기
- git: 브랜치, PR, 리뷰 (격주 교차 리뷰)
- API 키 관리(.env), 비용 감각: Haiku급 모델로 실험, 캐시 실험은 최소 캐시 토큰이 낮은 모델로

## 3. 나중에 (11월 말, GPU 단계 진입 시)

- vLLM OpenAI 호환 서버 띄우기 (`--enable-prefix-caching` 명시, Qwen2.5-7B-Instruct-AWQ), `/metrics`에서 `vllm:prefix_cache_hits_total` 읽기
- TTFT/prefill 측정 방법 (스트리밍 첫 토큰 시각, 서버 metrics)
- 4090은 EC2 relay 터널로 원격 접근 (기존 세팅)

## 4. 개념 체크리스트 — 이걸 설명할 수 있으면 통과

1. ReAct 루프에서 매 step의 prompt는 무엇으로 구성되고 무엇이 누적되는가
2. tool-use API에서 tool 호출과 결과가 메시지로 어떻게 표현되는가
3. LangGraph checkpoint와 time-travel(fork)이 왜 "suffix rerun"과 같은가
4. content-addressed 저장이 왜 memo와 undo를 공짜로 주는가
5. verifying trace vs constructive trace, 그리고 LLM 비결정성 아래서 왜 후자만 유효한가
6. early cutoff가 무엇이고 "동등성"을 어디까지 느슨하게 잡을 수 있는가 (exact → 정규화 → 임베딩 → LLM-judge)
7. prefix cache가 깨지는 조건과 chained block hash의 의미
8. prefill / decode / TTFT의 구분, 캐시된 token은 왜 싸며 어떤 usage 필드로 확인하는가
9. Execution Lineage와 우리의 차이 3가지
10. "stale reuse"를 어떻게 ground truth와 대조해 측정하는가
