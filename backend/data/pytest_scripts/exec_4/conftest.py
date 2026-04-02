"""由 QA Master 自动生成的 conftest.py"""

import json
import os

import pytest


@pytest.fixture(scope="session")
def base_url():
    """从环境变量读取 Base URL"""
    return os.environ.get("BASE_URL", "https://test.xhey.top")


@pytest.fixture(scope="session")
def default_headers():
    """从环境变量读取默认请求头"""
    raw = os.environ.get("DEFAULT_HEADERS", '{"Accept-Encoding": "gzip", "Content-Type": "application/json", "x-user-id": "xuser-df7f4883-986a-4b64-b797-455c6609c148", "x-sign-id": "f42a294454e5639932b1070324b86903", "device_id": "93d61a6764dabcbb"}')
    return json.loads(raw)


@pytest.fixture(scope="session")
def timeout():
    """从环境变量读取请求超时时间"""
    return int(os.environ.get("REQUEST_TIMEOUT", "50"))
