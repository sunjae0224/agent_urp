# agent_urp/workloads/ — 평가용 워크로드

## 역할

`core.runtime`/`llm`/`tools`를 조합한 실제 agent 프로그램. `agent_urp.eval.scenarios`가 여기서 `program`/`blocks`/`env`/`scripted_llm`을 가져다 편집 시나리오를 만든다.

## 파일별

- `trip_planner.py` — S1 워크로드: 예산 제약이 있는 5-step 여행 계획 agent.

## 워크로드 작성 규칙

- `program(ctx)`는 **결정적** Python 함수여야 한다(비용이 드는 일은 전부 `@step`으로 감싼 호출에서만 일어난다) — 분기는 `ctx.block`/`ctx.env` 값으로만 하고, 그 읽기가 `orchestration_reads`로 자동 기록된다.
- **step 하나당 LLM 호출은 최대 1개**(`ctx.llm(...)`을 두 번 부르면 그 step의 `key_static` 하나에 두 콜이 묶여 재사용 판정이 애매해진다).
- LLM step의 입력은 `extra=json.dumps({"task": "<step 이름>", ...}, sort_keys=True)`로 넘긴다 — `ContextAssembler`가 이를 `[input]\n{...}` 블록으로 prompt 끝에 붙이고, `ScriptedLLM` 규칙은 `"task": "..."`로 어느 step인지 구분한다(`_extra()`처럼 `prompt.split("[input]\n", 1)[1]`로 다시 파싱).
- 다른 step의 출력을 쓸 때는 **top-level kwarg로 `Artifact`를 그대로 전달**한다(`pick_hotel(ctx, hotels=hotels, flights=flights)`) — artifact는 파라미터 이름으로 키가 잡히므로 이름을 정확히 써야 한다(core/CLAUDE.md).
- 워크로드는 **env를 mutate하지 않는다**(v1 제약, `EnvMutatedInStep`).

## trip_planner: 단계·순서·기대 출력

순서: `search_flights` → `search_hotels` → `pick_hotel`(LLM) → `get_weather` → `compose_plan`(LLM). **`get_weather`는 예산과 무관한데도 `pick_hotel` 뒤에 온다** — SUFFIX는 이를 못 알아채고 재실행, DEP는 읽은 게 없으니 재사용(`test_trip_planner.py`가 이 구도를 검증).

- 예산 2000 USD(base): 해변 호텔 중 예산 내 `price_per_night`가 가장 비싼 곳 → **Ocean Grand**(1580 ≤ 2000).
- 예산 1200 USD로 편집: Ocean Grand는 초과(1580 > 1200) → **Seaside Suites**(700 ≤ 1200).
- 두 경우 모두 `PLAN: fly Jin Air ($180), stay at <hotel>, weather sunny, 24C`.

## 구현된 것 · 안 된 것

- 구현: trip_planner(S1) 하나.
- 안 됨: S2~S4 워크로드(제어 흐름 분기, memory 정정 등 다른 perturbation용) — `docs/superpowers/specs/`에는 있으나 미구현.
