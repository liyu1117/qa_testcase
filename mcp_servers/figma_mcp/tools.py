"""Figma MCP 工具定义"""

from mcp_servers.figma_mcp.client import FigmaClient


class FigmaTools:
    """Figma MCP 工具集"""

    def __init__(self, client: FigmaClient):
        self.client = client

    def get_tool_definitions(self) -> list[dict]:
        return [
            {
                "name": "get_file_pages",
                "description": "获取 Figma 文件的所有页面列表",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_key": {"type": "string", "description": "Figma 文件 Key"},
                    },
                    "required": ["file_key"],
                },
            },
            {
                "name": "get_page_frames",
                "description": "获取指定页面的所有 Frame（屏幕/组件）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_key": {"type": "string", "description": "Figma 文件 Key"},
                        "page_id": {"type": "string", "description": "页面 Node ID"},
                    },
                    "required": ["file_key", "page_id"],
                },
            },
            {
                "name": "get_frame_screenshot",
                "description": "获取指定 Frame 的渲染截图 URL",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_key": {"type": "string", "description": "Figma 文件 Key"},
                        "node_id": {"type": "string", "description": "Frame Node ID"},
                        "scale": {"type": "number", "description": "缩放倍数", "default": 2.0},
                    },
                    "required": ["file_key", "node_id"],
                },
            },
            {
                "name": "get_text_content",
                "description": "批量提取页面中所有文本内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_key": {"type": "string", "description": "Figma 文件 Key"},
                        "node_id": {"type": "string", "description": "Node ID"},
                    },
                    "required": ["file_key", "node_id"],
                },
            },
            {
                "name": "get_component_info",
                "description": "获取指定组件的详细属性信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_key": {"type": "string", "description": "Figma 文件 Key"},
                        "node_id": {"type": "string", "description": "Component Node ID"},
                    },
                    "required": ["file_key", "node_id"],
                },
            },
        ]

    async def call_tool(self, tool_name: str, params: dict) -> dict:
        if tool_name == "get_file_pages":
            pages = await self.client.get_file_pages(params["file_key"])
            return {"pages": pages}

        elif tool_name == "get_page_frames":
            frames = await self.client.get_page_frames(params["file_key"], params["page_id"])
            return {"frames": frames}

        elif tool_name == "get_frame_screenshot":
            url = await self.client.export_image(
                params["file_key"], params["node_id"], scale=params.get("scale", 2.0)
            )
            return {"image_url": url}

        elif tool_name == "get_text_content":
            texts = await self.client.get_text_content(params["file_key"], params["node_id"])
            return {"texts": texts}

        elif tool_name == "get_component_info":
            info = await self.client.get_component_info(params["file_key"], params["node_id"])
            return info

        else:
            raise ValueError(f"未知工具: {tool_name}")
