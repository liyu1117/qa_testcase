"""Figma REST API 客户端"""

import logging

import httpx

logger = logging.getLogger(__name__)


class FigmaClient:
    """Figma REST API v1 客户端"""

    API_BASE = "https://api.figma.com/v1"

    def __init__(self, access_token: str):
        self.access_token = access_token

    def _headers(self) -> dict:
        return {"X-Figma-Token": self.access_token}

    async def _get(self, path: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.API_BASE}{path}",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_file(self, file_key: str) -> dict:
        """获取文件元数据（页面列表）"""
        result = await self._get(f"/files/{file_key}", params={"depth": 1})
        return result

    async def get_file_pages(self, file_key: str) -> list[dict]:
        """获取文件的所有页面"""
        result = await self.get_file(file_key)
        document = result.get("document", {})
        pages = []
        for child in document.get("children", []):
            pages.append({
                "id": child["id"],
                "name": child["name"],
                "type": child.get("type"),
            })
        return pages

    async def get_node(self, file_key: str, node_id: str) -> dict:
        """获取指定节点的详细信息"""
        result = await self._get(f"/files/{file_key}/nodes", params={"ids": node_id})
        nodes = result.get("nodes", {})
        return nodes.get(node_id, {}).get("document", {})

    async def get_page_frames(self, file_key: str, page_id: str) -> list[dict]:
        """获取指定页面的所有 Frame"""
        node = await self.get_node(file_key, page_id)
        frames = []
        for child in node.get("children", []):
            if child.get("type") == "FRAME":
                frames.append({
                    "id": child["id"],
                    "name": child["name"],
                    "width": child.get("absoluteBoundingBox", {}).get("width"),
                    "height": child.get("absoluteBoundingBox", {}).get("height"),
                })
        return frames

    async def export_image(
        self, file_key: str, node_id: str, scale: float = 2.0, format: str = "png"
    ) -> str:
        """导出节点为图片，返回图片 URL"""
        result = await self._get(
            f"/images/{file_key}",
            params={"ids": node_id, "scale": scale, "format": format},
        )
        images = result.get("images", {})
        return images.get(node_id, "")

    async def get_text_content(self, file_key: str, node_id: str) -> list[dict]:
        """提取节点中所有文本内容"""
        node = await self.get_node(file_key, node_id)
        texts = []
        self._extract_texts(node, texts)
        return texts

    def _extract_texts(self, node: dict, results: list):
        """递归提取文本节点"""
        if node.get("type") == "TEXT":
            results.append({
                "name": node.get("name", ""),
                "characters": node.get("characters", ""),
                "style": {
                    "fontSize": node.get("style", {}).get("fontSize"),
                    "fontWeight": node.get("style", {}).get("fontWeight"),
                    "fills": node.get("fills", []),
                },
            })
        for child in node.get("children", []):
            self._extract_texts(child, results)

    async def get_component_info(self, file_key: str, node_id: str) -> dict:
        """获取组件详细信息"""
        node = await self.get_node(file_key, node_id)
        return {
            "id": node.get("id"),
            "name": node.get("name"),
            "type": node.get("type"),
            "boundingBox": node.get("absoluteBoundingBox"),
            "constraints": node.get("constraints"),
            "fills": node.get("fills"),
            "strokes": node.get("strokes"),
            "effects": node.get("effects"),
            "children_count": len(node.get("children", [])),
        }
