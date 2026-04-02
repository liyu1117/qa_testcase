"""断言引擎 - 支持多种断言类型"""

import re
import logging
from dataclasses import dataclass

from jsonpath_ng import parse as jsonpath_parse

logger = logging.getLogger(__name__)


@dataclass
class AssertionResult:
    assertion_type: str
    path: str | None
    expected: str
    actual: str
    operator: str
    passed: bool
    error_msg: str | None = None


class AssertionEngine:
    """断言判定引擎"""

    def evaluate(self, assertions: list[dict], response_data: dict) -> list[AssertionResult]:
        """
        对响应数据执行断言列表
        response_data: {"status_code": int, "body": dict/str, "latency_ms": int, "headers": dict}
        """
        results = []
        for assertion in assertions:
            a_type = assertion.get("type", "")
            path = assertion.get("path")
            expected = str(assertion.get("expected", ""))
            operator = assertion.get("operator", "equals")

            try:
                result = self._evaluate_single(a_type, path, expected, operator, response_data)
                results.append(result)
            except Exception as e:
                results.append(AssertionResult(
                    assertion_type=a_type,
                    path=path,
                    expected=expected,
                    actual="ERROR",
                    operator=operator,
                    passed=False,
                    error_msg=str(e),
                ))

        return results

    def _evaluate_single(
        self, a_type: str, path: str | None, expected: str, operator: str, response_data: dict
    ) -> AssertionResult:
        """执行单条断言"""

        if a_type == "status_code":
            actual = str(response_data.get("status_code", ""))
            passed = self._compare(actual, expected, operator)
            return AssertionResult(a_type, None, expected, actual, operator, passed)

        elif a_type == "json_field":
            body = response_data.get("body", {})
            if isinstance(body, str):
                return AssertionResult(a_type, path, expected, body, operator, False, "响应体不是JSON")
            actual = self._extract_jsonpath(body, path)
            passed = self._compare(str(actual), expected, operator)
            return AssertionResult(a_type, path, expected, str(actual), operator, passed)

        elif a_type == "response_time":
            actual = str(response_data.get("latency_ms", 0))
            passed = self._compare(actual, expected, operator)
            return AssertionResult(a_type, None, expected, actual, operator, passed)

        elif a_type == "regex":
            body = response_data.get("body", {})
            actual = str(self._extract_jsonpath(body, path)) if path else str(body)
            pattern = expected.strip("/")
            passed = bool(re.search(pattern, actual))
            return AssertionResult(a_type, path, expected, actual, "regex_match", passed)

        elif a_type == "contains":
            body = response_data.get("body", {})
            actual = str(self._extract_jsonpath(body, path)) if path else str(body)
            passed = expected in actual
            return AssertionResult(a_type, path, expected, actual, "contains", passed)

        elif a_type == "header_field":
            headers = response_data.get("headers", {})
            actual = headers.get(path, "")
            passed = self._compare(str(actual), expected, operator)
            return AssertionResult(a_type, path, expected, str(actual), operator, passed)

        else:
            return AssertionResult(a_type, path, expected, "", operator, False, f"未知断言类型: {a_type}")

    def _extract_jsonpath(self, data: dict, path: str | None):
        """使用 JSONPath 提取值"""
        if not path or not data:
            return None
        try:
            matches = jsonpath_parse(path).find(data)
            if matches:
                return matches[0].value
            return None
        except Exception as e:
            logger.warning(f"JSONPath 解析失败: {path}, error: {e}")
            return None

    def _compare(self, actual: str, expected: str, operator: str) -> bool:
        """比较操作"""
        if operator == "equals":
            return actual == expected
        elif operator == "not_null":
            return actual is not None and actual != "" and actual != "None" and actual != "null"
        elif operator == "contains":
            return expected in actual
        elif operator == "less_than":
            try:
                return float(actual) < float(expected)
            except ValueError:
                return False
        elif operator == "greater_than":
            try:
                return float(actual) > float(expected)
            except ValueError:
                return False
        elif operator == "not_equals":
            return actual != expected
        else:
            logger.warning(f"未知操作符: {operator}")
            return False
