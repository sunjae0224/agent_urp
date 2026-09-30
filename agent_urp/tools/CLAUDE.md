# agent_urp/tools/ — mock 환경 + tool

## 역할

실제 외부 시스템 대신 쓰는 버전 있는 in-memory 상태(`VersionedEnv`)와 그 위의 mock tool 두 개. Runtime이 read set을 자동 기록하려면 상태 접근이 항상 버전을 낼 수 있어야 하므로 존재한다.

## 파일별

- `env.py` — `VersionedEnv(name, state)`: dict 상태 + content-addressed `version`.
- `search.py` — `search(env, query, limit=5)`: `env["docs"]`에 대한 mock 검색.
- `db.py` — `db_query(env, table, where=None)`: `env["tables"][table]`에 대한 mock 테이블 조회.

## 사용법

- **`VersionedEnv.version`**: `content_hash(self.state)` — `name`은 버전에 영향 없다(같은 state → 같은 version, 이름이 달라도). 매번 계산되는 property이지, 캐시된 값이 아니다.
- **`get(path, default=None)`**: 점(`.`) 구분 경로로 중첩 dict를 읽는다(`e.get("a.b")`); 없으면 `default`, 깊은 복사본을 돌려준다.
- **`set(path, value)`** / **`update({path: value, ...})`**: 중간 dict를 `setdefault`로 만들며 마지막 키에 값을 쓴다(깊은 복사 저장). state가 바뀌므로 `version`도 바뀐다.
- **`snapshot()`** → `(name, version, deepcopy(state))`; **`VersionedEnv.restore(name, state)`**로 되돌린다. `TraceStore.put_env_snapshot`/`get_env_snapshot`이 이 튜플로 저장·복원한다.
- **`search`**: query를 공백으로 나눈 단어별로 title+text에서 대소문자 무시 매칭, 맞은 단어 수 내림차순(동점이면 `id` 오름차순)으로 정렬 후 `limit`개.
- **`db_query`**: `where`의 모든 key=value가 같은 행만 남긴다(등호 필터만, 없으면 전체).

## 바꿀 때 주의

- **env는 step 안에서 `ctx.env(name)`으로만 접근한다.** 직접 `VersionedEnv` 인스턴스를 들고 다니며 step 밖에서 `.set()`을 부르면 runtime이 read/write로 기록하지 못한다(core/CLAUDE.md의 "orchestration mutate는 막혀 있지 않다" 참고 — 규약 위반이어도 예외가 나지 않는다).
- 새 tool을 추가할 때도 이 패턴(순수 함수 `(env, ...) -> 결과`, env는 인자로만 받음)을 따른다 — tool이 자체적으로 env를 들고 있지 않게 한다.

## 구현된 것 · 안 된 것

- 구현: dotted-path get/set, snapshot/restore, search, db_query.
- 안 됨: env write를 StepRecord에 기록해 DEP가 검증하게 하는 것(core/CLAUDE.md 참고) — 지금은 tool 결과(반환값)만 artifact로 기록되고, env 자체의 변형은 추적 대상이 아니다.
