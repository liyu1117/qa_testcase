"""钉钉 MCP 工具定义"""

from mcp_servers.dingtalk_mcp.client import DingtalkClient


class DingtalkTools:
    """钉钉 MCP 工具集"""

    def __init__(self, client: DingtalkClient):
        self.client = client

    def get_tool_definitions(self) -> list[dict]:
        """返回工具定义列表"""
        return [
            {
                "name": "get_document_content",
                "description": "获取钉钉文档的完整Markdown内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "doc_id": {"type": "string", "description": "钉钉文档ID"},
                        "doc_type": {"type": "string", "description": "文档类型", "default": "alidoc"},
                    },
                    "required": ["doc_id"],
                },
            },
            {
                "name": "list_space_documents",
                "description": "列出知识空间下的文档列表",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "space_id": {"type": "string", "description": "空间ID"},
                        "parent_id": {"type": "string", "description": "父节点ID", "default": "0"},
                    },
                    "required": ["space_id"],
                },
            },
            {
                "name": "search_documents",
                "description": "按关键词搜索钉钉文档",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keyword": {"type": "string", "description": "搜索关键词"},
                        "space_id": {"type": "string", "description": "限定空间ID（可选）"},
                    },
                    "required": ["keyword"],
                },
            },
            {
                "name": "send_markdown_message",
                "description": "向钉钉群发送Markdown格式消息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "消息标题"},
                        "content": {"type": "string", "description": "Markdown内容"},
                        "webhook_url": {"type": "string", "description": "Webhook URL（可选，默认用全局配置）"},
                    },
                    "required": ["title", "content"],
                },
            },
        ]

    async def call_tool(self, tool_name: str, params: dict) -> dict:
        """统一工具调用入口"""
        if tool_name == "get_document_content":
            content = await self.client.get_doc_content(
                doc_id=params["doc_id"],
                doc_type=params.get("doc_type", "alidoc"),
            )
            return {"content": content}

        elif tool_name == "list_space_documents":
            docs = await self.client.list_docs(
                space_id=params["space_id"],
                parent_id=params.get("parent_id", "0"),
            )
            return {"documents": docs}

        elif tool_name == "search_documents":
            results = await self.client.search_docs(
                keyword=params["keyword"],
                space_id=params.get("space_id"),
            )
            return {"results": results}

        elif tool_name == "send_markdown_message":
            from backend.config import settings
            webhook_url = params.get("webhook_url") or settings.dingtalk_webhook_url
            secret = settings.dingtalk_webhook_secret
            result = await self.client.send_markdown(
                webhook_url=webhook_url,
                title=params["title"],
                content=params["content"],
                secret=secret if secret else None,
            )
            return result

        else:
            raise ValueError(f"未知工具: {tool_name}")
