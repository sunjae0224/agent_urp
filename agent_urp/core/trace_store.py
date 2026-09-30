"""Append-only SQLite store for artifacts, blocks, env snapshots, runs, edits and step records."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from agent_urp.core.hashing import canonical_json
from agent_urp.core.models import Artifact, Block, Edit, Run, StepRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS artifacts (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS blocks (
    name TEXT, version TEXT, data TEXT NOT NULL, PRIMARY KEY (name, version)
);
CREATE TABLE IF NOT EXISTS envs (
    name TEXT, version TEXT, state TEXT NOT NULL, PRIMARY KEY (name, version)
);
CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS edits (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS steps (
    id TEXT PRIMARY KEY, run_id TEXT, seq INTEGER, data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS steps_run ON steps (run_id, seq);
CREATE TABLE IF NOT EXISTS memo (
    rowid INTEGER PRIMARY KEY AUTOINCREMENT, key_static TEXT, step_id TEXT
);
CREATE INDEX IF NOT EXISTS memo_key ON memo (key_static);
"""


class TraceStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(path))
        self._conn.executescript(_SCHEMA)

    # --- generic helpers -------------------------------------------------
    def _put(self, sql: str, *params: Any) -> None:
        with self._conn:
            self._conn.execute(sql, params)

    def _one(self, sql: str, *params: Any) -> tuple:
        row = self._conn.execute(sql, params).fetchone()
        if row is None:
            raise KeyError(params)
        return row

    # --- content-addressed objects ----------------------------------------
    def put_artifact(self, a: Artifact) -> None:
        self._put("INSERT OR IGNORE INTO artifacts VALUES (?, ?)", a.id, a.model_dump_json())

    def get_artifact(self, artifact_id: str) -> Artifact:
        row = self._one("SELECT data FROM artifacts WHERE id=?", artifact_id)
        return Artifact.model_validate_json(row[0])

    def put_block(self, b: Block) -> None:
        self._put("INSERT OR IGNORE INTO blocks VALUES (?, ?, ?)",
                  b.name, b.version, b.model_dump_json())

    def get_block(self, name: str, version: str) -> Block:
        return Block.model_validate_json(
            self._one("SELECT data FROM blocks WHERE name=? AND version=?", name, version)[0])

    def put_env_snapshot(self, name: str, version: str, state: Any) -> None:
        self._put("INSERT OR IGNORE INTO envs VALUES (?, ?, ?)",
                  name, version, canonical_json(state))

    def get_env_snapshot(self, name: str, version: str) -> Any:
        row = self._one("SELECT state FROM envs WHERE name=? AND version=?", name, version)
        return json.loads(row[0])

    # --- runs / edits -------------------------------------------------------
    def put_run(self, run: Run) -> None:
        self._put("INSERT OR REPLACE INTO runs VALUES (?, ?)", run.id, run.model_dump_json())

    def get_run(self, run_id: str) -> Run:
        return Run.model_validate_json(self._one("SELECT data FROM runs WHERE id=?", run_id)[0])

    def update_run_metrics(self, run_id: str, metrics: dict[str, Any]) -> None:
        run = self.get_run(run_id)
        self.put_run(run.model_copy(update={"metrics": metrics}))

    def put_edit(self, e: Edit) -> None:
        self._put("INSERT OR REPLACE INTO edits VALUES (?, ?)", e.id, e.model_dump_json())

    def get_edit(self, edit_id: str) -> Edit:
        return Edit.model_validate_json(self._one("SELECT data FROM edits WHERE id=?", edit_id)[0])

    # --- steps / memo --------------------------------------------------------
    def record_step(self, rec: StepRecord) -> None:
        self._put("INSERT OR REPLACE INTO steps VALUES (?, ?, ?, ?)", rec.id, rec.run_id, rec.seq,
                  rec.model_dump_json())

    def get_steps(self, run_id: str) -> list[StepRecord]:
        rows = self._conn.execute("SELECT data FROM steps WHERE run_id=? ORDER BY seq", (run_id,))
        return [StepRecord.model_validate_json(r[0]) for r in rows]

    def memo_put(self, rec: StepRecord) -> None:
        self._put("INSERT INTO memo (key_static, step_id) VALUES (?, ?)", rec.key_static, rec.id)

    def memo_candidates(self, key_static: str) -> list[StepRecord]:
        rows = self._conn.execute(
            "SELECT s.data FROM memo m JOIN steps s ON s.id = m.step_id "
            "WHERE m.key_static=? ORDER BY m.rowid DESC", (key_static,))
        return [StepRecord.model_validate_json(r[0]) for r in rows]

    def close(self) -> None:
        self._conn.close()
