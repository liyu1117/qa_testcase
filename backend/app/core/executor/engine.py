"""测试用例执行引擎调度器"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.execution_job import ExecutionJob
from backend.app.models.execution_result import ExecutionResult
from backend.app.models.generation_job import GenerationJob
from backend.app.models.testcase import Testcase
from backend.app.core.executor.variable_resolver import VariableResolver
from backend.app.core.executor.http_runner import HttpRunner
from backend.app.core.executor.assertion import AssertionEngine
from backend.app.core.executor.report_builder import ReportBuilder
from backend.app.core.notifier.dingtalk import DingtalkNotifier
from backend.config import settings

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """接口测试用例自动化执行引擎"""

    def __init__(self, db: AsyncSession, concurrency: int = 5):
        self.db = db
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)

    async def run(self, job_id: int):
        """执行测试任务 - 根据 execution_mode 选择执行方式"""
        job = await self.db.get(ExecutionJob, job_id)
        if not job:
            logger.error(f"执行任务 {job_id} 不存在")
            return

        if job.execution_mode == "pytest":
            await self._run_with_pytest(job)
        else:
            await self._run_with_httpx(job)

    @staticmethod
    def _derive_script_filename(gen_job) -> str:
        """根据 GenerationJob 的接口路径生成脚本文件名
        
        例: /next/app/vip/send/v2 → test_vip_send_v2.py
        """
        paths = gen_job.yapi_interface_paths if gen_job else None
        if not paths or not isinstance(paths, list) or len(paths) == 0:
            return "test_api.py"

        # 取第一个接口路径
        api_path = paths[0]
        # 移除前缀和后缀斜线
        api_path = api_path.strip("/")
        # 取路径后几段避免太长（最多取最后3段）
        parts = [p for p in api_path.split("/") if p]
        if len(parts) > 3:
            parts = parts[-3:]
        # 拼接并清理非法字符
        name = "_".join(parts)
        name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        name = re.sub(r"_+", "_", name).strip("_")

        if not name:
            return "test_api.py"

        return f"test_{name}.py"

    # ──────── pytest 模式 ────────

    async def _run_with_pytest(self, job: ExecutionJob):
        """使用 pytest subprocess 执行"""
        from backend.app.core.executor.pytest_runner import PytestRunner

        job.status = "running"
        job.started_at = datetime.utcnow()
        await self.db.commit()

        start_time = time.monotonic()

        try:
            # 1. 收集关联的 pytest 脚本内容
            script_content = await self._collect_pytest_script(job)
            if not script_content:
                raise ValueError("未找到关联的 pytest 脚本内容，请先生成接口测试用例")

            # 1.5 根据接口路径派生脚本文件名
            gen_job = await self.db.get(GenerationJob, job.generation_job_id) if job.generation_job_id else None
            script_filename = self._derive_script_filename(gen_job)

            # 2. 执行 pytest
            runner = PytestRunner(timeout=job.env_config.get("timeout", 300) if job.env_config else 300)
            work_dir = settings.pytest_scripts_dir / f"exec_{job.id}"

            report = await runner.execute(
                script_content=script_content,
                env_config=job.env_config or {},
                work_dir=work_dir,
                script_filename=script_filename,
            )

            job.pytest_script_path = str(work_dir / script_filename)

            # 3. 映射 pytest 结果到 ExecutionResult
            await self._map_pytest_results(job, report)

            # 4. 更新任务统计
            job.passed = report.passed
            job.failed = report.failed
            job.skipped = report.skipped
            job.duration = round(time.monotonic() - start_time, 2)
            job.finished_at = datetime.utcnow()

            if report.failed == 0 and report.error == 0:
                job.status = "success"
            elif report.passed > 0:
                job.status = "partial_fail"
            else:
                job.status = "failed"

            # 5. 生成报告
            report_builder = ReportBuilder()
            report_results = self._build_pytest_report_results(report)
            report_content = report_builder.build(
                job_data={
                    "name": job.name,
                    "total_cases": job.total_cases,
                    "passed": report.passed,
                    "failed": report.failed,
                    "skipped": report.skipped,
                    "duration": job.duration,
                    "env_config": job.env_config,
                },
                results=report_results,
            )
            report_path = await self._save_report(job, report_content)
            job.report_path = str(report_path)

            await self.db.commit()
            logger.info(f"pytest 执行任务 {job.id} 完成: {report.passed}/{report.total} 通过")

            # 6. 发送通知
            try:
                notifier = DingtalkNotifier(self.db)
                await notifier.notify_execution_done(
                    job.name, job.id, job.total_cases, report.passed, report.failed, job.duration
                )
            except Exception as notify_err:
                logger.warning(f"执行完成通知发送失败: {notify_err}")

        except Exception as e:
            logger.exception(f"pytest 执行任务 {job.id} 异常: {e}")
            job.status = "failed"
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            job.duration = round(time.monotonic() - start_time, 2)
            await self.db.commit()

            try:
                notifier = DingtalkNotifier(self.db)
                await notifier.notify_execution_failed(job.name, job.id, str(e))
            except Exception as notify_err:
                logger.warning(f"执行失败通知发送失败: {notify_err}")

    async def _collect_pytest_script(self, job: ExecutionJob) -> str | None:
        """收集执行任务关联的 pytest 脚本内容"""
        # 优先通过 generation_job_id 直接获取脚本
        if job.generation_job_id:
            gen_job = await self.db.get(GenerationJob, job.generation_job_id)
            if gen_job and gen_job.pytest_script_content:
                return gen_job.pytest_script_content

        # 兜底: 通过 ExecutionResult -> Testcase -> GenerationJob 查找脚本（兼容旧数据）
        stmt = (
            select(GenerationJob.pytest_script_content)
            .join(Testcase, Testcase.generation_job_id == GenerationJob.id)
            .join(ExecutionResult, ExecutionResult.testcase_id == Testcase.id)
            .where(ExecutionResult.execution_job_id == job.id)
            .where(GenerationJob.pytest_script_content.is_not(None))
            .limit(1)
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        return row

    async def _map_pytest_results(self, job: ExecutionJob, report):
        """将 pytest 结果映射回 ExecutionResult"""
        # 加载所有 execution_result，按 id 排序（即创建顺序 = testcase_ids 顺序）
        stmt = (
            select(ExecutionResult)
            .where(ExecutionResult.execution_job_id == job.id)
            .order_by(ExecutionResult.id)
        )
        result = await self.db.execute(stmt)
        exec_results = list(result.scalars().all())

        # 建立序号映射: pytest nodeid 中 test_case_001 -> 序号 0
        pytest_by_index = {}
        for tr in report.test_results:
            idx = self._extract_case_index(tr.nodeid)
            if idx is not None:
                pytest_by_index[idx] = tr

        # 按序号匹配
        for i, er in enumerate(exec_results):
            tr = pytest_by_index.get(i)
            if tr:
                # 映射状态: passed -> pass, failed -> fail
                status_map = {"passed": "pass", "failed": "fail", "skipped": "skip", "error": "error"}
                er.status = status_map.get(tr.outcome, tr.outcome)
                er.pytest_nodeid = tr.nodeid
                er.pytest_error_detail = tr.error_longrepr
                er.error_message = tr.error_message
                er.executed_at = datetime.utcnow()
            else:
                # 未匹配到的标记为 skip
                er.status = "skip"
                er.executed_at = datetime.utcnow()

        await self.db.commit()

    @staticmethod
    def _extract_case_index(nodeid: str) -> int | None:
        """从 pytest nodeid 提取用例序号（0-indexed）"""
        # e.g. "test_api.py::test_case_001_login_success" -> 0
        match = re.search(r"test_case_(\d+)", nodeid)
        if match:
            return int(match.group(1)) - 1  # 转为 0-indexed
        return None

    @staticmethod
    def _build_pytest_report_results(report) -> list[dict]:
        """将 PytestReport 转换为 ReportBuilder 需要的格式"""
        results = []
        for tr in report.test_results:
            status_map = {"passed": "pass", "failed": "fail", "skipped": "skip", "error": "error"}
            results.append({
                "testcase_title": tr.nodeid.split("::")[-1] if "::" in tr.nodeid else tr.nodeid,
                "status": status_map.get(tr.outcome, tr.outcome),
                "request_info": {"pytest_nodeid": tr.nodeid},
                "response_info": {"duration_ms": tr.duration_ms},
                "assertion_results": [],
                "error_message": tr.error_message,
            })
        return results

    # ──────── httpx 模式 (现有逻辑) ────────

    async def _run_with_httpx(self, job: ExecutionJob):
        """使用内置 httpx 引擎执行（原有逻辑）"""
        job.status = "running"
        job.started_at = datetime.utcnow()
        await self.db.commit()

        start_time = time.monotonic()

        try:
            # 加载待执行的结果记录
            stmt = select(ExecutionResult).where(ExecutionResult.execution_job_id == job.id)
            result = await self.db.execute(stmt)
            exec_results = result.scalars().all()

            # 初始化变量解析器
            resolver = VariableResolver(job.env_config or {})
            runner = HttpRunner(
                timeout=job.env_config.get("timeout", 30.0) if job.env_config else 30.0,
            )
            assertion_engine = AssertionEngine()

            # 执行所有用例
            passed = 0
            failed = 0
            skipped = 0
            report_results = []

            for exec_result in exec_results:
                async with self.semaphore:
                    tc = await self.db.get(Testcase, exec_result.testcase_id)
                    if not tc or tc.case_type != "api":
                        exec_result.status = "skip"
                        skipped += 1
                        continue

                    result_data = await self._execute_single(
                        tc, exec_result, resolver, runner, assertion_engine
                    )
                    report_results.append(result_data)

                    if exec_result.status == "pass":
                        passed += 1
                    elif exec_result.status == "fail":
                        failed += 1
                    else:
                        skipped += 1

            # 更新任务统计
            job.passed = passed
            job.failed = failed
            job.skipped = skipped
            job.duration = round(time.monotonic() - start_time, 2)
            job.finished_at = datetime.utcnow()

            if failed == 0:
                job.status = "success"
            elif passed > 0:
                job.status = "partial_fail"
            else:
                job.status = "failed"

            # 生成报告
            report = ReportBuilder()
            report_content = report.build(
                job_data={
                    "name": job.name,
                    "total_cases": job.total_cases,
                    "passed": passed,
                    "failed": failed,
                    "skipped": skipped,
                    "duration": job.duration,
                    "env_config": job.env_config,
                },
                results=report_results,
            )
            report_path = await self._save_report(job, report_content)
            job.report_path = str(report_path)

            await self.db.commit()
            logger.info(f"执行任务 {job.id} 完成: {passed}/{job.total_cases} 通过")

            # 发送执行完成通知
            try:
                notifier = DingtalkNotifier(self.db)
                await notifier.notify_execution_done(
                    job.name, job.id, job.total_cases, passed, failed, job.duration
                )
            except Exception as notify_err:
                logger.warning(f"执行完成通知发送失败: {notify_err}")

        except Exception as e:
            logger.exception(f"执行任务 {job.id} 异常: {e}")
            job.status = "failed"
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            job.duration = round(time.monotonic() - start_time, 2)
            await self.db.commit()

            # 发送执行失败通知
            try:
                notifier = DingtalkNotifier(self.db)
                await notifier.notify_execution_failed(job.name, job.id, str(e))
            except Exception as notify_err:
                logger.warning(f"执行失败通知发送失败: {notify_err}")

    async def _execute_single(
        self,
        tc: Testcase,
        exec_result: ExecutionResult,
        resolver: VariableResolver,
        runner: HttpRunner,
        assertion_engine: AssertionEngine,
    ) -> dict:
        """执行单个测试用例 (httpx 模式)"""
        report_data = {"testcase_title": tc.title, "status": "error"}

        try:
            # 构造请求
            base_url = resolver.resolve("{{BASE_URL}}")
            method = tc.api_method or "GET"
            path = resolver.resolve(tc.api_path or "")
            url = f"{base_url}{path}" if not path.startswith("http") else path

            headers = resolver.resolve_dict(tc.api_headers) or {}
            body = resolver.resolve_dict(tc.api_request_body)

            request_info = {
                "method": method,
                "url": url,
                "headers": headers,
                "body": body,
            }
            exec_result.request_info = request_info

            # 执行请求
            response, retry_count = await runner.execute(
                method=method, url=url, headers=headers, body=body
            )
            exec_result.retry_count = retry_count

            response_info = {
                "status_code": response.status_code,
                "headers": dict(response.headers) if response.headers else {},
                "body": response.body,
                "latency_ms": response.latency_ms,
            }
            exec_result.response_info = response_info

            # 执行断言
            assertions = tc.api_assertions or []
            if assertions:
                assertion_results = assertion_engine.evaluate(assertions, response_info)
                exec_result.assertion_results = [asdict(a) for a in assertion_results]

                all_passed = all(a.passed for a in assertion_results)
                exec_result.status = "pass" if all_passed else "fail"
            else:
                # 无断言规则，仅检查状态码
                exec_result.status = "pass" if response.status_code < 400 else "fail"
                exec_result.assertion_results = []

            exec_result.executed_at = datetime.utcnow()

            report_data.update({
                "status": exec_result.status,
                "request_info": request_info,
                "response_info": response_info,
                "assertion_results": exec_result.assertion_results,
            })

        except Exception as e:
            logger.error(f"用例 {tc.title} 执行异常: {e}")
            exec_result.status = "error"
            exec_result.error_message = str(e)
            exec_result.executed_at = datetime.utcnow()
            report_data["error_message"] = str(e)

        await self.db.commit()
        return report_data

    async def _save_report(self, job: ExecutionJob, content: str) -> Path:
        """保存执行报告"""
        settings.reports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"execution_{job.id}_{timestamp}.html"
        file_path = settings.reports_dir / filename
        file_path.write_text(content, encoding="utf-8")
        return file_path
