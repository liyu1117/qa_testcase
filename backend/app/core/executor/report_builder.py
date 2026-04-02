"""执行报告生成器 - HTML 格式"""

import html
import json
from datetime import datetime


class ReportBuilder:
    """HTML 执行报告构建"""

    def build(self, job_data: dict, results: list[dict]) -> str:
        """
        生成 HTML 格式执行报告
        job_data: {name, total_cases, passed, failed, skipped, duration, env_config}
        results: [{testcase_title, status, request_info, response_info, assertion_results, error_message}]
        """
        total = job_data.get("total_cases", 0)
        passed = job_data.get("passed", 0)
        failed = job_data.get("failed", 0)
        skipped = job_data.get("skipped", 0)
        duration = job_data.get("duration", 0)
        pass_rate = round(passed / total * 100, 1) if total > 0 else 0
        name = html.escape(job_data.get("name", "N/A"))
        base_url = html.escape(job_data.get("env_config", {}).get("base_url", "N/A"))
        exec_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # 状态颜色映射
        status_color = {
            "pass": "#52c41a",
            "fail": "#ff4d4f",
            "skip": "#d9d9d9",
            "error": "#fa541c",
        }

        # 构建失败用例详情
        failed_section = ""
        failed_results = [r for r in results if r.get("status") == "fail"]
        if failed_results:
            rows = ""
            for i, r in enumerate(failed_results, 1):
                title = html.escape(r.get("testcase_title", "N/A"))
                req = r.get("request_info", {})
                req_text = html.escape(f"{req.get('method', '')} {req.get('url', '')}".strip())
                resp = r.get("response_info", {})
                resp_status = resp.get("status_code", "-")
                resp_latency = resp.get("latency_ms", resp.get("duration_ms", "-"))
                error_msg = html.escape(r.get("error_message", "") or "")

                # 断言详情
                assertions_html = ""
                assertions = r.get("assertion_results", [])
                if assertions:
                    a_rows = ""
                    for a in assertions:
                        a_passed = a.get("passed", False)
                        a_color = "#52c41a" if a_passed else "#ff4d4f"
                        a_label = "PASS" if a_passed else "FAIL"
                        a_rows += f"""<tr>
                            <td>{html.escape(str(a.get('assertion_type', '')))}</td>
                            <td>{html.escape(str(a.get('path', '-')))}</td>
                            <td>{html.escape(str(a.get('expected', '')))}</td>
                            <td>{html.escape(str(a.get('actual', '')))}</td>
                            <td style="color:{a_color};font-weight:bold">{a_label}</td>
                        </tr>"""
                    assertions_html = f"""
                    <div style="margin-top:8px">
                        <strong>断言详情:</strong>
                        <table class="inner-table">
                            <tr><th>类型</th><th>路径</th><th>期望</th><th>实际</th><th>结果</th></tr>
                            {a_rows}
                        </table>
                    </div>"""

                error_html = f'<div style="margin-top:8px;color:#ff4d4f"><strong>错误:</strong> {error_msg}</div>' if error_msg else ""

                rows += f"""<tr>
                    <td>{i}</td>
                    <td>{title}</td>
                    <td><code>{req_text}</code></td>
                    <td>{resp_status}</td>
                    <td>{resp_latency}</td>
                    <td>{error_html}{assertions_html}</td>
                </tr>"""

            failed_section = f"""
            <div class="section">
                <h2>失败用例详情</h2>
                <table>
                    <tr><th>#</th><th>用例名称</th><th>请求</th><th>状态码</th><th>耗时(ms)</th><th>详情</th></tr>
                    {rows}
                </table>
            </div>"""

        # 全部用例结果
        all_rows = ""
        for i, r in enumerate(results, 1):
            s = r.get("status", "unknown")
            color = status_color.get(s, "#999")
            s_label = {"pass": "通过", "fail": "失败", "skip": "跳过", "error": "异常"}.get(s, s.upper())
            title = html.escape(r.get("testcase_title", "N/A"))
            latency = r.get("response_info", {}).get("latency_ms", r.get("response_info", {}).get("duration_ms", "-"))
            all_rows += f"""<tr>
                <td>{i}</td>
                <td>{title}</td>
                <td><span style="color:{color};font-weight:bold">{s_label}</span></td>
                <td>{latency}</td>
            </tr>"""

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>接口测试报告 - {name}</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background: #f0f2f5; color: #333; padding: 24px; }}
    .container {{ max-width: 960px; margin: 0 auto; }}
    .header {{ background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%); color: #fff; padding: 32px; border-radius: 8px 8px 0 0; }}
    .header h1 {{ font-size: 24px; margin-bottom: 12px; }}
    .header .meta {{ font-size: 14px; opacity: 0.9; line-height: 1.8; }}
    .summary {{ display: flex; gap: 16px; padding: 20px 32px; background: #fff; border-bottom: 1px solid #f0f0f0; flex-wrap: wrap; }}
    .stat-card {{ flex: 1; min-width: 120px; text-align: center; padding: 16px; border-radius: 6px; background: #fafafa; }}
    .stat-card .value {{ font-size: 28px; font-weight: 700; }}
    .stat-card .label {{ font-size: 12px; color: #999; margin-top: 4px; }}
    .section {{ background: #fff; padding: 24px 32px; border-bottom: 1px solid #f0f0f0; }}
    .section:last-child {{ border-radius: 0 0 8px 8px; border-bottom: none; }}
    h2 {{ font-size: 18px; margin-bottom: 16px; color: #1890ff; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #f0f0f0; }}
    th {{ background: #fafafa; font-weight: 600; color: #666; }}
    tr:hover {{ background: #fafafa; }}
    code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 12px; }}
    .inner-table {{ margin-top: 6px; font-size: 12px; }}
    .inner-table th, .inner-table td {{ padding: 4px 8px; }}
    .footer {{ text-align: center; padding: 16px; color: #999; font-size: 12px; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>接口测试执行报告</h1>
        <div class="meta">
            <div>任务名称: {name}</div>
            <div>执行时间: {exec_time} UTC</div>
            <div>目标环境: {base_url}</div>
        </div>
    </div>

    <div class="summary">
        <div class="stat-card">
            <div class="value" style="color:#333">{total}</div>
            <div class="label">总用例</div>
        </div>
        <div class="stat-card">
            <div class="value" style="color:#52c41a">{passed}</div>
            <div class="label">通过</div>
        </div>
        <div class="stat-card">
            <div class="value" style="color:#ff4d4f">{failed}</div>
            <div class="label">失败</div>
        </div>
        <div class="stat-card">
            <div class="value" style="color:#faad14">{skipped}</div>
            <div class="label">跳过</div>
        </div>
        <div class="stat-card">
            <div class="value" style="color:#1890ff">{pass_rate}%</div>
            <div class="label">通过率</div>
        </div>
        <div class="stat-card">
            <div class="value" style="color:#666">{round(duration, 2)}s</div>
            <div class="label">总耗时</div>
        </div>
    </div>

    {failed_section}

    <div class="section">
        <h2>全部用例结果</h2>
        <table>
            <tr><th>#</th><th>用例名称</th><th>状态</th><th>耗时(ms)</th></tr>
            {all_rows}
        </table>
    </div>

    <div class="footer">
        QA Master 自动生成 | {exec_time}
    </div>
</div>
</body>
</html>"""
