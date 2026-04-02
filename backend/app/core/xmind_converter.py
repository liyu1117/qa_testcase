"""Markdown 测试用例 → XMind Zen 格式转换器

纯 Python 标准库实现，无外部依赖。
生成的 .xmind 文件兼容 XMind 2020+ / XMind Zen。
"""

import io
import json
import re
import uuid
import zipfile
from typing import Any


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _make_id() -> str:
    return uuid.uuid4().hex[:16]


def _make_topic(title: str, children: list[dict] | None = None) -> dict[str, Any]:
    topic: dict[str, Any] = {
        "id": _make_id(),
        "class": "topic",
        "title": title.strip(),
    }
    if children:
        topic["children"] = {"attached": children}
    return topic


# ---------------------------------------------------------------------------
# 通用 Markdown 表格解析
# ---------------------------------------------------------------------------

def _parse_table_rows(text: str) -> list[list[str]]:
    """解析 Markdown 表格，返回数据行（跳过表头和分隔行）"""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    rows: list[list[str]] = []
    for i, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        # 跳过分隔行（全是 - 或 :- 的行）
        if all(re.match(r'^[-:]+$', c) for c in cells):
            continue
        rows.append(cells)
    # 第一行是表头，后续是数据
    if len(rows) > 1:
        return rows[1:]
    return []


# ---------------------------------------------------------------------------
# 功能测试用例解析器
# ---------------------------------------------------------------------------

def _parse_functional(md_content: str) -> list[dict]:
    """解析功能测试用例 MD，返回按模块分组的 Topic 列表

    输出 XMind 结构（三层，兼容 case_depth=2 的分析脚本）：
      根节点 > 模块节点 > 用例节点 > (前置条件 / 测试步骤 / 预期结果)

    兼容两种格式：
    - ## TC-XXX / ## FT-XXX（二级标题）
    - ### TC-XXX / ### FT-XXX（三级标题，增强模式下的输出）
    """
    from collections import OrderedDict

    # 按 ## 或 ### 开头分割用例块
    blocks = re.split(r'(?=^#{2,3} )', md_content, flags=re.MULTILINE)

    # module_name -> list[topic_dict]
    module_cases: OrderedDict[str, list[dict]] = OrderedDict()

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # 提取标题行
        first_line_end = block.find('\n')
        if first_line_end == -1:
            first_line = block
            body = ""
        else:
            first_line = block[:first_line_end]
            body = block[first_line_end + 1:]

        # 去掉 ## 或 ### 前缀
        heading = re.sub(r'^#{2,3}\s+', '', first_line).strip()
        if not heading:
            continue

        # 跳过测试点清单等非用例段落
        if heading.startswith("第") and ("部分" in heading or "测试点清单" in heading):
            continue
        if heading == "补充用例":
            continue

        # 用例块通常包含 **优先级** 标记
        if '**优先级**' not in body and '优先级' not in body:
            continue

        children = []
        module_name = "未分类"
        priority_val = ""

        # 提取属性
        for attr_match in re.finditer(r'-\s*\*\*(.+?)\*\*:\s*(.+?)(?=\n-\s*\*\*|\n\n|\n\||\Z)', body, re.DOTALL):
            key = attr_match.group(1).strip()
            val = attr_match.group(2).strip()

            if key == '所属模块':
                module_name = val
                continue
            elif key == '优先级':
                priority_val = val
                continue
            elif key == '关联测试点':
                # 不作为子节点，信息已含在标题和模块中
                continue
            elif key == '前置条件':
                # 拆分有序列表
                cond_items = re.findall(r'\d+\.\s*(.+)', val)
                if cond_items:
                    children.append(_make_topic("前置条件", [_make_topic(c.strip()) for c in cond_items]))
                else:
                    children.append(_make_topic(f"前置条件: {val}"))
            elif key == '预期结果':
                children.append(_make_topic("预期结果", [_make_topic(val)]))
            else:
                children.append(_make_topic(f"{key}: {val}"))

        # 提取步骤表格，拆分为"操作步骤"和"预期结果"两个独立节点
        table_match = re.search(r'(\|.+步骤.+操作.+预期.+\|[\s\S]*?)(?=\n\n|\n-\s*\*\*|\Z)', body)
        if table_match:
            rows = _parse_table_rows(table_match.group(1))
            if rows:
                step_children = []
                expected_children = []
                for row in rows:
                    if len(row) >= 3:
                        step_children.append(_make_topic(f"步骤{row[0]}: {row[1]}"))
                        expected_children.append(_make_topic(f"步骤{row[0]}预期: {row[2]}"))
                    elif len(row) >= 2:
                        step_children.append(_make_topic(f"步骤{row[0]}: {row[1]}"))
                if step_children:
                    children.append(_make_topic("操作步骤", step_children))
                if expected_children:
                    children.append(_make_topic("预期结果", expected_children))

        # 优先级写入标题后缀，便于分析脚本识别
        case_title = heading
        if priority_val:
            case_title = f"{heading} [{priority_val}]"

        case_topic = _make_topic(case_title, children if children else None)
        module_cases.setdefault(module_name, []).append(case_topic)

    # 构建模块分组 Topic 列表
    module_topics = []
    for mod_name, cases in module_cases.items():
        module_topics.append(_make_topic(mod_name, cases))

    return module_topics


