"""
自定义邮箱客户端

职责：
1. 提供用户指定的邮箱地址
2. 在需要验证码时，提示用户手动输入
"""

import sys
import time
import re


class CustomMailClient:
    """自定义邮箱客户端，兼容现有 mail client 接口"""

    def __init__(self, config=None, proxy=None):
        self.config = config or {}
        self.proxy = proxy
        self.api_base = "manual-input"
        self.current_email = None
        self._used_codes = set()

    def _prompt_email(self):
        """交互式获取邮箱地址"""
        while True:
            if self.current_email:
                email = input(f"请输入自定义邮箱 [{self.current_email}]: ").strip()
                if not email:
                    email = self.current_email
            else:
                email = input("请输入自定义邮箱: ").strip()
            if email:
                return email
            print("  [!] 邮箱不能为空，请重试")

    def create_temp_email(self):
        """
        返回自定义邮箱，保持与现有接口兼容

        Returns:
            tuple: (email, token)
        """
        email = self._prompt_email()
        self.current_email = email
        print(f"  ✅ 使用自定义邮箱: {self.current_email}")
        return self.current_email, None

    def fetch_emails(self, email=None):
        """自定义邮箱不负责自动收件，返回空列表保持兼容"""
        return []

    def extract_verification_code(self, content):
        """从输入文本中提取 6 位验证码"""
        if not content:
            return None

        match = re.search(r"\b(\d{6})\b", str(content))
        return match.group(1) if match else None

    def wait_for_verification_code(self, email, timeout=60, exclude_codes=None):
        """
        提示用户手动输入验证码
        """
        if exclude_codes is None:
            exclude_codes = set()

        all_exclude_codes = set(exclude_codes) | self._used_codes
        deadline = time.time() + timeout

        print(f"  ⏳ 请到邮箱 {email} 查收验证码 (最大 {timeout}s)...")
        print("  输入 6 位验证码；输入 quit 取消")

        while time.time() < deadline:
            raw = input("  验证码: ").strip()
            lower = raw.lower()

            if lower in {"quit", "exit", "q"}:
                print("  [!] 用户取消输入验证码")
                return None

            code = self.extract_verification_code(raw)
            if not code:
                print("  [!] 验证码格式不正确，应为 6 位数字")
                continue

            if code in all_exclude_codes:
                print("  [!] 该验证码已尝试过，请输入新的验证码")
                continue

            self._used_codes.add(code)
            print(f"  ✅ 验证码: {code}")
            return code

        print("  ⏰ 等待验证码超时")
        return None


def init_custom_mail_client(config):
    """初始化自定义邮箱客户端"""
    proxy = config.get("proxy", "")
    client = CustomMailClient(config=config, proxy=proxy)

    print("📧 正在初始化自定义邮箱客户端...")
    try:
        print("✅ 自定义邮箱客户端准备就绪")
        return client
    except Exception as e:
        print(f"❌ 自定义邮箱客户端初始化失败: {e}")
        sys.exit(1)
