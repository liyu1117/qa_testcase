"""钉钉通知服务 - 生成/执行事件通知"""

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.notification_log import NotificationLog
from backend.config import settings

logger = logging.getLogger(__name__)


class DingtalkNotifier:
    """钉钉通知服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    TYPE_LABELS = {"functional": "功能测试", "ui": "UI测试", "api": "接口测试"}

    async def notify_generation_done(self, job_name: str, job_id: int, case_count: int, duration: float, job_type: str = ""):
        """生成完成通知"""
        type_label = self.TYPE_LABELS.get(job_type, job_type)
        title = "测试用例生成完成"
        content = (
            f"### {title}\n\n"
            f"- **任务**: {job_name}\n"
            f"- **任务类型**: {type_label}\n"
            f"- **生成用例数**: {case_count} 条\n"
            f"- **耗时**: {round(duration, 1)}s\n"
            f"- **时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        await self._send(title, content, "generation_done", job_id)

    async def notify_generation_failed(self, job_name: str, job_id: int, error: str, job_type: str = ""):
        """生成失败通知"""
        type_label = self.TYPE_LABELS.get(job_type, job_type)
        title = "测试用例生成失败"
        content = (
            f"### {title}\n\n"
            f"- **任务**: {job_name}\n"
            f"- **任务类型**: {type_label}\n"
            f"- **错误**: {error[:200]}\n"
            f"- **时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        await self._send(title, content, "generation_failed", job_id)

    async def notify_execution_done(
        self, job_name: str, job_id: int, total: int, passed: int, failed: int, duration: float
    ):
        """执行完成通知"""
        pass_rate = round(passed / total * 100, 1) if total > 0 else 0
        status_text = "全部通过" if failed == 0 else f"{failed} 条失败"
        title = f"接口测试执行完成 - {status_text}"
        content = (
            f"### {title}\n\n"
            f"- **任务**: {job_name}\n"
            f"- **通过率**: {pass_rate}% ({passed}/{total})\n"
            f"- **失败**: {failed} 条\n"
            f"- **耗时**: {round(duration, 1)}s\n"
            f"- **时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        await self._send(title, content, "execution_done", job_id)

    async def notify_execution_failed(self, job_name: str, job_id: int, error: str):
        """执行失败通知"""
        title = "接口测试执行异常"
        content = (
            f"### {title}\n\n"
            f"- **任务**: {job_name}\n"
            f"- **错误**: {error[:200]}\n"
            f"- **时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        await self._send(title, content, "execution_failed", job_id)


    async def notify_upload_done(
        self,
        job_name: str,
        job_id: int,
        dingtalk_url: str,
        upload_format: str = "md",
        job_type: str = "",
    ):
        """上传到钉钉成功通知"""
        type_label = self.TYPE_LABELS.get(job_type, job_type)
        view_tip = "可在线查看" if upload_format == "md" else "建议下载后使用 XMind 客户端打开"

        title = "测试用例上传到钉钉成功"
        content = (
            f"### {title}\n\n"
            f"- **任务名称**: {job_name}\n"
            f"- **任务类型**: {type_label}\n"
            f"- **上传格式**: {upload_format}\n"
            f"- **查看说明**: {view_tip}\n"
            f"- **钉钉链接**: {dingtalk_url}\n"
            f"- **时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )

        await self._send(title, content, "upload_done", job_id)

    async def _send(self, title: str, content: str, event_type: str, related_id: int):
        """发送钉钉通知并记录日志"""
        from backend.app.api.v1.notifications import _notification_config

        log = NotificationLog(
            event_type=event_type,
            related_id=related_id,
            channel="dingtalk",
            message_title=title,
            message_body=content,
            status="pending",
        )

        try:
            # 检查是否启用通知
            if not _notification_config.get("enabled", True):
                log.status = "failed"
                log.error_message = "通知已关闭"
                self.db.add(log)
                await self.db.commit()
                return

            webhook_url = _notification_config.get("dingtalk_webhook_url") or settings.dingtalk_webhook_url
            if not webhook_url:
                log.status = "failed"
                log.error_message = "未配置钉钉 Webhook URL"
                self.db.add(log)
                await self.db.commit()
                logger.warning("钉钉通知跳过: 未配置 Webhook URL")
                return

            webhook_secret = _notification_config.get("dingtalk_webhook_secret") or settings.dingtalk_webhook_secret

            from mcp_servers.dingtalk_mcp.client import DingtalkClient
            client = DingtalkClient(
                app_key=settings.dingtalk_app_key,
                app_secret=settings.dingtalk_app_secret,
            )
            result = await client.send_markdown(
                webhook_url=webhook_url,
                title=title,
                content=content,
                secret=webhook_secret or None,
            )

            if result.get("errcode") == 0:
                log.status = "success"
            else:
                log.status = "failed"
                log.error_message = str(result)

        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)
            logger.error(f"钉钉通知发送失败: {e}")

        self.db.add(log)
        await self.db.commit()
