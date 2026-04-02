"""接口自动化测试脚本 - 由 QA Master 自动生成"""

import json
import os
import re
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


@pytest.fixture(scope="session")
def valid_token():
    return os.environ.get("VALID_TOKEN", "test_valid_token_123456")


@pytest.fixture(scope="session")
def invalid_token():
    return os.environ.get("INVALID_TOKEN", "test_invalid_token_abcdef")


def test_case_001_send_vip_success(base_url, default_headers, timeout, valid_token):
    """赠送会员-有效参数赠送成功"""
    url = f"{base_url}/next/app/vip/send/v2"
    headers = {**default_headers, "Authorization": f"Bearer {valid_token}", "Content-Type": "application/json"}
    body = {
        "openday": 8,
        "watermarkCount": 100,
        "sourceDetail": "daily_active_reward_20250317_android"
    }
    start_time = time.time()
    resp = requests.post(url, json=body, headers=headers, timeout=timeout)
    end_time = time.time()
    response_time_ms = (end_time - start_time) * 1000

    assert resp.status_code == 200, f"期望 200，实际 {resp.status_code}"
    data = resp.json()
    assert data.get("code") == 0, f"期望 code=0，实际 {data.get('code')}"
    assert response_time_ms < 2000, f"期望响应时间<2000ms，实际 {response_time_ms:.2f}ms"


def test_case_002_missing_openday(base_url, default_headers, timeout, valid_token):
    """赠送会员-缺失必填参数openday"""
    url = f"{base_url}/next/app/vip/send/v2"
    headers = {**default_headers, "Authorization": f"Bearer {valid_token}", "Content-Type": "application/json"}
    body = {
        "watermarkCount": 100,
        "sourceDetail": "daily_active_reward_20250317_android"
    }
    start_time = time.time()
    resp = requests.post(url, json=body, headers=headers, timeout=timeout)
    end_time = time.time()
    response_time_ms = (end_time - start_time) * 1000

    assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}"
    data = resp.json()
    assert data.get("code") in [40001, 400], f"期望 code为参数缺失类错误码，实际 {data.get('code')}"
    assert "openday" in data.get("message", "").lower(), f"期望提示包含'openday'，实际 {data.get('message')}"
    assert response_time_ms < 2000, f"期望响应时间<2000ms，实际 {response_time_ms:.2f}ms"


def test_case_003_missing_watermarkcount(base_url, default_headers, timeout, valid_token):
    """赠送会员-缺失必填参数watermarkCount"""
    url = f"{base_url}/next/app/vip/send/v2"
    headers = {**default_headers, "Authorization": f"Bearer {valid_token}", "Content-Type": "application/json"}
    body = {
        "openday": 8,
        "sourceDetail": "daily_active_reward_20250317_android"
    }
    start_time = time.time()
    resp = requests.post(url, json=body, headers=headers, timeout=timeout)
    end_time = time.time()
    response_time_ms = (end_time - start_time) * 1000

    assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}"
    data = resp.json()
    assert data.get("code") in [40001, 400], f"期望 code为参数缺失类错误码，实际 {data.get('code')}"
    assert "watermarkcount" in data.get("message", "").lower(), f"期望提示包含'watermarkCount'，实际 {data.get('message')}"
    assert response_time_ms < 2000, f"期望响应时间<2000ms，实际 {response_time_ms:.2f}ms"


def test_case_004_missing_sourcedetail(base_url, default_headers, timeout, valid_token):
    """赠送会员-缺失必填参数sourceDetail"""
    url = f"{base_url}/next/app/vip/send/v2"
    headers = {**default_headers, "Authorization": f"Bearer {valid_token}", "Content-Type": "application/json"}
    body = {
        "openday": 8,
        "watermarkCount": 100
    }
    start_time = time.time()
    resp = requests.post(url, json=body, headers=headers, timeout=timeout)
    end_time = time.time()
    response_time_ms = (end_time - start_time) * 1000

    assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}"
    data = resp.json()
    assert data.get("code") in [40001, 400], f"期望 code为参数缺失类错误码，实际 {data.get('code')}"
    assert "sourcedetail" in data.get("message", "").lower(), f"期望提示包含'sourceDetail'，实际 {data.get('message')}"
    assert response_time_ms < 2000, f"期望响应时间<2000ms，实际 {response_time_ms:.2f}ms"


def test_case_005_sourcedetail_empty(base_url, default_headers, timeout, valid_token):
    """赠送会员-sourceDetail参数为空字符串"""
    url = f"{base_url}/next/app/vip/send/v2"
    headers = {**default_headers, "Authorization": f"Bearer {valid_token}", "Content-Type": "application/json"}
    body = {
        "openday": 8,
        "watermarkCount": 100,
        "sourceDetail": ""
    }
    start_time = time.time()
    resp = requests.post(url, json=body, headers=headers, timeout=timeout)
    end_time = time.time()
    response_time_ms = (end_time - start_time) * 1000

    assert resp.status_code == 400, f"期望 400，实际 {resp.status_code}"
    data = resp.json()
    assert data.get("code") in [40002, 400], f"期望 code为参数格式类错误码，实际 {data.get('code')}"
    assert "sourcedetail" in data.get("message", "").lower(), f"期望提示包含'sourceDetail'，实际 {data.get('message')}"
    assert response_time_ms < 2000, f"期望响应时间<2000