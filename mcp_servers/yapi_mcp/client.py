"""YApi HTTP 客户端"""

import logging

import httpx

logger = logging.getLogger(__name__)


class YApiClient:
    """YApi 平台 API 客户端"""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token

    async def _get(self, path: str, params: dict | None = None) -> dict:
        params = params or {}
        params["token"] = self.token
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{self.base_url}{path}", params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode") != 0:
                raise Exception(f"YApi 请求失败: {data.get('errmsg')}")
            return data.get("data", data)

    async def list_projects(self, group_id: int | None = None) -> list[dict]:
        """获取项目列表"""
        params = {}
        if group_id:
            params["group_id"] = group_id
        return await self._get("/api/project/list", params=params)

    async def get_project(self, project_id: int) -> dict:
        """获取项目详情"""
        return await self._get(f"/api/project/get", params={"id": project_id})

    async def list_categories(self, project_id: int) -> list[dict]:
        """获取项目下的接口分类列表"""
        return await self._get("/api/interface/getCatMenu", params={"project_id": project_id})

    async def list_interfaces(self, project_id: int, cat_id: int | None = None, page: int = 1, limit: int = 200) -> dict:
        """获取接口列表"""
        params = {"project_id": project_id, "page": page, "limit": limit}
        if cat_id:
            params["catid"] = cat_id
        return await self._get("/api/interface/list", params=params)

    async def get_interface_detail(self, interface_id: int) -> dict:
        """获取单个接口完整定义"""
        return await self._get("/api/interface/get", params={"id": interface_id})

    async def search_interfaces(self, project_id: int, keyword: str) -> list[dict]:
        """搜索接口"""
        result = await self.list_interfaces(project_id)
        interfaces = result.get("list", [])
        return [i for i in interfaces if keyword.lower() in (i.get("title", "") + i.get("path", "")).lower()]

    async def find_interfaces_by_paths(self, project_id: int, paths: list[str]) -> list[dict]:
        """按路径列表精确匹配接口，只获取匹配接口的详情"""
        result = await self.list_interfaces(project_id)
        interfaces = result.get("list", [])
        normalized = {p.rstrip('/') for p in paths}
        matched = []
        for item in interfaces:
            if item.get("path", "").rstrip('/') in normalized:
                detail = await self.get_interface_detail(item["_id"])
                matched.append(detail)
        return matched

    def format_interface_as_markdown(self, interface: dict) -> str:
        """将接口定义格式化为 Markdown"""
        method = interface.get("method", "GET").upper()
        path = interface.get("path", "")
        title = interface.get("title", "")

        md = f"### {method} {path}\n"
        md += f"**描述**: {title}\n\n"

        # 请求参数
        req_body = interface.get("req_body_other", "")
        req_body_type = interface.get("req_body_type", "")
        if req_body:
            md += f"**请求体** ({req_body_type}):\n```json\n{req_body}\n```\n\n"

        # Query 参数
        req_query = interface.get("req_query", [])
        if req_query:
            md += "**Query 参数**:\n| 参数名 | 必须 | 说明 |\n|--------|------|------|\n"
            for q in req_query:
                md += f"| {q.get('name', '')} | {q.get('required', '0')} | {q.get('desc', '')} |\n"
            md += "\n"

        # 请求头
        req_headers = interface.get("req_headers", [])
        if req_headers:
            md += "**请求头**:\n| Key | Value | 必须 |\n|-----|-------|------|\n"
            for h in req_headers:
                md += f"| {h.get('name', '')} | {h.get('value', '')} | {h.get('required', '0')} |\n"
            md += "\n"

        # 响应
        res_body = interface.get("res_body", "")
        if res_body:
            md += f"**响应体**:\n```json\n{res_body}\n```\n\n"

        return md
