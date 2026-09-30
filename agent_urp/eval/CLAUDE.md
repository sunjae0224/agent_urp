# agent_urp/eval/ — 시나리오 · 지표 · CLI

## 역할

워크로드 + 편집 + "정답으로 무엇이 재실행돼야 하는가"를 묶은 `Scenario`를 정의하고, 정책별로 돌려 stale reuse/과잉 재실행을 채점한다.

## 파일별

- `scenarios.py` — `Scenario` dataclass, `S1_budget_edit`, `S5_noop_edit`, `SCENARIOS` 딕셔너리.
- `metrics.py` — `summarize(result)`(호출·토큰 요약), `audit(result, scenario, oracle, level=Level.L0)`(stale/over-rerun/일치 판정). `_content`는 출력 안의 Artifact를 dict/list/tuple 안까지 재귀적으로 내용으로 바꾼다(`created_by`는 run마다 다르므로).
- `run_matrix.py` — CLI: 시나리오마다 base 실행 + FULL oracle 편집 실행 + 요청된 정책들로 replay, 표 출력. `run_scenario`는 자기 `level`로 audit한다.

## Scenario 필드

`must_rerun`은 "정답에 영향을 주는 step 집합 G" — 편집 후 이 중 하나라도 REUSE되면 `stale_reuse`(오답 위험). `must_not_rerun`은 "편집과 무관한 step" — 이 중 하나라도 실행되면 `over_rerun`(낭비, 오답은 아님). 두 집합은 워크로드를 우리가 만들었기 때문에 사람이 미리 정한 정답이다.

## 표 컬럼

`scenario, policy, executed, reused, llm_calls, tool_calls, input_tokens, output_tokens, stale_reuse, over_rerun, matches_full`. `matches_full`은 이 정책의 출력이 FULL(oracle) 출력과 **run의 동등성 level에서** 같은지다: `equivalent(Artifact.of("out", a), Artifact.of("out", b), level)` — L0는 완전 동일, L1은 공백·숫자·키 순서 정규화 후 동일(L1 backdating이 L1-동등한 옛 출력을 그대로 쓰는 것을 불일치로 세지 않기 위함).

## CLI 사용법

```
uv run python -m agent_urp.eval.run_matrix --scenarios S1,S5 --policies full,suffix,memo,dep [--level 0] [--layout naive] [--db :memory:]
```

모르는 시나리오/정책 이름은 유효한 이름 목록과 함께 오류(exit 2); `--layout`은 `naive|stable_prefix`, `--level`은 `0|1`만. `--db PATH`면 부모 폴더가 없을 때 만든다(SQLite 파일, 실행마다 누적).

## S1/S5 기대 수치 (level=0, `tests/test_run_matrix.py`가 고정; `--level 1 --layout stable_prefix`도 같다)

- S1(예산 2000→1200): full/memo executed=5, suffix executed=3(`over_rerun=[get_weather]`), dep executed=2(`over_rerun=[]`, `llm_calls=2`, `tool_calls=0`).
- S5(같은 뜻 재표현): dep executed=1(`over_rerun=[]`), suffix `over_rerun=[compose_plan, get_weather]`.
- 두 시나리오·모든 정책에서 `stale_reuse == []`, `matches_full == True`.

## 구현된 것 · 안 된 것

- 구현: S1, S5, 4개 정책 비교, CLI 표 출력.
- 안 됨: S2~S4/S6 시나리오, cost 컬럼(§7.2).
