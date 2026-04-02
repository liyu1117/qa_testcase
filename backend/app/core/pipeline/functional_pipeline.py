"""功能测试用例生成 Pipeline"""

import logging
import re

from jinja2 import Template

from backend.app.core.pipeline.base_pipeline import BasePipeline
from backend.app.core.ai.chat_client import ChatClient
from backend.app.models.generation_job import GenerationJob
from backend.app.models.testcase import Testcase
from backend.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一位拥有10年经验的资深QA工程师，精通测试用例设计方法论"
    "（等价类划分、边界值分析、判定表、错误推测法、场景法）。"
    "你的任务是根据提供的需求文档和规范，生成高质量的测试用例。"
    "输出必须严格遵守指定的Markdown模板格式，不得有任何偏差。"
)


class FunctionalPipeline(BasePipeline):
    """功能测试用例生成"""

    def _preprocess_requirement(self, content: str) -> str:
        """
        预处理需求文档，移除无效内容以提高AI理解效率
        
        清理内容包括：
        1. Markdown围栏代码块（```...```，保留代码前后业务描述）
        2. 图片占位符 [图片]
        3. 删除线内容 ~~已删除~~
        4. 空表格行
        5. 未确认问题（如「怎么AB？」）
        6. 无关章节（设计稿链接、数据埋点等）
        """
        # 1. 移除 Markdown 围栏代码块（通用方式，覆盖SQL/代码等所有情况）
        cleaned = re.sub(r'```[\s\S]*?```', '[已移除代码块]', content)
        
        # 2. 移除图片占位符并添加提醒
        cleaned = re.sub(r'\[图片\]', '', cleaned)
        
        # 3. 移除删除线内容
        cleaned = re.sub(r'~~[^~]+~~', '', cleaned)
        
        # 4. 移除空表格行（仅匹配只包含分隔符的行，如 |---|---|）
        cleaned = re.sub(r'^\|[\s\-|:]*\|$\n?', '', cleaned, flags=re.MULTILINE)
        
        # 5. 移除仅包含中文问号的疑问行（保护包含业务内容的行）
        cleaned = re.sub(r'^[^\n|#*\-]{0,10}？\s*$\n?', '', cleaned, flags=re.MULTILINE)
        
        # 6. 移除无关章节（设计稿链接、数据埋点等尾部模板段落）
        cleaned = re.sub(
            r'^#+ \*{0,2}·?\s*(设计稿链接|数据埋点)\*{0,2}[\s\S]*?(?=^#|\Z)',
            '', cleaned, flags=re.MULTILINE
        )
        
        # 7. 清理多余空白行（超过2个连续换行压缩为2个）
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        
        # 记录日志
        original_len = len(content)
        cleaned_len = len(cleaned)
        if cleaned_len < original_len * 0.8:
            logger.info(
                f"需求预处理完成：原文{original_len}字符 → 清理后{cleaned_len}字符 "
                f"(减少了{original_len - cleaned_len}字符)"
            )
        
        # 内容完整性校验：如果清理后内容过短，记录告警
        if cleaned_len < 500:
            logger.warning(
                f"⚠️ 预处理后内容仅{cleaned_len}字符，可能存在内容丢失！"
                f"请检查需求文档是否完整。"
            )
            
        return cleaned

    async def _generate(self, job: GenerationJob) -> str:
        # Step 1: 加载上下文
        await self._update_progress(job, 10, "加载需求文档和规范...")
        spec_content = await self._load_spec_content(job)
        requirement_content = await self._load_requirement_content(job)

        # Step 2: 需求预处理
        await self._update_progress(job, 15, "预处理需求文档...")
        requirement_content = self._preprocess_requirement(requirement_content)

        # Step 3: 渲染 Prompt
        await self._update_progress(job, 20, "构建 Prompt...")
        prompt_path = settings.prompts_dir / "functional_testcase.j2"
        template = Template(prompt_path.read_text(encoding="utf-8"))
        prompt = template.render(
            spec_content=spec_content,
            requirement_content=requirement_content,
            target_module="",
            expected_count="",
        )
        job.prompt_snapshot = prompt
        job.requirement_content = requirement_content
        await self.db.commit()

        # Step 4: 调用 AI 模型生成
        await self._update_progress(job, 25, "调用 AI 模型生成用例...")
        model_alias = job.ai_model or "chat-pro"
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
                progress = min(25 + int(token_count / 50), 85)
                await self._update_progress(job, progress, f"已生成 {token_count} tokens...")

        job.raw_output = full_content

        # Step 5: 覆盖率校验 — 检查测试点和用例的映射关系
        await self._update_progress(job, 86, "校验测试点覆盖率...")
        test_points = set(re.findall(r"TO-\d{3}", full_content))
        testcases_raw = self._parse_testcases(full_content, job)
        covered_points = set()
        for tc in testcases_raw:
            covered_points.update(re.findall(r"TO-\d{3}", tc.content_md or ""))

        uncovered = sorted(test_points - covered_points)
        coverage_rate = len(covered_points) / len(test_points) * 100 if test_points else 0
        logger.info(
            f"任务 {job.id}: 测试点={len(test_points)}, 用例={len(testcases_raw)}, "
            f"已覆盖={len(covered_points)}, 未覆盖={len(uncovered)}, 覆盖率={coverage_rate:.0f}%"
        )

        # Step 6: 如果覆盖率不足，触发补充生成（最多补充1次）
        if uncovered and len(testcases_raw) < len(test_points):
            await self._update_progress(
                job, 87,
                f"覆盖率 {coverage_rate:.0f}%，{len(uncovered)} 个测试点未覆盖，正在补充生成..."
            )
            supplement_prompt = self._build_supplement_prompt(full_content, uncovered)
            supplement_content = ""
            async for token in client.stream_generate(
                prompt=supplement_prompt,
                system_prompt=SYSTEM_PROMPT,
                model_alias=model_alias,
            ):
                supplement_content += token

            # 合并补充内容
            full_content = full_content + "\n\n---\n## 补充用例\n" + supplement_content
            job.raw_output = full_content

        await self._update_progress(job, 90, "解析生成结果...")

        # Step 7: 最终解析用例并写入数据库
        testcases = self._parse_testcases(full_content, job)

        if not testcases:
            logger.warning(f"任务 {job.id}: AI 未生成有效测试用例，raw_output 长度={len(full_content)}")
            raise ValueError(f"AI 未生成有效测试用例，请检查需求文档是否完整。AI 反馈:\n{full_content[:500]}")

        for tc in testcases:
            self.db.add(tc)
        await self.db.commit()

        # 输出最终覆盖率统计
        final_covered = set()
        for tc in testcases:
            final_covered.update(re.findall(r"TO-\d{3}", tc.content_md or ""))
        final_rate = len(final_covered) / len(test_points) * 100 if test_points else 0
        await self._update_progress(
            job, 95,
            f"成功解析 {len(testcases)} 条用例，覆盖 {len(final_covered)}/{len(test_points)} 个测试点（{final_rate:.0f}%）"
        )

        return full_content

    def _build_supplement_prompt(self, original_output: str, uncovered: list[str]) -> str:
        """构建补充生成的 Prompt"""
        uncovered_str = "、".join(uncovered)
        return f"""你之前已经生成了测试点清单和部分测试用例，但以下测试点没有对应的测试用例：

未覆盖的测试点：{uncovered_str}

请从你之前的输出中找到这些测试点的定义，为每个测试点生成对应的测试用例。

要求：
1. 为上述每个 TO-XXX 测试点各生成至少 1 条测试用例
2. 每条用例必须标注「关联测试点: TO-XXX」
3. 格式与之前的用例保持一致（使用 ### TC-XXX-NNN 标题格式）
4. 测试数据必须为具体值，预期结果必须可验证

你之前的完整输出如下：
---
{original_output}
---

请只输出补充的测试用例，不要重复已有的用例。"""

    def _parse_testcases(self, md_content: str, job: GenerationJob) -> list[Testcase]:
        """解析 AI 输出的 Markdown，提取测试用例。
        
        兼容多种 AI 输出格式：
        - ## TC-XXX-001 模块 - 标题
        - ### TC-XXX-001 标题（增强模式下的三级标题）
        - ## 测试用例 1: 标题
        - ```markdown 代码块包裹的用例
        """
        testcases = []

        # 先去除 ```markdown 代码块包裹
        cleaned = re.sub(r"```(?:markdown)?\s*\n", "", md_content)
        cleaned = re.sub(r"```\s*\n?", "", cleaned)

        # 按 ## 或 ### 标题分割（兼容二级和三级标题）
        blocks = re.split(r"(?=^#{2,3} )", cleaned, flags=re.MULTILINE)

        for block in blocks:
            block = block.strip()
            if not re.match(r"^#{2,3} ", block):
                continue

            # 提取标题行
            first_line = block.split("\n")[0]
            # 去掉 ## 或 ### 前缀，得到标题文本
            raw_title = re.sub(r"^#{2,3}\s+", "", first_line).strip()

            # 跳过非用例的标题（如 "第一部分：测试点清单" "第二部分：测试用例" 等）
            # 用例标题通常包含 TC- / FT- 编号，或包含 "测试" 关键词，或包含 " - " 分隔符
            has_tc_id = bool(re.match(r"(TC|FT)-", raw_title))
            has_separator = " - " in raw_title or ":" in raw_title or "：" in raw_title
            has_table = ("|" in block) and ("步骤" in block or "操作" in block)
            # 跳过测试点清单等非用例段落
            is_section_header = raw_title.startswith("第") and ("部分" in raw_title or "测试点清单" in raw_title)
            if is_section_header:
                continue
            if not (has_tc_id or has_separator or has_table):
                continue

            # 必须有表格结构才算用例
            if "|" not in block:
                continue

            tc = Testcase(
                case_type="functional",
                generation_job_id=job.id,
                requirement_id=job.requirement_id,
                content_md=block,
                status="draft",
            )

            # 提取标题：去掉 TC-XXX-NNN / FT-XXX-NNN 前缀
            title_cleaned = re.sub(r"^(TC|FT)-\S+\s*", "", raw_title).strip()
            tc.title = title_cleaned or raw_title

            # 提取优先级
            priority_match = re.search(r"\*\*优先级\*\*[：:]\s*(P[0-3])", block)
            tc.priority = priority_match.group(1) if priority_match else "P2"

            # 提取模块
            module_match = re.search(r"\*\*(?:所属模块|模块)\*\*[：:]\s*(.+)", block)
            tc.module = module_match.group(1).strip() if module_match else None

            # 提取前置条件
            pre_match = re.search(r"\*\*前置条件\*\*[：:]\s*(.+)", block)
            if not pre_match:
                pre_match = re.search(r"### 前置条件\n([\s\S]*?)(?=\n(?:##|###|\||-\s*\*\*)|\Z)", block)
            tc.precondition = pre_match.group(1).strip() if pre_match else None

            # 提取预期结果（最后的总结性预期结果）
            expect_match = re.search(r"\*\*预期结果\*\*[：:]\s*(.+)", block)
            if not expect_match:
                expect_match = re.search(r"### 预期(?:最终)?结果\n([\s\S]*?)(?=\n(?:##|###)|\Z)", block)
            tc.expected_result = expect_match.group(1).strip() if expect_match else None

            # 提取测试步骤表格
            steps = self._parse_steps_table(block)
            if steps:
                tc.steps = steps

            testcases.append(tc)

        logger.info(f"从 AI 输出中解析出 {len(testcases)} 条用例")
        return testcases

    def _parse_steps_table(self, block: str) -> list[dict] | None:
        """解析测试步骤表格，兼容多种列结构"""
        # 匹配表头+分隔线+数据行
        table_match = re.search(
            r"\|(.+)\|\s*\n\|[-| :]+\|\s*\n((?:\|.+\|\s*\n?)*)", block
        )
        if not table_match:
            return None

        # 解析表头确定列含义
        header_cells = [c.strip() for c in table_match.group(1).split("|")]
        data_lines = table_match.group(2).strip().split("\n")

        steps = []
        for i, line in enumerate(data_lines):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) < 2:
                continue

            step = {"step": str(i + 1)}
            for j, cell in enumerate(cells):
                if j < len(header_cells):
                    h = header_cells[j].lower()
                    if "步骤" in h or "序号" in h:
                        step["step"] = cell
                    elif "操作" in h or "动作" in h:
                        step["action"] = cell
                    elif "输入" in h or "数据" in h:
                        step["input"] = cell
                    elif "预期" in h or "结果" in h or "期望" in h:
                        step["expected"] = cell

            # 如果只有两列（操作 | 预期结果），也兼容
            if "action" not in step and len(cells) >= 2:
                step["action"] = cells[0] if len(header_cells) <= 2 else cells[1]
            if "expected" not in step and len(cells) >= 2:
                step["expected"] = cells[-1]

            steps.append(step)
        return steps or None
