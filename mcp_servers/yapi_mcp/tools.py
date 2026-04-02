"""YApi MCP 工具定义"""

from mcp_servers.yapi_mcp.client import YApiClient


class YApiTools:
    """YApi MCP 工具集"""

    def __init__(self, client: YApiClient):
        self.client = client

    def get_tool_definitions(self) -> list[dict]:
        return [
            {
                "name": "list_projects",
                "description": "获取 YApi 平台项目列表",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "group_id": {"type": "integer", "description": "分组ID（可选）"},
                    },
                },
            },
            {
                "name": "list_categories",
                "description": "获取项目下的接口分类列表",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "integer", "description": "项目ID"},
                    },
                    "required": ["project_id"],
                },
            },
            {
                "name": "get_interface_detail",
                "description": "获取单个接口的完整定义（含请求参数、响应结构）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "interface_id": {"type": "integer", "description": "接口ID"},
                    },
                    "required": ["interface_id"],
                },
            },
            {
                "name": "list_interfaces",
                "description": "获取项目或分类下的接口列表",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "integer", "description": "项目ID"},
                        "cat_id": {"type": "integer", "description": "分类ID（可选）"},
                    },
                    "required": ["project_id"],
                },
            },
            {
                "name": "search_interfaces",
                "description": "在项目中按关键词搜索接口",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_id": {"type": "integer", "description": "项目ID"},
                        "keyword": {"type": "string", "description": "搜索关键词"},
                    },
                    "required": ["project_id", "keyword"],
                },
            },
        ]

    async def call_tool(self, tool_name: str, params: dict) -> dict:
        if tool_name == "list_projects":
            projects = await self.client.list_projects(group_id=params.get("group_id"))
            return {"projects": projects}

        elif tool_name == "list_categories":
            categories = await self.client.list_categories(params["project_id"])
            return {"categories": categories}

        elif tool_name == "get_interface_detail":
            detail = await self.client.get_interface_detail(params["interface_id"])
            markdown = self.client.format_interface_as_markdown(detail)
            return {"detail": detail, "markdown": markdown}

        elif tool_name == "list_interfaces":
            result = await self.client.list_interfaces(
                params["project_id"], cat_id=params.get("cat_id")
            )
            return result

        elif tool_name == "search_interfaces":
            results = await self.client.search_interfaces(
                params["project_id"], params["keyword"]
            )
            return {"results": results}

        else:
            raise ValueError(f"未知工具: {tool_name}")
