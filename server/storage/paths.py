from __future__ import annotations

import pathlib


def repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent


def data_dir() -> pathlib.Path:
    d = repo_root() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> pathlib.Path:
    return data_dir() / "config.json"


def schedule_state_path() -> pathlib.Path:
    return data_dir() / "schedule_state.json"


def wall_runs_path() -> pathlib.Path:
    return data_dir() / "wall_runs.jsonl"


def recent_ai_mottos_path() -> pathlib.Path:
    """JSONL of recent ai_motto outputs for prompt de-duplication (see templates.ai_motto.diversity)."""
    return data_dir() / "recent_ai_mottos.jsonl"


def output_dir() -> pathlib.Path:
    o = data_dir() / "output"
    o.mkdir(parents=True, exist_ok=True)
    return o


def run_output_dir(run_id: str) -> pathlib.Path:
    p = output_dir() / run_id
    p.mkdir(parents=True, exist_ok=True)
    return p
