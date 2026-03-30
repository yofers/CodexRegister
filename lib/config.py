"""
配置加载模块
"""

import os
import json


def load_config():
    """从 config.json 加载配置，环境变量优先级更高"""
    config = {
        "mail_provider": "custom",
        "proxy": "",
        "output_file": "registered_accounts.txt",
        "enable_oauth": True,
        "oauth_required": True,
        "token_json_dir": "tokens",
        "upload_api_url": "",
        "upload_api_token": "",
    }

    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                config.update(file_config)
        except Exception as e:
            print(f"⚠️ 加载 config.json 失败: {e}")

    # 环境变量优先级更高
    env_mappings = {
        "MAIL_PROVIDER": "mail_provider",
        "PROXY": "proxy",
        "ENABLE_OAUTH": "enable_oauth",
        "OAUTH_REQUIRED": "oauth_required",
        "TOKEN_JSON_DIR": "token_json_dir",
        "UPLOAD_API_URL": "upload_api_url",
        "UPLOAD_API_TOKEN": "upload_api_token",
    }

    for env_key, config_key in env_mappings.items():
        env_value = os.environ.get(env_key)
        if env_value is not None:
            if config_key in ["enable_oauth", "oauth_required"]:
                config[config_key] = env_value.lower() in ["1", "true", "yes", "y", "on"]
            else:
                config[config_key] = env_value

    return config


def as_bool(value):
    """将值转换为布尔值"""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
