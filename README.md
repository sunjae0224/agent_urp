# agent_urp — LLM Agent 의존성 기반 선택적 재실행 Runtime

학부생 연구학점제 (2026-08-31 ~ 2026-12-18) · 팀 3명 · 상태: **구현 v1 완료 (2026-09-30)**

## 한 문단

에이전트가 여러 단계(LLM 호출, tool 호출, memory 읽기/쓰기)를 거쳐 일을 끝낸 뒤 **무언가 바뀌면** — 사용자가 조건을 고치거나, tool 결과가 달라지거나, memory가 교정되거나 — 지금의 프레임워크는 전부 다시 돌리거나(full rerun) 그 지점 이후를 전부 다시 돌린다(suffix rerun, LangGraph time-travel). 우리는 실행 중 **누가 무엇을 읽고 썼는지**를 기록해 두었다가, 정말로 영향받은 step만 다시 실행하고 나머지는 재사용한다. 그리고 그 결정을 호출 수가 아니라 **prefix cache를 고려한 실제 추론 비용**으로 내린다.

구현된 모델(v1): 워크로드는 결정적 함수 `program(ctx)`이고 비용이 드는 일은 `@step(kind=...)` 호출에서만 일어나며, 각 step의 read(block/env/artifact 버전)와 write가 실행 중 자동 기록된다.

```
편집(block 내용 / env 상태) → 원 run의 초기 상태 복원 + 편집 적용 → program(ctx)을 처음부터 다시 실행
  각 step 호출은 원 run의 같은 (name, 순서) 기록과 비교해 정책별로 판정한다:
    FULL    항상 실행
    SUFFIX  편집 대상을 처음 읽은 step 이전이면 위치만 보고 재사용 (LangGraph time-travel)
    MEMO    key_static + 전체 상태 해시가 같은 기록만 재사용 (LangGraph CachePolicy)
    DEP     verifying trace: 기록된 read 버전이 모두 현재와 같으면 재사용
            → constructive trace: 조상 run의 같은 key_static 기록 중 검증되는 것 재사용
            → 아니면 실행; L1이면 동등한 새 출력 대신 옛 artifact 채택(early cutoff)
  → 판정 REUSE | REBUILD | RERUN | LIVE(제어 흐름이 갈라져 원 run에 없는 호출)
```

현재 결과(scripted LLM, `run_matrix`): S1 예산 편집에서 DEP는 5 step 중 2개만 실행(SUFFIX 3, FULL·MEMO 5), S5 같은 뜻 재표현에서는 1개만 실행 — 모든 정책이 FULL과 같은 출력, stale reuse 0. 비용 모델과 cache-aware 결정(스펙 §7)은 아직 없다.

## 빠른 시작

```bash
uv sync                                       # 의존성 설치 (pydantic, networkx)
uv run pytest -q                              # 전체 테스트
uv run python -m agent_urp.eval.run_matrix    # S1/S5 × FULL/SUFFIX/MEMO/DEP 비교표
```

작업 규칙(TDD, CLAUDE.md 갱신, 커밋 규칙)과 폴더별 설명은 [CLAUDE.md](CLAUDE.md)와 각 폴더의 CLAUDE.md에 있다.

## 문서 지도

| 문서 | 내용 |
|---|---|
| [docs/superpowers/specs/2026-09-30-agent-urp-design.md](docs/superpowers/specs/2026-09-30-agent-urp-design.md) | **설계 스펙** — 문제 정의, 접근법 비교, 아키텍처, 데이터 모델, 알고리즘, 평가, 리스크, 열린 질문 |
| [docs/research-landscape.md](docs/research-landscape.md) | 관련 연구 지도(5개 분야), 계획서 인용 검증, **차별화 전략과 위협**, 필독 논문, 프레임워크·벤치마크 판정 |
| [docs/study-guide.md](docs/study-guide.md) | 에이전트 경험 없는 팀원용 2주 선행 학습 + 세미나 순서 + 개념 체크리스트 |
| [docs/roadmap.md](docs/roadmap.md) | 12/18까지 주차 계획, 역할, 데모 체크포인트, GPU-free → GPU 확장 경로 |

## 핵심 결정 (요약)

- **얇은 자체 runtime**을 만든다. LangGraph는 학습용 + suffix rerun 베이스라인 독립 구현체로만 쓴다.
- **GPU 없이 핵심 주장을 끝낸다.** 호출·token·비용·정확성은 API(+기록된 응답 재생)로, prefix cache 효과는 Anthropic/OpenAI의 cached-token 필드로 실측. vLLM APC(RTX 4090) 실측은 선택적 부록.
- 이론 뼈대는 빌드 시스템(Build Systems à la Carte: constructive trace, early cutoff, minimality) + Salsa durability + Adapton demand-driven.
- 가장 가까운 선행 연구는 Execution Lineage(arXiv:2605.06365)와 Incremental Consistency Execution(arXiv:2609.24090). 우리 빈자리: **cache-aware 재실행 결정, 의미적 early cutoff의 정량화, 에이전트 특화 트리거·동적 그래프, perturbation 벤치마크**.

## 다음 할 일

1. **팀 학습**: [study-guide.md](docs/study-guide.md) 1~2주차를 하면서 스펙 §5·§6과 CLAUDE.md를 읽고 `run_matrix` 결과를 직접 재현한다. Execution Lineage·ICE 본문을 정독해 [research-landscape.md §3.1](docs/research-landscape.md) 표를 갱신하고, 스펙 §13 열린 질문에 답한다.
2. **API 백엔드**: `llm/anthropic.py`·`llm/openai_compat.py`를 붙이고 cassette로 기록·재생한다(provider·예산은 §13 1번 결정 후).
3. **시나리오 S2~S6**: 리서치 파이프라인(S2 소스 변경, S4 tool 실패), 사무 작업(S3 memory 교정), S6 제어 흐름 분기 워크로드와 시나리오를 추가한다 — [roadmap.md](docs/roadmap.md).
