"""UI 测试用例生成 Pipeline"""

import logging

from jinja2 import Template

from backend.app.core.pipeline.base_pipeline import BasePipeline
from backend.app.core.pipeline.functional_pipeline import FunctionalPipeline
from backend.app.core.ai.chat_client import ChatClient
from backend.app.core.ai.multimodal_client import MultimodalClient
from backend.app.models.generation_job import GenerationJob
from backend.app.models.testcase import Testcase
from backend.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一位拥有10年经验的资深QA工程师，擅长UI视觉还原测试和交互测试。"
    "你的任务是根据需求文档和UI设计稿信息，生成高质量的UI测试用例。"
    "输出必须严格遵守指定的Markdown模板格式。"
)


class UIPipeline(BasePipeline):
    """UI 测试用例生成"""

    async def _generate(self, job: GenerationJob) -> str:
        # Step 1: 加载需求和规范
        await self._update_progress(job, 10, "加载需求文档和规范...")
        spec_content = await self._load_spec_content(job)
        requirement_content = await self._load_requirement_content(job)

        # Step 2: 获取 Figma 设计稿信息
        design_description = ""
        design_images = ""
        if job.figma_url:
            await self._update_progress(job, 15, "获取 Figma 设计稿...")
            try:
                design_description, design_images = await self._fetch_figma_info(job.figma_url)
            except Exception as e:
                logger.warning(f"获取 Figma 信息失败: {e}, 将仅基于需求文档生成")
                design_description = f"[Figma 获取失败: {e}]"

        await self._update_progress(job, 25, "分析设计稿...")

        # 保存需求内容和 Figma 信息到 job，供详情页展示
        display_parts = []
        if requirement_content:
            display_parts.append(requirement_content)
        if design_description:
            display_parts.append(f"---\n\n## Figma 设计稿读取信息\n\n{design_description}")
        job.requirement_content = "\n\n".join(display_parts) if display_parts else None
        await self.db.commit()

        # Step 3: 如果有设计稿截图，用多模态模型分析
        if design_images:
            await self._update_progress(job, 30, "多模态模型分析设计稿...")
            try:
                mm_client = MultimodalClient()
                analysis = await mm_client.analyze_with_image(
                    prompt="请详细描述这个UI设计稿的页面结构、组件布局、交互元素和视觉风格。列出所有可见的组件及其属性。",
                    image_url=design_images,
                    model_alias="vision-pro",
                )
                design_description += f"\n\n### 多模态分析结果\n{analysis}"
            except Exception as e:
                logger.warning(f"多模态分析失败: {e}")

        # 更新 Figma 信息（含多模态分析结果）
        if design_description:
            display_parts = [requirement_content] if requirement_content else []
            display_parts.append(f"---\n\n## Figma 设计稿读取信息\n\n{design_description}")
            job.requirement_content = "\n\n".join(display_parts)
            await self.db.commit()

        # Step 4: 渲染 Prompt
        await self._update_progress(job, 35, "构建 Prompt...")
        prompt_path = settings.prompts_dir / "ui_testcase.j2"
        template = Template(prompt_path.read_text(encoding="utf-8"))
        prompt = template.render(
            spec_content=spec_content,
            requirement_content=requirement_content,
            design_description=design_description,
            design_images="",
            target_module="",
            expected_count="",
        )
        job.prompt_snapshot = prompt
        await self.db.commit()

        # Step 5: 调用 AI 模型生成
        await self._update_progress(job, 40, "调用 AI 模型生成 UI 用例...")
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
                progress = min(40 + int(token_count / 50), 90)
                await self._update_progress(job, progress, f"已生成 {token_count} tokens...")

        job.raw_output = full_content
        await self._update_progress(job, 90, "解析生成结果...")

        # Step 6: 复用 functional pipeline 的解析逻辑，但设为 ui 类型
        import re
        testcases = self._parse_ui_testcases(full_content, job)
        for tc in testcases:
            self.db.add(tc)
        await self.db.commit()
        await self._update_progress(job, 95, f"成功解析 {len(testcases)} 条 UI 用例")

        return full_content

    async def _fetch_figma_info(self, figma_url: str) -> tuple[str, str]:
        """从 Figma URL 提取设计信息，支持 node-id 精准定位"""
        from mcp_servers.figma_mcp.client import FigmaClient
        from backend.config import settings

        import re
        match = re.search(r"figma\.com/(?:file|design)/([^/]+)", figma_url)
        if not match:
            return "无法解析 Figma URL", ""

        file_key = match.group(1)

        if not settings.figma_access_token:
            return "[Figma 获取失败: 未配置 FIGMA_ACCESS_TOKEN]", ""

        client = FigmaClient(access_token=settings.figma_access_token)

        # 解析 URL 中的 node-id 参数（如 node-id=35-10366）
        node_match = re.search(r"node-id=([^&]+)", figma_url)
        target_node_id = node_match.group(1).replace("-", ":") if node_match else None

        description_parts = []
        first_screenshot = ""

        if target_node_id:
            # 精准模式：直接获取指定节点
            logger.info(f"Figma: 精准获取节点 {target_node_id}")
            node = await client.get_node(file_key, target_node_id)
            node_name = node.get("name", "未知节点")
            node_type = node.get("type", "UNKNOWN")
            description_parts.append(f"## 目标节点: {node_name} ({node_type})")

            # 收集子 Frame
            children = node.get("children", [])
            child_frames = [
                c for c in children
                if c.get("type") in ("FRAME", "COMPONENT", "INSTANCE", "GROUP", "SECTION")
            ]

            # 如果目标节点本身是 FRAME 且无子 Frame，把自身当作唯一 Frame
            frames_to_scan = child_frames if child_frames else ([{"id": target_node_id, "name": node_name, **node}] if node_type == "FRAME" else [])

            for frame in frames_to_scan[:8]:
                fid = frame.get("id", frame.get("id"))
                fname = frame.get("name", "")
                bbox = frame.get("absoluteBoundingBox", {})
                w, h = bbox.get("width", "?"), bbox.get("height", "?")
                description_parts.append(f"### Frame: {fname} ({w}x{h})")

                # 截图（仅第一个）
                if not first_screenshot:
                    try:
                        first_screenshot = await client.export_image(file_key, fid)
                    except Exception:
                        pass

                # 文本内容
                try:
                    texts = await client.get_text_content(file_key, fid)
                    if texts:
                        description_parts.append("文本内容:")
                        for t in texts[:15]:
                            description_parts.append(f'  - "{t["characters"]}"')
                except Exception:
                    pass
        else:
            # 通用模式：获取前3个页面
            logger.info("Figma: 通用模式，获取前3个页面")
            pages = await client.get_file_pages(file_key)
            for page in pages[:3]:
                frames = await client.get_page_frames(file_key, page["id"])
                description_parts.append(f"## 页面: {page['name']}")
                for frame in frames[:5]:
                    description_parts.append(
                        f"- Frame: {frame['name']} ({frame.get('width', '?')}x{frame.get('height', '?')})"
                    )
                    if not first_screenshot:
                        try:
                            first_screenshot = await client.export_image(file_key, frame["id"])
                        except Exception:
                            pass
                    try:
                        texts = await client.get_text_content(file_key, frame["id"])
                        for t in texts[:10]:
                            description_parts.append(f'  - 文本: "{t["characters"]}"')
                    except Exception:
                        pass

        return "\n".join(description_parts), first_screenshot

    def _parse_ui_testcases(self, md_content: str, job: GenerationJob) -> list[Testcase]:
        """解析 UI 测试用例 - 兼容多种 AI 输出格式"""
        import re
        testcases = []

        # 兼容两种格式:
        #   格式A: ## 测试用例 UI-LOGIN-001 ...  (旧模板)
        #   格式B: ## UI-VSG-001 ...             (AI 实际输出)
        blocks = re.split(r"(?=^## (?:测试用例\s+)?UI-)", md_content, flags=re.MULTILINE)

        for block in blocks:
            block = block.strip()
            if not re.match(r"^## (?:测试用例\s+)?UI-", block):
                continue

            # 去除块尾的分割线
            block = re.sub(r"\n---\s*$", "", block).strip()

            tc = Testcase(
                case_type="ui",
                generation_job_id=job.id,
                requirement_id=job.requirement_id,
                content_md=block,
                status="draft",
            )

            # 标题: 优先取 **标题**: 字段，否则从 heading 提取
            title_match = re.search(r"\*\*标题\*\*:\s*(.+)", block)
            if title_match:
                tc.title = title_match.group(1).strip()
            else:
                heading_match = re.match(r"^## (?:测试用例\s+)?(UI-\S+)\s+(.+?)$", block, re.MULTILINE)
                if heading_match:
                    tc.title = f"{heading_match.group(1)} {heading_match.group(2)}".strip()
                else:
                    tc.title = "未命名UI用例"

            # 优先级
            priority_match = re.search(r"\*\*优先级\*\*:\s*(P[0-3])", block)
            tc.priority = priority_match.group(1) if priority_match else "P2"

            # 模块/页面
            module_match = re.search(r"\*\*(?:模块|所属页面(?:/模块)?|检查维度)\*\*:\s*(.+)", block)
            tc.module = module_match.group(1).strip() if module_match else None

            testcases.append(tc)

        return testcases