# ---------------------------------------------------------------------------
# API 接口测试用例解析器
# ---------------------------------------------------------------------------

def _parse_api(md_content: str) -> list[dict]:
    """解析 API 接口测试用例 MD"""
    blocks = re.split(r'(?=^## )', md_content, flags=re.MULTILINE)

    case_topics = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        first_line_end = block.find('\n')
        if first_line_end == -1:
            first_line = block
            body = ""
        else:
            first_line = block[:first_line_end]
            body = block[first_line_end + 1:]

        heading = first_line.lstrip('#').strip()
        if not heading:
            continue
        if '**优先级**' not in body and '**标题**' not in body:
            continue

        children = []

        # 提取加粗键值对属性
        for attr_match in re.finditer(r'\*\*(.+?)\*\*:\s*(.+)', body):
            key = attr_match.group(1).strip()
            val = attr_match.group(2).strip()
            if key in ('Headers', '请求体'):
                continue  # 单独处理
            children.append(_make_topic(f"{key}: {val}"))

        # 提取请求体
        req_body_match = re.search(r'\*\*请求体\*\*:\s*\n```(?:json)?\s*\n([\s\S]*?)\n```', body)
        if req_body_match:
            req_text = req_body_match.group(1).strip()
            # 简化展示：只取前 200 字符
            if len(req_text) > 200:
                req_text = req_text[:200] + "..."
            children.append(_make_topic(f"请求体: {req_text}"))

        # 提取断言规则表格
        assert_match = re.search(r'(###\s*断言规则[\s\S]*?)(?=\n\n\*\*|\Z)', body)
        if assert_match:
            rows = _parse_table_rows(assert_match.group(1))
            if rows:
                assert_children = []
                for row in rows:
                    if len(row) >= 4:
                        assert_children.append(_make_topic(f"{row[0]}: {row[1]} {row[2]} ({row[3]})"))
                    elif len(row) >= 3:
                        assert_children.append(_make_topic(f"{row[0]}: {row[1]} {row[2]}"))
                if assert_children:
                    children.append(_make_topic("断言规则", assert_children))

        case_topics.append(_make_topic(heading, children if children else None))

    return case_topics


# ---------------------------------------------------------------------------
# UI 测试用例解析器
# ---------------------------------------------------------------------------

