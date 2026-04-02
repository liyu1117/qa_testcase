import json
import logging
import base64
import httpx

from backend.config import settings

logger = logging.getLogger(__name__)


class DingtalkMCPUploader:

    def __init__(self, mcp_url: str | None = None):
        self.mcp_url = mcp_url or settings.dingtalk_mcp_url

    async def _initialize(self):
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
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                },
            )
            resp.raise_for_status()

    async def _call_tool(self, name: str, args: dict, tool_id: int):
        payload = {
            "jsonrpc": "2.0",
            "id": tool_id,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": args,
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
            self.mcp_url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        if "error" in data:
            raise Exception(data["error"])

        return data.get("result", {})

    # ✅ Markdown → 文档
    async def upload_markdown_as_doc(self, filename: str, markdown: str) -> str:
        await self._initialize()

        create_args = {
            "name": filename,
            "markdown": markdown,
        }

        if getattr(settings, "dingtalk_folder_id", ""):
            create_args["folderId"] = settings.dingtalk_folder_id
        if getattr(settings, "dingtalk_workspace_id", ""):
            create_args["workspaceId"] = settings.dingtalk_workspace_id

        result = await self._call_tool(
            "create_document",
            create_args,
            2,
        )

        content = result.get("content", [])
        text = content[0].get("text", "") if content else ""

        try:
            parsed = json.loads(text)
            return parsed.get("docUrl", "")
        except:
            logger.error(f"create_document JSON解析失败: {text}")
            return ""

    # 🔥 真正文件上传（支持 xmind）
    async def upload_file(self, filename: str, file_bytes: bytes) -> str:
        await self._initialize()

        # Step1: 获取上传信息
        # upload_info = await self._call_tool(
        #     "get_file_upload_info",
        #     {
        #         "folderId": "",  # 可填目录,默认上传到“我的文档根目录”
        #     },
        #     2,
        # )
        upload_args = {}
        if getattr(settings, "dingtalk_folder_id", ""):
            upload_args["folderId"] = settings.dingtalk_folder_id
        if getattr(settings, "dingtalk_workspace_id", ""):
            upload_args["workspaceId"] = settings.dingtalk_workspace_id

        upload_info = await self._call_tool(
            "get_file_upload_info",
            upload_args,
            2,
        )

        content = upload_info.get("content", [])
        text = content[0].get("text", "") if content else ""

        # parsed = json.loads(text)
        #
        # upload_key = parsed["uploadKey"]
        # upload_url = parsed["resourceUrl"]
        # headers = parsed.get("headers", {})
        try:
            parsed = json.loads(text)
        except Exception:
            logger.error(f"upload_info JSON解析失败: {text}")
            return ""

        if not parsed.get("success"):
            raise Exception(
                f"获取上传信息失败: {parsed.get('errorMsg') or parsed.get('errorCode') or text[:200]}"
            )

        upload_key = parsed["uploadKey"]
        upload_url = parsed["resourceUrl"]
        headers = parsed.get("headers", {}) or {}
        headers["Content-Type"] = ""

        # Step2: PUT 上传文件
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.put(
                upload_url,
                content=file_bytes,
                headers=headers,
            )
            resp.raise_for_status()

        # Step3: 提交文件
        # commit_res = await self._call_tool(
        #     "commit_uploaded_file",
        #     {
        #         "name": filename,
        #         "fileSize": len(file_bytes),
        #         "uploadKey": upload_key,
        #     },
        #     3,
        # )
        commit_args = {
            "name": filename,
            "fileSize": len(file_bytes),
            "uploadKey": upload_key,
            "convertToOnlineDoc": False,
        }

        if getattr(settings, "dingtalk_folder_id", ""):
            commit_args["folderId"] = settings.dingtalk_folder_id
        if getattr(settings, "dingtalk_workspace_id", ""):
            commit_args["workspaceId"] = settings.dingtalk_workspace_id

        commit_res = await self._call_tool(
            "commit_uploaded_file",
            commit_args,
            3,
        )

        # content = commit_res.get("content", [])
        # text = content[0].get("text", "") if content else ""
        #
        # parsed = json.loads(text)
        #
        # return parsed.get("docUrl", "")
        content = commit_res.get("content", [])
        text = content[0].get("text", "") if content else ""

        # 🔥 打日志（先看真实返回）
        logger.info(f"commit_res raw: {commit_res}")
        logger.info(f"text: {text}")

        # try:
        #     parsed = json.loads(text)
        # except Exception as e:
        #     logger.error(f"JSON解析失败: {text}")
        #     return ""
        #
        # # ✅ 优先拿 docUrl
        # doc_url = parsed.get("docUrl")
        #
        # # 🔥 兜底拼接（关键修复）
        # if not doc_url:
        #     node_id = parsed.get("nodeId") or parsed.get("dentryUuid")
        #     if node_id:
        #         doc_url = f"https://alidocs.dingtalk.com/i/nodes/{node_id}"
        #
        # return doc_url or ""
        try:
            parsed = json.loads(text)
        except Exception:
            logger.error(f"commit JSON解析失败: {text}")
            return ""

        if not parsed.get("success"):
            raise Exception(
                f"提交上传文件失败: {parsed.get('errorMsg') or parsed.get('errorCode') or text[:200]}"
            )

        doc_url = parsed.get("docUrl")

        if not doc_url:
            node_id = parsed.get("nodeId") or parsed.get("dentryUuid")
            if node_id:
                doc_url = f"https://alidocs.dingtalk.com/i/nodes/{node_id}"

        return doc_url or ""