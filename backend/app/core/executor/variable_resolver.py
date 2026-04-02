"""变量替换系统 - 支持 {{VARIABLE}} 格式的变量解析"""

import re
import logging

logger = logging.getLogger(__name__)


class VariableResolver:
    """三级变量解析器: 执行环境 > 前序用例提取 > 全局默认"""

    def __init__(self, env_config: dict):
        # 从 env_config 提取变量
        self.env_vars: dict[str, str] = {}
        if env_config:
            self.env_vars["BASE_URL"] = env_config.get("base_url", "")
            # 将 headers 中的值也作为变量
            for key, value in env_config.get("headers", {}).items():
                var_name = key.upper().replace("-", "_")
                self.env_vars[var_name] = str(value)
            # 额外变量
            for key, value in env_config.get("variables", {}).items():
                self.env_vars[key.upper()] = str(value)

        # 前序用例提取的变量
        self.extracted_vars: dict[str, str] = {}

    def set_extracted_var(self, name: str, value: str):
        """设置从前序用例响应中提取的变量"""
        self.extracted_vars[name.upper()] = value

    def resolve(self, text: str) -> str:
        """替换文本中的 {{VARIABLE}} 占位符"""
        if not text:
            return text

        def _replace(match):
            var_name = match.group(1).strip().upper()
            # 优先级: 执行环境 > 前序提取 > 原样保留
            if var_name in self.env_vars:
                return self.env_vars[var_name]
            if var_name in self.extracted_vars:
                return self.extracted_vars[var_name]
            logger.warning(f"未解析的变量: {{{{{var_name}}}}}")
            return match.group(0)  # 原样返回

        return re.sub(r"\{\{(\w+)\}\}", _replace, text)

    def resolve_dict(self, data: dict | None) -> dict | None:
        """递归替换字典中的变量"""
        if not data:
            return data
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.resolve(value)
            elif isinstance(value, dict):
                result[key] = self.resolve_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self.resolve(v) if isinstance(v, str) else v for v in value
                ]
            else:
                result[key] = value
        return result
