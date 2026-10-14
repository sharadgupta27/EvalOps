"""`{{variable}}` prompt templates. Deliberately tiny: no logic, no code execution."""

import re
from typing import Any

_VAR = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


class TemplateError(ValueError):
    pass


def variables(template: str) -> list[str]:
    seen: dict[str, None] = {}
    for m in _VAR.finditer(template):
        seen.setdefault(m.group(1), None)
    return list(seen)


def render(template: str, inputs: dict[str, Any]) -> str:
    missing = [v for v in variables(template) if v not in inputs]
    if missing:
        raise TemplateError(f"missing input variable(s): {', '.join(missing)}")

    def sub(m: re.Match[str]) -> str:
        value = inputs[m.group(1)]
        return value if isinstance(value, str) else str(value)

    return _VAR.sub(sub, template)
