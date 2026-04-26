"""画框模板 **入参** 框架（与具体模板业务解耦）。

业务侧（各 ``WallTemplate`` 包）只维护 ``param_schema``（JSON 或 ``field_string`` / ``field_boolean``）。
本模块负责：加载与规范化 schema、**写入场景前的** ``templateParams`` 清洗与必填校验、
``show-now`` 的 patch 合并。HTTP 路由应调用本模块的公开函数，不重复实现合并规则。

公开入口（业务接入只需提供 ``param_schema``）：

- ``load_param_schema_json`` / ``field_string`` / ``field_boolean``
- ``normalize_scene_template_params`` + ``validate_scene_template_params_required``
- ``merge_incoming_template_params``（仅 ``POST .../templates/<id>/show-now`` 使用）
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Final

log = logging.getLogger(__name__)

# 字符串入参在存储与合并时的最大长度（不在 schema 中按字段配置）。
DEFAULT_STRING_MAX_LEN: Final[int] = 2000

_ALLOWED_TYPES: Final[frozenset[str]] = frozenset({"string", "boolean"})


def field_string(
    key: str,
    *,
    name: str = "",
    description: str = "",
    required: bool = False,
    default: str = "",
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "key": key.strip(),
        "type": "string",
        "required": required,
        "default": default,
    }
    if name.strip():
        out["name"] = name.strip()
    if description:
        out["description"] = description
    return out


def field_boolean(
    key: str,
    *,
    name: str = "",
    description: str = "",
    required: bool = False,
    default: bool = False,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "key": key.strip(),
        "type": "boolean",
        "required": required,
        "default": default,
    }
    if name.strip():
        out["name"] = name.strip()
    if description:
        out["description"] = description
    return out


def _bool_default(meta: dict[str, Any]) -> bool:
    d = meta.get("default")
    if isinstance(d, bool):
        return d
    return False


def _string_default(meta: dict[str, Any]) -> str:
    d = meta.get("default")
    if isinstance(d, str):
        return d
    if d is None:
        return ""
    return str(d)


def _coerce_bool_value(v: Any, fallback: bool) -> bool:
    """与 Web 端 ``boolFromUnknown`` 约定一致（便于跨端与手工 API）。"""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) and v in (0, 1):
        return bool(int(v))
    if isinstance(v, str):
        x = v.strip().lower()
        if x in ("true", "1", "yes", "on"):
            return True
        if x in ("false", "0", "no", "off", ""):
            return False
    return fallback


def _iter_schema_fields(schema_fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in schema_fields:
        if isinstance(f, dict) and f.get("key"):
            out.append(f)
    return out


def _normalize_field(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    key = raw.get("key")
    typ = raw.get("type")
    if not isinstance(key, str) or not key.strip():
        return None
    if typ not in _ALLOWED_TYPES:
        log.warning("ui_params: skip field with unknown type %r key=%r", typ, key)
        return None
    out: dict[str, Any] = {
        "key": key.strip(),
        "type": typ,
        "required": bool(raw.get("required")) if raw.get("required") is not None else False,
    }
    if isinstance(raw.get("description"), str) and raw["description"].strip():
        out["description"] = raw["description"].strip()
    if isinstance(raw.get("name"), str) and raw["name"].strip():
        out["name"] = raw["name"].strip()
    if typ == "string":
        if "default" in raw:
            d = raw.get("default")
            out["default"] = d if isinstance(d, str) else ("" if d is None else str(d))
        else:
            out["default"] = ""
    else:
        if "default" in raw:
            out["default"] = _coerce_bool_value(raw.get("default"), False)
        else:
            out["default"] = False
    return out


def load_param_schema_json(path: str | Path) -> list[dict[str, Any]]:
    """从 JSON 文件加载 ``paramSchema`` 列表；文件不存在或无效时返回 ``[]``。"""
    p = Path(path)
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        log.warning("ui_params: cannot read %s: %s", p, e)
        return []
    if isinstance(raw, dict) and "fields" in raw:
        raw = raw["fields"]
    if not isinstance(raw, list):
        log.warning("ui_params: root must be a list or {{\"fields\": [...]}} in %s", p)
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        norm = _normalize_field(item)
        if norm is not None:
            out.append(norm)
    return out


def _apply_string_incoming_to_store(
    store: dict[str, Any],
    meta: dict[str, Any],
    raw_v: Any,
    *,
    delete_when_none: bool,
) -> None:
    """根据 schema 写入或删除 string 键（``delete_when_none``：``v is None`` 时是否删除可选键）。"""
    k = str(meta["key"])
    required = bool(meta.get("required"))
    cap = DEFAULT_STRING_MAX_LEN

    if raw_v is None:
        if delete_when_none:
            if not required:
                store.pop(k, None)
            return
        return

    s = raw_v if isinstance(raw_v, str) else str(raw_v)
    s = s[:cap]
    if not s.strip() and not required:
        store.pop(k, None)
    else:
        store[k] = s


def _apply_bool_incoming_to_store(store: dict[str, Any], meta: dict[str, Any], raw_v: Any) -> None:
    k = str(meta["key"])
    store[k] = _coerce_bool_value(raw_v, _bool_default(meta))


def normalize_scene_template_params(
    schema_fields: list[dict[str, Any]],
    incoming: dict[str, Any] | None,
) -> dict[str, Any]:
    """从请求体构建**仅含 schema 声明键**的 ``templateParams``，供场景落库。

    - 去掉 schema 外的键（防脏数据）。
    - ``boolean``：始终写入规范化布尔值。
    - ``string``：截断至 ``DEFAULT_STRING_MAX_LEN``；可选且仅空白则**省略**该键。
    - ``string`` 键缺失且可选：省略；缺失且必填：不写键（由校验捕获）。
    """
    inc = dict(incoming or {})
    out: dict[str, Any] = {}
    for meta in _iter_schema_fields(schema_fields):
        k = str(meta["key"])
        typ = meta.get("type")
        if typ == "boolean":
            out[k] = _coerce_bool_value(inc.get(k), _bool_default(meta))
            continue
        if typ != "string":
            continue
        if k not in inc:
            continue
        raw_v = inc[k]
        tmp: dict[str, Any] = {}
        _apply_string_incoming_to_store(tmp, meta, raw_v, delete_when_none=False)
        out.update(tmp)
    return out


def validate_scene_template_params_required(
    schema_fields: list[dict[str, Any]],
    params: dict[str, Any],
) -> str | None:
    """若违反必填规则，返回英文短错误信息（HTTP ``error`` 字段）；否则 ``None``。

    说明：``required`` 对 ``boolean`` 暂不生效（开关总有值）；仅校验 ``string``。
    """
    for meta in _iter_schema_fields(schema_fields):
        if not bool(meta.get("required")):
            continue
        if meta.get("type") != "string":
            continue
        k = str(meta["key"])
        s = params.get(k)
        if not isinstance(s, str) or not s.strip():
            return f"required template param {k!r} is missing or empty"
    return None


def merge_incoming_template_params(
    schema_fields: list[dict[str, Any]],
    base_params: dict[str, Any],
    incoming: dict[str, Any],
) -> dict[str, Any]:
    """将 HTTP ``templateParams`` patch 合并进 ``base_params``（仅 schema 声明的键）。"""
    allowed = {str(f["key"]): f for f in _iter_schema_fields(schema_fields)}
    merged: dict[str, Any] = {**(base_params or {})}
    if not allowed:
        return merged
    for k, v in incoming.items():
        if k not in allowed:
            continue
        meta = allowed[k]
        typ = meta.get("type")
        if typ == "boolean":
            _apply_bool_incoming_to_store(merged, meta, v)
            continue
        if typ == "string":
            if v is None:
                if not bool(meta.get("required")):
                    merged.pop(k, None)
                continue
            _apply_string_incoming_to_store(merged, meta, v, delete_when_none=False)
    return merged


def scene_template_params_after_model(
    schema_fields: list[dict[str, Any]],
    template_params: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    """场景 ``Scene.model_validate`` 之后调用：规范化并校验 ``templateParams``。

    返回 ``(normalized, error)``；``error`` 非空表示应 ``400`` 拒绝写入。
    """
    normalized = normalize_scene_template_params(schema_fields, template_params)
    err = validate_scene_template_params_required(schema_fields, normalized)
    return normalized, err
