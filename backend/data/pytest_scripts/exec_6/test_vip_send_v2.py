"""接口自动化测试脚本 - 赠送会员 /next/app/vip/send/v2
由 QA Master 自动生成，基于实际 API 响应格式修正
"""

import json
import os
import time

import pytest
import requests


@pytest.fixture(scope="session")
def base_url():
    return os.environ.get("BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def default_headers():
    raw = os.environ.get("DEFAULT_HEADERS", "{}")
    return json.loads(raw)


@pytest.fixture(scope="session")
def timeout():
    return int(os.environ.get("REQUEST_TIMEOUT", "30"))


# ──────── 基础请求参数 ────────

VALID_BODY = {
    "openday": 8,
    "watermarkCount": 100,
    "sourceDetail": "daily_active_reward_20250317_android",
}

API_PATH = "/next/app/vip/send/v2"


def _post(base_url, headers, body, timeout_val):
    """统一 POST 请求封装"""
    url = f"{base_url}{API_PATH}"
    start = time.time()
    resp = requests.post(url, json=body, headers=headers, timeout=timeout_val)
    elapsed_ms = (time.time() - start) * 1000
    return resp, elapsed_ms


# ──────── 测试用例 ────────

def test_case_001_send_vip_success(base_url, default_headers, timeout):
    """赠送会员-有效参数赠送成功"""
    headers = {**default_headers, "Content-Type": "application/json"}
    resp, elapsed_ms = _post(base_url, headers, VALID_BODY, timeout)

    assert resp.status_code == 200, f"HTTP 状态码期望 200，实际 {resp.status_code}"
    data = resp.json()
    assert data.get("code") == 200, f"业务码期望 200，实际 {data.get('code')}"
    assert data.get("msg") == "success", f"期望 msg='success'，实际 {data.get('msg')}"
    assert elapsed_ms < 2000, f"响应时间期望 <2000ms，实际 {elapsed_ms:.0f}ms"


def test_case_002_missing_openday(base_url, default_headers, timeout):
    """赠送会员-缺失必填参数openday"""
    headers = {**default_headers, "Content-Type": "application/json"}
    body = {k: v for k, v in VALID_BODY.items() if k != "openday"}
    resp, elapsed_ms = _post(base_url, headers, body, timeout)

    assert resp.status_code == 200, f"HTTP 状态码期望 200，实际 {resp.status_code}"
    data = resp.json()
    # 缺少必填参数应返回非成功的业务码或提示信息
    assert data.get("code") != 200 or data.get("msg") != "success", \
        f"缺少 openday 应返回错误，实际 code={data.get('code')}, msg={data.get('msg')}"
    assert elapsed_ms < 2000, f"响应时间期望 <2000ms，实际 {elapsed_ms:.0f}ms"


def test_case_003_missing_watermarkcount(base_url, default_headers, timeout):
    """赠送会员-缺失必填参数watermarkCount"""
    headers = {**default_headers, "Content-Type": "application/json"}
    body = {k: v for k, v in VALID_BODY.items() if k != "watermarkCount"}
    resp, elapsed_ms = _post(base_url, headers, body, timeout)

    assert resp.status_code == 200, f"HTTP 状态码期望 200，实际 {resp.status_code}"
    data = resp.json()
    assert data.get("code") != 200 or data.get("msg") != "success", \
        f"缺少 watermarkCount 应返回错误，实际 code={data.get('code')}, msg={data.get('msg')}"
    assert elapsed_ms < 2000, f"响应时间期望 <2000ms，实际 {elapsed_ms:.0f}ms"


def test_case_004_missing_sourcedetail(base_url, default_headers, timeout):
    """赠送会员-缺失必填参数sourceDetail"""
    headers = {**default_headers, "Content-Type": "application/json"}
    body = {k: v for k, v in VALID_BODY.items() if k != "sourceDetail"}
    resp, elapsed_ms = _post(base_url, headers, body, timeout)

    assert resp.status_code == 200, f"HTTP 状态码期望 200，实际 {resp.status_code}"
    data = resp.json()
    assert data.get("code") != 200 or data.get("msg") != "success", \
        f"缺少 sourceDetail 应返回错误，实际 code={data.get('code')}, msg={data.get('msg')}"
    assert elapsed_ms < 2000, f"响应时间期望 <2000ms，实际 {elapsed_ms:.0f}ms"


def test_case_005_sourcedetail_empty_string(base_url, default_headers, timeout):
    """赠送会员-sourceDetail参数为空字符串"""
    headers = {**default_headers, "Content-Type": "application/json"}
    body = {**VALID_BODY, "sourceDetail": ""}
    resp, elapsed_ms = _post(base_url, headers, body, timeout)

    assert resp.status_code == 200, f"HTTP 状态码期望 200，实际 {resp.status_code}"
    data = resp.json()
    # sourceDetail 有 minLength:1 约束，空字符串应被拒绝
    assert data.get("code") != 200 or data.get("msg") != "success", \
        f"sourceDetail 为空应返回错误，实际 code={data.get('code')}, msg={data.get('msg')}"
    assert elapsed_ms < 2000, f"响应时间期望 <2000ms，实际 {elapsed_ms:.0f}ms"


def test_case_006_openday_string_type(base_url, default_headers, timeout):
    """赠送会员-openday参数传字符串类型"""
    headers = {**default_headers, "Content-Type": "application/json"}
    body = {**VALID_BODY, "openday": "八天"}
    resp, elapsed_ms = _post(base_url, headers, body, timeout)

    assert resp.status_code == 200, f"HTTP 状态码期望 200，实际 {resp.status_code}"
    data = resp.json()
    # openday 要求 number 类型，传字符串应被拒绝
    assert data.get("code") != 200 or data.get("msg") != "success", \
        f"openday 传字符串应返回错误，实际 code={data.get('code')}, msg={data.get('msg')}"
    assert elapsed_ms < 2000, f"响应时间期望 <2000ms，实际 {elapsed_ms:.0f}ms"


def test_case_007_no_authorization(base_url, default_headers, timeout):
    """赠送会员-不携带Authorization鉴权Header"""
    headers = {**default_headers, "Content-Type": "application/json"}
    # 移除 Authorization 头
    headers.pop("Authorization", None)
    headers.pop("authorization", None)
    resp, elapsed_ms = _post(base_url, headers, VALID_BODY, timeout)

    data = resp.json()
    # 不携带鉴权信息应返回 401 或业务错误码
    is_auth_error = (
        resp.status_code == 401
        or data.get("code") not in [200, None]
        or data.get("msg") != "success"
    )
    assert is_auth_error, \
        f"未携带 Authorization 应返回鉴权错误，实际 status={resp.status_code}, code={data.get('code')}"
    assert elapsed_ms < 2000, f"响应时间期望 <2000ms，实际 {elapsed_ms:.0f}ms"


def test_case_008_invalid_authorization(base_url, default_headers, timeout):
    """赠送会员-携带无效Authorization鉴权Header"""
    headers = {
        **default_headers,
        "Content-Type": "application/json",
        "Authorization": "Bearer invalid_token_abcdef_999",
    }
    resp, elapsed_ms = _post(base_url, headers, VALID_BODY, timeout)

    data = resp.json()
    # 无效 token 应返回 401 或业务错误码
    is_auth_error = (
        resp.status_code == 401
        or data.get("code") not in [200, None]
        or data.get("msg") != "success"
    )
    assert is_auth_error, \
        f"无效 Authorization 应返回鉴权错误，实际 status={resp.status_code}, code={data.get('code')}"
    assert elapsed_ms < 2000, f"响应时间期望 <2000ms，实际 {elapsed_ms:.0f}ms"
