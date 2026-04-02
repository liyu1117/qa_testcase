"""pytest 脚本执行器 - 通过 subprocess 运行 pytest 并解析 JSON 报告"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PytestTestResult:
    """单个 pytest 测试函数的结果"""
    nodeid: str                          # e.g. "test_api.py::test_case_001_login_success"
    outcome: str                         # passed / failed / skipped / error
    duration_ms: int = 0
    error_message: Optional[str] = None
    error_longrepr: Optional[str] = None  # 完整错误栈


@dataclass
class PytestReport:
    """pytest 执行报告"""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    error: int = 0
    duration: float = 0.0
    test_results: list[PytestTestResult] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""


CONFTEST_TEMPLATE = '''"""由 QA Master 自动生成的 conftest.py"""

import json
import os

import pytest


@pytest.fixture(scope="session")
def base_url():
    """从环境变量读取 Base URL"""
    return os.environ.get("BASE_URL", "{default_base_url}")


@pytest.fixture(scope="session")
def default_headers():
    """从环境变量读取默认请求头"""
    raw = os.environ.get("DEFAULT_HEADERS", '{default_headers_json}')
    return json.loads(raw)


@pytest.fixture(scope="session")
def timeout():
    """从环境变量读取请求超时时间"""
    return int(os.environ.get("REQUEST_TIMEOUT", "{default_timeout}"))
'''


class PytestRunner:
    """通过 subprocess 执行 pytest 脚本并解析结果"""

    def __init__(self, timeout: int = 300):
        self.timeout = timeout

    async def execute(
        self,
        script_content: str,
        env_config: dict,
        work_dir: Path,
        script_filename: str = "test_api.py",
    ) -> PytestReport:
        """
        执行 pytest 脚本

        Args:
            script_content: pytest 脚本内容
            env_config: 环境配置 {base_url, headers, timeout, ...}
            work_dir: 工作目录
            script_filename: 脚本文件名（基于接口路径生成）

        Returns:
            PytestReport 执行报告
        """
        work_dir.mkdir(parents=True, exist_ok=True)

        # 1. 写入测试脚本
        script_path = work_dir / script_filename
        script_path.write_text(script_content, encoding="utf-8")

        # 2. 生成 conftest.py
        conftest_content = self._generate_conftest(env_config)
        conftest_path = work_dir / "conftest.py"
        conftest_path.write_text(conftest_content, encoding="utf-8")

        # 3. 构建 pytest 命令
        report_json_path = work_dir / "report.json"
        cmd = [
            "pytest",
            str(script_path),
            f"--json-report-file={report_json_path}",
            "--json-report",
            "-v",
            "--tb=short",
            "--no-header",
        ]

        # 4. 构建环境变量
        env_vars = dict(os.environ)
        env_vars["BASE_URL"] = env_config.get("base_url", "http://localhost:8000")
        env_vars["REQUEST_TIMEOUT"] = str(env_config.get("timeout", 30))
        headers = env_config.get("headers", {})
        if headers:
            env_vars["DEFAULT_HEADERS"] = json.dumps(headers, ensure_ascii=False)
        else:
            env_vars["DEFAULT_HEADERS"] = "{}"

        logger.info(f"执行 pytest: {' '.join(cmd)}")
        logger.info(f"工作目录: {work_dir}")

        # 5. 执行 pytest
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(work_dir),
                env=env_vars,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout,
            )

            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            logger.info(f"pytest 退出码: {process.returncode}")
            if stderr_text.strip():
                logger.warning(f"pytest stderr:\n{stderr_text[:500]}")

        except asyncio.TimeoutError:
            logger.error(f"pytest 执行超时 ({self.timeout}s)")
            return PytestReport(
                stderr=f"pytest 执行超时 ({self.timeout}s)",
            )

        # 6. 解析 JSON 报告
        if report_json_path.exists():
            try:
                raw_report = json.loads(report_json_path.read_text(encoding="utf-8"))
                report = self._parse_json_report(raw_report)
                report.stdout = stdout_text
                report.stderr = stderr_text
                return report
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"JSON 报告解析失败: {e}")

        # 回退：从 stdout 推断结果
        return self._parse_stdout_fallback(stdout_text, stderr_text)

    def _generate_conftest(self, env_config: dict) -> str:
        """生成 conftest.py"""
        default_base_url = env_config.get("base_url", "http://localhost:8000")
        default_timeout = str(env_config.get("timeout", 30))
        headers = env_config.get("headers", {})
        # 转义 JSON 中的单引号
        default_headers_json = json.dumps(headers, ensure_ascii=False).replace("'", "\\'")

        return CONFTEST_TEMPLATE.format(
            default_base_url=default_base_url,
            default_headers_json=default_headers_json,
            default_timeout=default_timeout,
        )

    def _parse_json_report(self, raw: dict) -> PytestReport:
        """解析 pytest-json-report 的 JSON 输出"""
        test_results = []

        # 检查收集阶段是否有错误（语法错误、导入失败等）
        for collector in raw.get("collectors", []):
            if collector.get("outcome") == "failed":
                longrepr = collector.get("longrepr", "")
                error_msg = longrepr.split("\n")[-1].strip() if longrepr else "用例收集失败"
                raise RuntimeError(f"pytest 用例收集失败: {error_msg}")

        for test in raw.get("tests", []):
            nodeid = test.get("nodeid", "")
            outcome = test.get("outcome", "unknown")
            duration_s = test.get("duration", 0)

            error_message = None
            error_longrepr = None

            if outcome in ("failed", "error"):
                call_info = test.get("call", {})
                crash = call_info.get("crash", {})
                error_message = crash.get("message", "")
                longrepr = call_info.get("longrepr", "")
                error_longrepr = longrepr if isinstance(longrepr, str) else str(longrepr)

            test_results.append(PytestTestResult(
                nodeid=nodeid,
                outcome=outcome,
                duration_ms=int(duration_s * 1000),
                error_message=error_message,
                error_longrepr=error_longrepr,
            ))

        summary = raw.get("summary", {})

        return PytestReport(
            total=summary.get("total", len(test_results)),
            passed=summary.get("passed", 0),
            failed=summary.get("failed", 0),
            skipped=summary.get("skipped", 0),
            error=summary.get("error", 0),
            duration=raw.get("duration", 0.0),
            test_results=test_results,
        )

    def _parse_stdout_fallback(self, stdout: str, stderr: str) -> PytestReport:
        """从 stdout 推断结果（当 JSON 报告不可用时的回退方案）"""
        import re

        report = PytestReport(stdout=stdout, stderr=stderr)

        # 尝试解析 pytest 汇总行：如 "5 passed, 2 failed, 1 skipped in 1.23s"
        summary_match = re.search(
            r"(\d+) passed.*?(\d+) failed|(\d+) passed|(\d+) failed",
            stdout,
        )
        if summary_match:
            # 简单解析
            passed_match = re.search(r"(\d+) passed", stdout)
            failed_match = re.search(r"(\d+) failed", stdout)
            skipped_match = re.search(r"(\d+) skipped", stdout)
            error_match = re.search(r"(\d+) error", stdout)

            report.passed = int(passed_match.group(1)) if passed_match else 0
            report.failed = int(failed_match.group(1)) if failed_match else 0
            report.skipped = int(skipped_match.group(1)) if skipped_match else 0
            report.error = int(error_match.group(1)) if error_match else 0
            report.total = report.passed + report.failed + report.skipped + report.error

        return report
