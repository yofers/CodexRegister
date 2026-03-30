"""
邮件客户端工厂
"""

import sys

from .custom_mail_client import init_custom_mail_client
from .duckmail_client import init_duckmail_client
from .guerrilla_mail_client import init_guerrilla_mail_client
from .mail_tm_client import init_mail_tm_client


def init_mail_client(config):
    """按配置初始化邮件客户端"""
    provider = str(config.get("mail_provider", "duckmail")).strip().lower()

    if provider in {"duckmail", "duck"}:
        return init_duckmail_client(config)
    if provider in {"mail_tm", "mailtm", "mail.tm"}:
        return init_mail_tm_client(config)
    if provider in {"guerrilla", "guerrilla_mail", "guerrillamail"}:
        return init_guerrilla_mail_client(config)
    if provider in {"custom", "manual"}:
        return init_custom_mail_client(config)

    print(f"❌ 不支持的 mail_provider: {provider}")
    sys.exit(1)
