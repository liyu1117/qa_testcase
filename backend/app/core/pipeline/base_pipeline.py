"""用例生成 Pipeline 基类 - 进度管理/状态流转/结果存储"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.generation_job import GenerationJob
from backend.app.models.requirement import Requirement
from backend.app.core.notifier.dingtalk import DingtalkNotifier
from backend.config import settings

logger = logging.getLogger(__name__)


class BasePipeline(ABC):
    """测试用例生成 Pipeline 抽象基类"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(self, job_id: int):
        """执行 pipeline 主流程"""
        job = await self.db.get(GenerationJob, job_id)
        if not job:
            logger.error(f"生成任务 {job_id} 不存在")
            return

        try:
            job.status = "running"
            job.started_at = datetime.utcnow()
            await self._update_progress(job, 5, "启动 Pipeline...")

            # 更新需求状态为"生成中"
            if job.requirement_id:
                req = await self.db.get(Requirement, job.requirement_id)
                if req:
                    req.status = "in_generation"
                    await self.db.commit()

            # 子类实现具体生成逻辑
            md_content = await self._generate(job)

            # 保存结果文件
            file_path = await self._save_result(job, md_content)
            job.result_file_path = str(file_path)
            job.status = "success"
            job.finished_at = datetime.utcnow()
            await self._update_progress(job, 100, "生成完成")

            # 更新需求状态为"已完成"
            if job.requirement_id:
                req = await self.db.get(Requirement, job.requirement_id)
                if req:
                    req.status = "done"
                    await self.db.commit()

            logger.info(f"生成任务 {job_id} 成功完成, 文件: {file_path}")

            # 发送生成完成通知
            try:
                from sqlalchemy import select, func
                from backend.app.models.testcase import Testcase
                count_stmt = select(func.count(Testcase.id)).where(Testcase.generation_job_id == job.id)
                case_count = (await self.db.execute(count_stmt)).scalar() or 0
                duration = (job.finished_at - job.started_at).total_seconds() if job.started_at and job.finished_at else 0
                notifier = DingtalkNotifier(self.db)
                await notifier.notify_generation_done(job.name, job.id, case_count, duration, job.job_type)
            except Exception as notify_err:
                logger.warning(f"生成完成通知发送失败: {notify_err}")

        except Exception as e:
            logger.exception(f"生成任务 {job_id} 失败: {e}")
            job.status = "failed"
            job.error_message = str(e)[:2000]
            job.finished_at = datetime.utcnow()
            await self.db.commit()

            # 发送生成失败通知
            try:
                notifier = DingtalkNotifier(self.db)
                await notifier.notify_generation_failed(job.name, job.id, str(e), job.job_type)
            except Exception as notify_err:
                logger.warning(f"生成失败通知发送失败: {notify_err}")

    @abstractmethod
    async def _generate(self, job: GenerationJob) -> str:
        """子类实现：具体生成逻辑，返回 Markdown 内容"""
        ...

    async def _update_progress(self, job: GenerationJob, progress: int, message: str = ""):
        """更新任务进度"""
        job.progress = progress
        await self.db.commit()
        logger.info(f"任务 {job.id} 进度: {progress}% - {message}")

    async def _save_result(self, job: GenerationJob, md_content: str) -> Path:
        """保存生成的 MD 文件"""
        settings.exports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{job.job_type}_{job.id}_{timestamp}.md"
        file_path = settings.exports_dir / filename

        file_path.write_text(md_content, encoding="utf-8")
        return file_path

    async def _load_spec_content(self, job: GenerationJob) -> str:
        """加载测试用例规范"""
        if job.spec_id:
            from backend.app.models.testcase_spec import TestcaseSpec
            spec = await self.db.get(TestcaseSpec, job.spec_id)
            if spec:
                return spec.content

        # fallback: 读取本地规范文件
        spec_files = {
            "functional": "testcase_specs/functional_spec.md",
            "ui": "testcase_specs/ui_spec.md",
            "api": "testcase_specs/api_spec.md",
        }
        spec_file = Path(spec_files.get(job.job_type, ""))
        if spec_file.exists():
            return spec_file.read_text(encoding="utf-8")
        return ""

    async def _load_requirement_content(self, job: GenerationJob) -> str:
        """加载需求文档内容，优先从钉钉文档链接读取"""
        from backend.app.models.requirement import Requirement
        req = await self.db.get(Requirement, job.requirement_id)
        if not req:
            return ""

        # 尝试从钉钉文档链接获取最新内容（每次重新拉取以确保表格等数据完整）
        if req.source_url and "dingtalk.com" in req.source_url:
            try:
                from backend.app.core.doc_reader.dingtalk_mcp_reader import DingtalkMCPReader
                reader = DingtalkMCPReader()
                content = await reader.read_document(req.source_url)
                if content:
                    # 缓存到数据库
                    req.raw_content = content
                    req.source_type = "dingtalk_doc"
                    await self.db.commit()
                    logger.info(f"从钉钉文档获取需求内容成功: {len(content)} 字符")
                    return content
            except Exception as e:
                logger.warning(f"从钉钉文档获取内容失败: {e}")

        # 使用已缓存的 raw_content
        if req.raw_content:
            return req.raw_content

        return f"# {req.title}\n\n{req.description or ''}"
