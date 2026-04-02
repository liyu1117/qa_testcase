"""钉钉文档 MCP 读取器 - 通过 MCP 协议读取钉钉在线文档内容"""

import json
import logging
import re

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)


class DingtalkMCPReader:
    """通过钉钉 MCP 服务读取文档内容"""

    def __init__(self, mcp_url: str | None = None):
        self.mcp_url = mcp_url or settings.dingtalk_mcp_url

    async def read_document(self, doc_url_or_id: str) -> str:
        """读取钉钉文档，返回 Markdown 格式文本

        使用 get_document_content 工具直接获取完整 Markdown 内容，
        包含表格数据、列表、标题等全部结构化信息。

        Args:
            doc_url_or_id: 钉钉文档链接或 dentryUuid
        Returns:
            文档的 Markdown 格式内容
        """
        if not self.mcp_url:
            raise ValueError("未配置钉钉 MCP URL (DINGTALK_MCP_URL)")

        # 1. 初始化 MCP 会话
        await self._initialize()

        # 2. 调用 get_document_content 获取完整 Markdown
        markdown = await self._get_document_content(doc_url_or_id)

        # 3. 清理 Markdown（去除图片链接等无用内容，保留文本）
        cleaned = self._clean_markdown(markdown)
        return cleaned

    async def upload_file(self, filename: str, content: bytes) -> str:
        """上传文件到钉钉文档（返回文档链接）"""
        await self._initialize()

        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "create_document",
                "arguments": {
                    "name": filename,
                    "content": content.decode("utf-8", errors="ignore"),
                },
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                self.mcp_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

        if "error" in data:
            raise Exception(f"上传钉钉失败: {data['error']}")

        result = data.get("result", {})
        doc_url = result.get("docUrl", "")

        return doc_url

    async def _initialize(self):
        """MCP 协议初始化握手"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "qa-master", "version": "1.0.0"},
            },
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self.mcp_url,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise Exception(f"MCP 初始化失败: {data['error']}")
            logger.info("钉钉 MCP 初始化成功")

    async def _get_document_content(self, node_id: str) -> str:
        """调用 get_document_content 工具获取文档的完整 Markdown 内容"""
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "get_document_content",
                "arguments": {"nodeId": node_id},
            },
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                self.mcp_url,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

        if "error" in data:
            raise Exception(f"MCP 调用失败: {data['error']}")

        result = data.get("result", {})
        content_list = result.get("content", [])
        if not content_list:
            raise Exception("MCP 返回内容为空")

        text = content_list[0].get("text", "")

        # 尝试解析为 JSON（get_document_content 返回 JSON 包含 markdown 字段）
        try:
            parsed = json.loads(text)
            if parsed.get("success"):
                markdown = parsed.get("markdown", "")
                title = parsed.get("title", "")
                if title and markdown:
                    markdown = f"# {title}\n\n{markdown}"
                logger.info(f"从钉钉文档获取 Markdown 成功: {len(markdown)} 字符")
                return markdown
            else:
                raise Exception(f"get_document_content 返回失败: {text[:200]}")
        except json.JSONDecodeError:
            # 非 JSON，直接作为文本返回
            return text

    @staticmethod
    def _clean_markdown(md: str) -> str:
        """清理 Markdown 内容：去除图片链接，简化 HTML 标签，保留核心文本

        重要：HTML标签正则必须使用 </?[a-zA-Z!] 前缀限定，
        避免把 SQL 中的 <= / <> 运算符误判为HTML标签开头，
        导致贪婪匹配吞掉后续大段正文内容。
        """
        # 将 ![alt](url) 图片标记替换为 [图片] 占位符
        md = re.sub(r"!\[.*?\]\(.*?\)", "[图片]", md)

        # 简化 HTML 列表标签为 Markdown 格式
        md = re.sub(r"<ul>", "", md)
        md = re.sub(r"</ul>", "", md)
        md = re.sub(r"<li.*?>", "- ", md)
        md = re.sub(r"</li>", "", md)
        md = re.sub(r"<br\s*/?>", "\n", md)

        # 去除其他 HTML style 属性
        md = re.sub(r'\s*style="[^"]*"', "", md)

        # 去除剩余的 HTML 标签（仅匹配合法的HTML标签，以字母或/开头）
        # 旧写法 <[^>]+> 会把 SQL 中的 <= 28 等误判为标签开头，
        # 贪婪匹配到下一个 > 字符，吞掉数千字符的正文内容
        md = re.sub(r"</?[a-zA-Z!][^>]*>", "", md)

        # 合并多个连续空行为最多两个
        md = re.sub(r"\n{4,}", "\n\n\n", md)

        return md.strip()
