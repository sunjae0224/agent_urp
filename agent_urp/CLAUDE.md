# agent_urp/ — 패키지 지도

`core`가 데이터 모델과 실행 엔진, 나머지는 그 위에 얹히는 조각들이다. 각 폴더의 역할·파일별 설명·구현 상태는 해당 폴더의 CLAUDE.md에 있다(여기는 지도만; 공통 규칙은 루트 CLAUDE.md).

## 하위 폴더

- agent_urp/core/ → agent_urp/core/CLAUDE.md
- agent_urp/llm/ → agent_urp/llm/CLAUDE.md
- agent_urp/tools/ → agent_urp/tools/CLAUDE.md
- agent_urp/workloads/ → agent_urp/workloads/CLAUDE.md
- agent_urp/eval/ → agent_urp/eval/CLAUDE.md

## import 계층

`core ← llm, tools ← workloads ← eval`. core는 llm/tools의 구현체(scripted, cassette, search, db)에는 의존하지 않지만, `core/runtime.py`는 `llm.base.LLMBackend`(Protocol)와 `tools.env.VersionedEnv` 타입은 가져다 쓴다 — 순환은 아니다: `llm/base.py`는 core.models만, `tools/env.py`는 core.hashing만 참조한다. 상위(core)가 하위 구현체를 import하는 방향은 없고, workloads/eval만 셋을 조합한다.

## 파일

- `agent_urp/__init__.py` — `__version__ = "0.1.0"`만 정의.
