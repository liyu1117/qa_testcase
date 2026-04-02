"""钉钉开放平台 HTTP 客户端"""

import hashlib
import hmac
import base64
import time
import logging
import urllib.parse

import httpx

logger = logging.getLogger(__name__)


class DingtalkClient:
    """钉钉开放平台 API 客户端"""

    AUTH_URL = "https://oapi.dingtalk.com/gettoken"
    API_BASE = "https://api.dingtalk.com"

    def __init__(self, app_key: str, app_secret: str):
        self.app_key = app_key
        self.app_secret = app_secret
        self._access_token: str | None = None
        self._token_expires_at: float = 0

    async def _ensure_token(self):
        """获取/刷新 access_token"""
        if self._access_token and time.time() < self._token_expires_at:
            return

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                self.AUTH_URL,
                params={"appkey": self.app_key, "appsecret": self.app_secret},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode") != 0:
                raise Exception(f"钉钉认证失败: {data.get('errmsg')}")

            self._access_token = data["access_token"]
            self._token_expires_at = time.time() + data.get("expires_in", 7200) - 300
            logger.info("钉钉 access_token 获取成功")

    async def _api_request(self, method: str, path: str, **kwargs) -> dict:
        """通用 API 请求"""
        await self._ensure_token()
        url = f"{self.API_BASE}{path}"
        headers = {
            "x-acs-dingtalk-access-token": self._access_token,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(method, url, headers=headers, **kwargs)
            resp.raise_for_status()
            return resp.json()

    # ---- 文档相关 ----

    async def list_spaces(self, union_id: str) -> list[dict]:
        """列出知识库空间"""
        result = await self._api_request(
            "POST",
            f"/v1.0/doc/spaces/query",
            json={"unionId": union_id},
        )
        return result.get("spaces", [])

    async def list_docs(self, space_id: str, parent_id: str = "0") -> list[dict]:
        """列出文档列表"""
        result = await self._api_request(
            "GET",
            f"/v1.0/doc/spaces/{space_id}/docs",
            params={"parentId": parent_id, "maxResults": 50},
        )
        return result.get("items", [])

    async def get_doc_content(self, doc_id: str, doc_type: str = "alidoc") -> str:
        """获取文档内容（Markdown格式）"""
        result = await self._api_request(
            "GET",
            f"/v1.0/doc/documents/{doc_id}",
            params={"docType": doc_type},
        )
        return result.get("body", {}).get("content", "")

    async def search_docs(self, keyword: str, space_id: str | None = None) -> list[dict]:
        """搜索文档"""
        payload = {"keyword": keyword, "maxResults": 20}
        if space_id:
            payload["spaceId"] = space_id
        result = await self._api_request("POST", "/v1.0/doc/docs/search", json=payload)
        return result.get("items", [])

    # ---- 通知相关 ----

    @staticmethod
    def _sign_webhook(secret: str) -> tuple[str, str]:
        """生成 Webhook 签名"""
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode("utf-8"))
        return timestamp, sign

    async def send_markdown(
        self,
        webhook_url: str,
        title: str,
        content: str,
        secret: str | None = None,
        at_mobiles: list[str] | None = None,
    ) -> dict:
        """发送 Markdown 消息到钉钉群"""
        url = webhook_url
        if secret:
            timestamp, sign = self._sign_webhook(secret)
            url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"

        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": content},
        }
        if at_mobiles:
            payload["at"] = {"atMobiles": at_mobiles, "isAtAll": False}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()
            if result.get("errcode") != 0:
                logger.error(f"钉钉消息发送失败: {result}")
            return result
