"""接口测试用例生成 Pipeline"""

import json
import logging
import re
from pathlib import Path

from jinja2 import Template

from backend.app.core.pipeline.base_pipeline import BasePipeline
from backend.app.core.ai.chat_client import ChatClient
from backend.app.models.generation_job import GenerationJob
from backend.app.models.testcase import Testcase
from backend.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一位拥有10年经验的资深QA工程师，精通接口测试、HTTP协议和REST API规范。"
    "你的任务是根据需求文档和接口文档，生成高质量的接口测试用例。"
    "输出必须严格遵守指定的三段式格式：Markdown用例、pytest脚本、结构化JSON。"
    "每个接口必须覆盖：正常场景、参数缺失、格式错误、鉴权校验。"
)


class ApiPipeline(BasePipeline):
    """接口测试用例生成"""

    async def _generate(self, job: GenerationJob) -> str:
        # Step 1: 加载上下文
        await self._update_progress(job, 10, "加载需求文档和规范...")
        spec_content = await self._load_spec_content(job)
        requirement_content = await self._load_requirement_content(job)

        # Step 2: 获取 YApi 接口文档（失败则直接中断任务）
        api_doc_content = ""
        if job.yapi_project_id:
            await self._update_progress(job, 15, "获取 YApi 接口文档...")
            api_doc_content = await self._fetch_yapi_docs(
                job.yapi_project_id, job.yapi_interface_paths, job.yapi_token
            )
            job.yapi_doc_content = api_doc_content
            await self.db.commit()

        await self._update_progress(job, 20, "构建 Prompt...")

        # Step 3: 渲染 Prompt
        prompt_path = settings.prompts_dir / "api_testcase.j2"
        template = Template(prompt_path.read_text(encoding="utf-8"))
        prompt = template.render(
            spec_content=spec_content,
            requirement_content=requirement_content,
            api_doc_content=api_doc_content,
            target_module="",
            expected_count="",
        )
        job.prompt_snapshot = prompt
        await self.db.commit()

        # Step 4: 调用 AI 模型生成
        await self._update_progress(job, 25, "调用 AI 模型生成接口用例...")
        model_alias = job.ai_model or "code-pro"
        client = ChatClient()

        full_content = ""
        token_count = 0
        async for token in client.stream_generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            model_alias=model_alias,
        ):
            full_content += token
            token_count += 1
            if token_count % 100 == 0:
                progress = min(25 + int(token_count / 50), 90)
                await self._update_progress(job, progress, f"已生成 {token_count} tokens...")

        job.raw_output = full_content
        await self._update_progress(job, 90, "解析生成结果...")

        # Step 5: 解析 AI 三段输出
        parsed = self._parse_ai_output(full_content)

        # Step 5.1: 解析 Markdown 用例并保存到 DB (现有逻辑)
        md_content = parsed["markdown"]
        testcases = self._parse_api_testcases(md_content, job)
        for tc in testcases:
            self.db.add(tc)

        # Step 5.2: 保存 pytest 脚本
        if parsed["pytest_script"]:
            script = self._fix_truncated_script(parsed["pytest_script"])
            script_path = await self._save_pytest_script(job, script)
            job.pytest_script_content = script
            job.pytest_script_path = str(script_path)
            logger.info(f"Job {job.id}: 保存 pytest 脚本到 {script_path}")

        # Step 5.3: 保存结构化 JSON (A方案预留)
        if parsed["structured_json"]:
            job.structured_json = parsed["structured_json"]
            logger.info(f"Job {job.id}: 保存结构化 JSON ({len(parsed['structured_json'].get('testcases', []))} 条)")

        await self.db.commit()
        await self._update_progress(job, 95, f"成功解析 {len(testcases)} 条接口用例")

        return md_content or full_content

    # ──────── AI 输出解析 ────────

    def _parse_ai_output(self, raw: str) -> dict:
        """解析 AI 输出的三段内容：Markdown、pytest 脚本、结构化 JSON"""
        result = {
            "markdown": "",
            "pytest_script": "",
            "structured_json": None,
        }

        # 1. 提取 Markdown 测试用例
        md_match = re.search(
            r"===TESTCASE_MD_START===\s*\n([\s\S]*?)\n\s*===TESTCASE_MD_END===",
            raw,
        )
        if md_match:
            result["markdown"] = md_match.group(1).strip()
        else:
            # 容错：如果没有标记，尝试提取 ## 测试用例 开头的内容
            blocks = re.findall(r"(## 测试用例[\s\S]*?)(?=## 测试用例|\Z)", raw)
            if blocks:
                result["markdown"] = "\n\n".join(b.strip() for b in blocks)
                logger.warning("未找到 TESTCASE_MD 标记，使用容错模式提取 Markdown")

        # 2. 提取 pytest 脚本
        pytest_match = re.search(
            r"===PYTEST_SCRIPT_START===\s*\n([\s\S]*?)\n\s*===PYTEST_SCRIPT_END===",
            raw,
        )
        if pytest_match:
            script = pytest_match.group(1).strip()
            # 去除外层 ```python ... ``` 包裹
            script = re.sub(r"^```python\s*\n", "", script)
            script = re.sub(r"\n```\s*$", "", script)
            result["pytest_script"] = script.strip()
        else:
            # 容错1：只有 START 没有 END（AI 输出被截断）
            start_match = re.search(r"===PYTEST_SCRIPT_START===\s*\n([\s\S]+)", raw)
            if start_match:
                script = start_match.group(1).strip()
                script = re.sub(r"^```python\s*\n", "", script)
                script = re.sub(r"\n```\s*$", "", script)
                # 去掉末尾可能残留的其他段落标记
                script = re.split(r"\n===STRUCTURED_JSON_START===", script)[0].strip()
                if "def test_" in script:
                    result["pytest_script"] = script
                    logger.warning("PYTEST_SCRIPT_END 标记缺失（输出可能被截断），使用容错提取")
            else:
                # 容错2：从全文中找最大的 python 代码块
                code_blocks = re.findall(r"```python\s*\n([\s\S]*?)\n```", raw)
                if code_blocks:
                    # 选最长的（通常是完整脚本）
                    longest = max(code_blocks, key=len)
                    if "def test_" in longest:
                        result["pytest_script"] = longest.strip()
                        logger.warning("未找到 PYTEST_SCRIPT 标记，使用容错模式提取脚本")

        # 3. 提取结构化 JSON
        json_match = re.search(
            r"===STRUCTURED_JSON_START===\s*\n([\s\S]*?)\n\s*===STRUCTURED_JSON_END===",
            raw,
        )
        if json_match:
            json_text = json_match.group(1).strip()
            # 去除外层 ```json ... ``` 包裹
            json_text = re.sub(r"^```json\s*\n", "", json_text)
            json_text = re.sub(r"\n```\s*$", "", json_text)
            try:
                result["structured_json"] = json.loads(json_text.strip())
            except json.JSONDecodeError as e:
                logger.warning(f"结构化 JSON 解析失败: {e}")

        return result

    # ──────── 脚本修复 ────────

    def _fix_truncated_script(self, script: str) -> str:
        """修复被截断的 pytest 脚本，确保语法正确"""
        import ast
        try:
            ast.parse(script)
            return script
        except SyntaxError:
            pass

        # 截断通常发生在最后一个函数中，删除不完整的最后一个函数
        lines = script.split("\n")
        # 从后往前找到最后一个 def test_ 的起始行
        last_def_idx = -1
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].startswith("def test_"):
                last_def_idx = i
                break

        if last_def_idx > 0:
            trimmed = "\n".join(lines[:last_def_idx]).rstrip()
            try:
                ast.parse(trimmed)
                logger.warning(f"pytest 脚本末尾被截断，已移除不完整的最后一个测试函数（第{last_def_idx+1}行起）")
                return trimmed
            except SyntaxError:
                pass

        logger.warning("pytest 脚本存在语法错误，无法自动修复")
        return script

    # ──────── 脚本保存 ────────

    async def _save_pytest_script(self, job: GenerationJob, script_content: str) -> Path:
        """保存 pytest 脚本到文件系统"""
        dir_path = settings.pytest_scripts_dir / f"gen_{job.id}"
        dir_path.mkdir(parents=True, exist_ok=True)
        script_path = dir_path / "test_generated.py"
        script_path.write_text(script_content, encoding="utf-8")
        return script_path

    # ──────── YApi 集成 ────────

    async def _fetch_yapi_docs(self, project_id: str, interface_paths: list[str] | None = None, token: str | None = None) -> str:
        """从 YApi 获取接口文档并格式化

        Args:
            project_id: YApi 项目 ID
            interface_paths: 指定要获取的接口路径列表，为空则获取全部
            token: 项目级别的 YApi Token，为空则使用全局配置
        """
        from mcp_servers.yapi_mcp.client import YApiClient
        from backend.config import settings

        client = YApiClient(base_url=settings.yapi_base_url, token=token or settings.yapi_token)

        md_parts = [f"# 接口文档 (项目ID: {project_id})\n"]

        if interface_paths:
            # 定向获取：只获取指定路径的接口
            matched = await client.find_interfaces_by_paths(int(project_id), interface_paths)
            for detail in matched:
                md_parts.append(client.format_interface_as_markdown(detail))
            logger.info(f"YApi 定向获取: {len(matched)}/{len(interface_paths)} 个接口匹配")
        else:
            # 全量获取：保持原有逻辑
            result = await client.list_interfaces(int(project_id))
            interfaces = result.get("list", [])
            for item in interfaces:
                detail = await client.get_interface_detail(item["_id"])
                md_parts.append(client.format_interface_as_markdown(detail))

        return "\n".join(md_parts)

    # ──────── Markdown 用例解析 (现有逻辑) ────────

    def _parse_api_testcases(self, md_content: str, job: GenerationJob) -> list[Testcase]:
        """解析 AI 输出的接口测试用例"""
        testcases = []
        blocks = re.split(r"(?=^## 测试用例)", md_content, flags=re.MULTILINE)

        for block in blocks:
            block = block.strip()
            if not block.startswith("## 测试用例"):
                continue

            tc = Testcase(
                case_type="api",
                generation_job_id=job.id,
                requirement_id=job.requirement_id,
                content_md=block,
                status="draft",
            )

            # 基础字段
            title_match = re.search(r"\*\*标题\*\*:\s*(.+)", block)
            tc.title = title_match.group(1).strip() if title_match else "未命名接口用例"

            priority_match = re.search(r"\*\*优先级\*\*:\s*(P[0-3])", block)
            tc.priority = priority_match.group(1) if priority_match else "P2"

            module_match = re.search(r"\*\*模块\*\*:\s*(.+)", block)
            tc.module = module_match.group(1).strip() if module_match else None

            # 接口路径
            path_match = re.search(r"\*\*接口路径\*\*:\s*(GET|POST|PUT|DELETE|PATCH)\s+(.+)", block)
            if path_match:
                tc.api_method = path_match.group(1).strip()
                tc.api_path = path_match.group(2).strip()

            # 请求头
            tc.api_headers = self._parse_headers_table(block)

            # 请求体
            body_match = re.search(r"```json\s*\n([\s\S]*?)\n```", block)
            if body_match:
                try:
                    tc.api_request_body = json.loads(body_match.group(1))
                except json.JSONDecodeError:
                    tc.api_request_body = {"_raw": body_match.group(1)}

            # 断言规则
            tc.api_assertions = self._parse_assertions_table(block)

            testcases.append(tc)

        return testcases

    def _parse_headers_table(self, block: str) -> dict | None:
        """解析 Headers 表格"""
        match = re.search(
            r"\*\*Headers\*\*:\n\|.*\n\|[-| ]+\n((?:\|.*\n)*)", block
        )
        if not match:
            return None
        headers = {}
        for line in match.group(1).strip().split("\n"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) >= 2:
                headers[cells[0]] = cells[1]
        return headers or None

    def _parse_assertions_table(self, block: str) -> list[dict] | None:
        """解析断言规则表格"""
        match = re.search(
            r"### 断言规则\n\|.*\n\|[-| ]+\n((?:\|.*\n)*)", block
        )
        if not match:
            return None
        assertions = []
        for line in match.group(1).strip().split("\n"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) >= 4:
                assertions.append({
                    "type": cells[0],
                    "path": cells[1] if cells[1] != "-" else None,
                    "expected": cells[2],
                    "operator": cells[3],
                })
        return assertions or None