def _parse_ui(md_content: str) -> list[dict]:
    """解析 UI 测试用例 MD"""
    blocks = re.split(r'(?=^## (?:UI-|测试用例\s+UI-))', md_content, flags=re.MULTILINE)

    case_topics = []
    for block in blocks:
        block = block.strip()
        if not block or not block.startswith('## '):
            continue

        first_line_end = block.find('\n')
        if first_line_end == -1:
            first_line = block
            body = ""
        else:
            first_line = block[:first_line_end]
            body = block[first_line_end + 1:]

        heading = first_line.lstrip('#').strip()
        if not heading:
            continue

        children = []

        # 提取属性
        for attr_match in re.finditer(r'-\s*\*\*(.+?)\*\*:\s*(.+)', body):
            key = attr_match.group(1).strip()
            val = attr_match.group(2).strip()
            if key == '前置条件':
                cond_parts = re.split(r';\s*(?=\d+\.)', val)
                if len(cond_parts) > 1:
                    cond_children = [_make_topic(c.strip()) for c in cond_parts if c.strip()]
                    children.append(_make_topic("前置条件", cond_children))
                else:
                    cond_items = re.findall(r'\d+\.\s*(.+?)(?=;\s*\d+\.|\Z)', val)
                    if cond_items:
                        children.append(_make_topic("前置条件", [_make_topic(c.strip()) for c in cond_items]))
                    else:
                        children.append(_make_topic(f"前置条件: {val}"))
            else:
                children.append(_make_topic(f"{key}: {val}"))

        # 提取检查清单 / 响应式断点验证表格
        table_sections = re.finditer(r'###\s*(.+?)\n([\s\S]*?)(?=\n###|\n---|\n##|\Z)', body)
        for tsec in table_sections:
            section_title = tsec.group(1).strip()
            section_body = tsec.group(2)
            rows = _parse_table_rows(section_body)
            if rows:
                row_children = []
                for row in rows:
                    # 尝试合并所有列为一行描述
                    row_text = " | ".join(c for c in row if c.strip())
                    if row_text:
                        row_children.append(_make_topic(row_text))
                if row_children:
                    children.append(_make_topic(section_title, row_children))

        case_topics.append(_make_topic(heading, children if children else None))

    return case_topics


# ---------------------------------------------------------------------------
# 通用解析器（兜底）
# ---------------------------------------------------------------------------

def _parse_generic(md_content: str) -> list[dict]:
    """通用解析：按 ## 标题分割"""
    blocks = re.split(r'(?=^## )', md_content, flags=re.MULTILINE)
    topics = []
    for block in blocks:
        block = block.strip()
        if not block or not block.startswith('## '):
            continue
        first_line_end = block.find('\n')
        if first_line_end == -1:
            heading = block.lstrip('#').strip()
            topics.append(_make_topic(heading))
        else:
            heading = block[:first_line_end].lstrip('#').strip()
            body = block[first_line_end + 1:].strip()
            if body:
                # 简单地把非空行作为子节点
                child_lines = [ln.strip() for ln in body.splitlines() if ln.strip() and not ln.strip().startswith('---')]
                children = [_make_topic(ln[:200]) for ln in child_lines[:50]]
                topics.append(_make_topic(heading, children if children else None))
            else:
                topics.append(_make_topic(heading))
    return topics


# ---------------------------------------------------------------------------
# XMind ZIP 打包
# ---------------------------------------------------------------------------

def _build_xmind_zip(root_title: str, case_topics: list[dict]) -> bytes:
    """将 Topic 列表打包为 XMind Zen 格式的 ZIP 字节流"""
    root_topic = _make_topic(root_title, case_topics if case_topics else [_make_topic("暂无内容")])

    content = [
        {
            "id": _make_id(),
            "class": "sheet",
            "title": root_title,
            "rootTopic": root_topic,
        }
    ]

    metadata = {
        "creator": {
            "name": "QA Testcase Platform",
            "version": "1.0.0",
        }
    }

    manifest = {
        "file-entries": {
            "content.json": {},
            "metadata.json": {},
        }
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.json", json.dumps(content, ensure_ascii=False, indent=2))
        zf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    return buf.getvalue()


# ---------------------------------------------------------------------------
# 对外公共接口
# ---------------------------------------------------------------------------

def convert_md_to_xmind(md_content: str, job_type: str, title: str) -> bytes:
    """将 Markdown 测试用例转换为 .xmind 文件字节流

    Args:
        md_content: Markdown 文本内容
        job_type: 任务类型 (functional / api / ui)
        title: 根节点标题（通常为任务名称）

    Returns:
        bytes: .xmind 文件的二进制内容
    """
    parser_map = {
        "functional": _parse_functional,
        "api": _parse_api,
        "ui": _parse_ui,
    }
    parser = parser_map.get(job_type, _parse_generic)
    case_topics = parser(md_content)

    if not case_topics:
        case_topics = _parse_generic(md_content)

    return _build_xmind_zip(title, case_topics)
