# agent_urp — LLM Agent 의존성 기반 선택적 재실행 Runtime

학부생 연구학점제 (2026-08-31 ~ 2026-12-18) · 팀 3명 · 상태: **설계 검토 단계 (2026-09-30)**

## 한 문단

에이전트가 여러 단계(LLM 호출, tool 호출, memory 읽기/쓰기)를 거쳐 일을 끝낸 뒤 **무언가 바뀌면** — 사용자가 조건을 고치거나, tool 결과가 달라지거나, memory가 교정되거나 — 지금의 프레임워크는 전부 다시 돌리거나(full rerun) 그 지점 이후를 전부 다시 돌린다(suffix rerun, LangGraph time-travel). 우리는 실행 중 **누가 무엇을 읽고 썼는지**를 기록해 두었다가, 정말로 영향받은 step만 다시 실행하고 나머지는 재사용한다. 그리고 그 결정을 호출 수가 아니라 **prefix cache를 고려한 실제 추론 비용**으로 내린다.

```
편집(조건/tool 결과/memory) → dirty 전파(의존성 그래프) ∩ 요구된 출력의 조상
  → REUSE | REBUILD | RERUN → 재실행 결과가 같으면 전파 중단(early cutoff)
  → 제어 흐름이 갈라지면 LIVE 실행 + memo 재사용
  → prompt 조립은 stable-prefix 순서로(캐시 유지), probe 순서는 비용 모델로
```

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

## 지금 할 일

1. 팀이 설계 스펙을 읽고 §1.2 가정과 §13 열린 질문에 답한다.
2. 승인되면 구현 계획(`docs/superpowers/plans/`)을 쓰고 Phase 0(학습 2주)에 들어간다 — [roadmap.md](docs/roadmap.md).
3. 1주차 안에 Execution Lineage와 ICE 본문을 정독하고 [research-landscape.md §3.1](docs/research-landscape.md) 표를 갱신한다.
