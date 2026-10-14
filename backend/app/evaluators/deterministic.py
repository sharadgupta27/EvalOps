"""Cheap, deterministic evaluators. Run these before reaching for an LLM judge."""

import json
import re
from typing import Any

import jsonschema
from pydantic import Field, field_validator

from app.evaluators.base import CaseData, EvalScore, Evaluator, EvaluatorConfig
from app.evaluators.registry import register
from app.models import EvaluatorType


def _strip_code_fence(text: str) -> str:
    m = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", text, re.S)
    return m.group(1) if m else text


class ExactMatchConfig(EvaluatorConfig):
    case_sensitive: bool = False
    strip: bool = True


@register(EvaluatorType.exact_match)
class ExactMatch(Evaluator):
    config_model = ExactMatchConfig
    config: ExactMatchConfig

    async def evaluate(self, case: CaseData, output: str) -> EvalScore:
        if case.expected_output is None:
            return self._score(False, "case has no expected_output")
        a, b = output, case.expected_output
        if self.config.strip:
            a, b = a.strip(), b.strip()
        if not self.config.case_sensitive:
            a, b = a.lower(), b.lower()
        return self._score(a == b, "exact match" if a == b else "output differs from expected")


class ContainsConfig(EvaluatorConfig):
    value: str | None = Field(default=None, description="Defaults to the case's expected_output")
    case_sensitive: bool = False


@register(EvaluatorType.contains)
class Contains(Evaluator):
    config_model = ContainsConfig
    config: ContainsConfig

    async def evaluate(self, case: CaseData, output: str) -> EvalScore:
        needle = self.config.value if self.config.value is not None else case.expected_output
        if not needle:
            return self._score(False, "nothing to look for: set config.value or expected_output")
        hay = output if self.config.case_sensitive else output.lower()
        n = needle if self.config.case_sensitive else needle.lower()
        found = n in hay
        return self._score(found, f"{'found' if found else 'missing'}: {needle!r}")


class RegexConfig(EvaluatorConfig):
    pattern: str
    must_match: bool = True

    @field_validator("pattern")
    @classmethod
    def _compiles(cls, v: str) -> str:
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"invalid regex: {e}") from e
        return v


@register(EvaluatorType.regex)
class Regex(Evaluator):
    config_model = RegexConfig
    config: RegexConfig

    async def evaluate(self, case: CaseData, output: str) -> EvalScore:
        matched = re.search(self.config.pattern, output) is not None
        passed = matched == self.config.must_match
        verb = "matches" if matched else "does not match"
        return self._score(passed, f"output {verb} /{self.config.pattern}/")


class JsonSchemaConfig(EvaluatorConfig):
    json_schema: dict[str, Any] = Field(alias="schema")

    model_config = EvaluatorConfig.model_config | {"populate_by_name": True}

    @field_validator("json_schema")
    @classmethod
    def _valid_schema(cls, v: dict[str, Any]) -> dict[str, Any]:
        try:
            jsonschema.Draft202012Validator.check_schema(v)
        except jsonschema.SchemaError as e:
            raise ValueError(f"invalid JSON Schema: {e.message}") from e
        return v

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        return super().model_dump(by_alias=True, **kwargs)


@register(EvaluatorType.json_schema)
class JsonSchema(Evaluator):
    config_model = JsonSchemaConfig
    config: JsonSchemaConfig

    async def evaluate(self, case: CaseData, output: str) -> EvalScore:
        try:
            data = json.loads(_strip_code_fence(output))
        except json.JSONDecodeError as e:
            return self._score(False, f"not valid JSON: {e.msg}")
        errors = sorted(
            jsonschema.Draft202012Validator(self.config.json_schema).iter_errors(data),
            key=lambda e: list(e.path),
        )
        if errors:
            where = "/".join(map(str, errors[0].path)) or "(root)"
            return self._score(False, f"schema violation at {where}: {errors[0].message}")
        return self._score(True, "valid JSON matching schema")
