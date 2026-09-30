# agent_urp/llm/ — LLM 백엔드

## 역할

`Runtime`이 쓰는 LLM을 교체 가능하게 만드는 얇은 계층. 전부 `LLMBackend` Protocol 하나를 만족한다.

## 파일별

- `base.py` — `LLMResponse{text, usage: Usage}`, `LLMBackend` Protocol: `name: str`, `complete(prompt, params=None) -> LLMResponse`. `@runtime_checkable`이라 `isinstance(x, LLMBackend)`로 검사 가능.
- `scripted.py` — `ScriptedLLM(rules, default="OK")`: 결정적 rule 매칭 백엔드. offline 테스트·워크로드 전용.
- `cassette.py` — `CassetteLLM(path, inner=None, mode="auto")`: 실제(또는 scripted) 백엔드 호출을 JSON 파일 하나에 기록/재생.

## 사용법

- **ScriptedLLM 규칙 형식**: `Rule = tuple[pattern, responder]`. `pattern`은 `str`(내부에서 `re.compile(p, re.S)`) 또는 이미 컴파일된 `re.Pattern`. `responder`는 고정 문자열이거나 `(prompt, match) -> str` 콜러블. 규칙은 **목록 순서대로** 검사해 `pattern.search(prompt)`가 처음 맞는 것이 이긴다; 아무것도 안 맞으면 `default`. `usage`는 `input_tokens=len(prompt.split())`, `output_tokens=len(text.split())`(공백 기준 단어 수 — 토크나이저 아님).
- **CassetteLLM 키**: `content_hash({"backend": inner.name, "prompt": prompt, "params": dict(params or {})})` — inner가 없으면(재생 전용) 저장된 `_backend` 필드로 대신한다. prompt/params가 조금만 달라도 다른 키.
- **모드**: `"auto"`(기본) — 키가 있으면 캐시 사용, 없으면 inner 호출 후 저장(inner 없으면 `CassetteMiss`). `"record"` — 캐시를 무시하고 **항상 inner를 호출**해 덮어쓴다. `"replay"` — inner를 절대 호출하지 않고, 미스면 무조건 `CassetteMiss`(inner가 있어도).
- 파일은 매 미스마다 즉시 저장된다(`_save`, indent+sort_keys). 저장은 원자적이다: `<path>.tmp`에 쓴 뒤 `os.replace`로 바꿔치기하므로 저장 도중 죽어도 이전 파일이 온전히 남는다.
- 열 때 파일이 비었거나 JSON이 아니거나 최상위가 dict가 아니면 `ValueError("corrupt cassette file: <path>")` — 조용히 빈 cassette로 시작하지 않는다.

## 구현된 것 · 안 된 것

- 구현: scripted, cassette(record/replay/auto 3모드, 원자적 저장, 손상 파일 감지).
- 안 됨: 실제 네트워크 백엔드(`anthropic.py`, `openai_compat.py`) — `base.py`의 Protocol만 있고 구현체는 없다. 손상된 cassette의 자동 복구도 없다(오류를 내고 멈춘다).
