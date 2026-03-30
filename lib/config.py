"""
配置加载模块
"""

import os
import json
import importlib.util


DEFAULT_CONFIG = {
    "mail_provider": "custom",
    "proxy": "",
    "output_file": "registered_accounts.txt",
    "token_json_dir": "tokens",
    "upload_api_url": "",
    "upload_api_token": "",
}

PY_CONFIG_MAPPINGS = {
    "MAIL_PROVIDER": "mail_provider",
    "PROXY": "proxy",
    "OUTPUT_FILE": "output_file",
    "TOKEN_JSON_DIR": "token_json_dir",
    "UPLOAD_API_URL": "upload_api_url",
    "UPLOAD_API_TOKEN": "upload_api_token",
}

ENV_MAPPINGS = {
    "MAIL_PROVIDER": "mail_provider",
    "PROXY": "proxy",
    "TOKEN_JSON_DIR": "token_json_dir",
    "UPLOAD_API_URL": "upload_api_url",
    "UPLOAD_API_TOKEN": "upload_api_token",
}


def _load_py_config(config_path):
    """从 Python 配置文件中读取配置"""
    spec = importlib.util.spec_from_file_location("codex_register_app_config", config_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 Python 配置文件")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    config = {}

    config_dict = getattr(module, "CONFIG", None)
    if isinstance(config_dict, dict):
        for key, value in config_dict.items():
            if key in DEFAULT_CONFIG:
                config[key] = value

    for py_key, config_key in PY_CONFIG_MAPPINGS.items():
        if hasattr(module, py_key):
            config[config_key] = getattr(module, py_key)

    return config


def load_config():
    """加载配置，优先级：默认值 < config.json < app_config.py < 环境变量"""
    config = DEFAULT_CONFIG.copy()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    json_config_path = os.path.join(project_root, "config.json")
    if os.path.exists(json_config_path):
        try:
            with open(json_config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                config.update(file_config)
        except Exception as e:
            print(f"⚠️ 加载 config.json 失败: {e}")

    py_config_path = os.path.join(project_root, "app_config.py")
    if os.path.exists(py_config_path):
        try:
            file_config = _load_py_config(py_config_path)
            config.update(file_config)
        except Exception as e:
            print(f"⚠️ 加载 app_config.py 失败: {e}")

    for env_key, config_key in ENV_MAPPINGS.items():
        env_value = os.environ.get(env_key)
        if env_value is not None:
            config[config_key] = env_value

    return config


def as_bool(value):
    """将值转换为布尔值"""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
