"""
DuckMail 临时邮箱客户端模块 (兼容 SkymailClient/MailTmClient 接口)
参考文档: https://raw.githubusercontent.com/MoonWeSif/DuckMail/main/public/llm-api-docs.txt
"""

import sys
import time
import re
import random
import string
from curl_cffi.requests import Session

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

class DuckMailClient:
    """DuckMail 邮箱服务客户端，适配了原先 SkymailClient 的接口"""

    def __init__(self, proxy=None):
        self.proxy = proxy
        self.api_base = "https://api.duckmail.sbs"
        self.current_email = None
        self.current_password = None
        self.token = None
        self._used_codes = set()
        
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
        self.session = Session(proxies=proxies, impersonate="chrome120")
        self.session.headers.update({
            "User-Agent": UA,
            "Accept": "application/json",
            "Content-Type": "application/json"
        })

    def _req(self, method, endpoint, params=None, json_data=None):
        """发送 API 请求"""
        url = f"{self.api_base}{endpoint}"
        headers = self.session.headers.copy()
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            
        try:
            r = self.session.request(method, url, params=params, json=json_data, headers=headers, timeout=20)
            if r.status_code in [200, 201]:
                return r.json()
            elif r.status_code == 204:
                return True
            else:
                print(f"  [!] DuckMail API 错误: HTTP {r.status_code} - {r.text}")
                return None
        except Exception as e:
            print(f"  [!] DuckMail API 请求异常: {e}")
            return None

    def get_domains(self):
        """获取可用的域名列表"""
        data = self._req("GET", "/domains")
        if data and "hydra:member" in data:
            # 过滤出已验证的域名
            domains = [d["domain"] for d in data["hydra:member"] if d.get("isVerified")]
            return domains
        return []

    def create_temp_email(self):
        """
        创建 DuckMail 临时邮箱账号并获取 Token
        """
        domains = self.get_domains()
        if not domains:
            raise Exception("获取 DuckMail 域名失败")
            
        domain = random.choice(domains)
        username = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        password = "".join(random.choices(string.ascii_letters + string.digits, k=12))
        email_address = f"{username}@{domain}"
        
        # 1. 创建账号
        account_data = {
            "address": email_address,
            "password": password,
            "expiresIn": 86400 # 24小时过期
        }
        res_create = self._req("POST", "/accounts", json_data=account_data)
        if not res_create or "id" not in res_create:
            raise Exception("注册 DuckMail 账号失败")
            
        # 2. 获取 Token
        token_data = {
            "address": email_address,
            "password": password
        }
        res_token = self._req("POST", "/token", json_data=token_data)
        if not res_token or "token" not in res_token:
            raise Exception("获取 DuckMail Token 失败")
            
        self.current_email = email_address
        self.current_password = password
        self.token = res_token["token"]
        print(f"  ✅ 成功创建邮箱账号: {self.current_email} (密码: {self.current_password})")
        return self.current_email, self.token

    def fetch_emails(self, email=None):
        """
        获取邮件列表
        """
        if not self.token:
            return []
            
        # GET /messages
        data = self._req("GET", "/messages")
        if not data:
            return []
            
        result_list = []
        messages = data.get("hydra:member", [])
        
        for m in messages:
            # 需要再获取一次详情才能拿到正文，但为了优化速度，如果只需要标题/简介可以暂时只用列表数据
            # 如果需要正文提取验证码，最好获取详情
            msg_id = m.get("id")
            detail = self._req("GET", f"/messages/{msg_id}")
            if detail:
                text_content = detail.get("text", "")
                html_content = ""
                if detail.get("html") and len(detail["html"]) > 0:
                    html_content = detail["html"][0]
                    
                result_list.append({
                    "emailId": msg_id,
                    "subject": detail.get("subject", ""),
                    "intro": text_content[:100], 
                    "content": text_content or html_content,
                    "text": text_content or html_content
                })
            
        return result_list

    def extract_verification_code(self, content):
        """从邮件内容提取6位验证码"""
        if not content:
            return None

        patterns = [
            r"Verification code:?\s*(\d{6})",
            r"code is\s*(\d{6})",
            r"代码为[:：]?\s*(\d{6})",
            r"验证码[:：]?\s*(\d{6})",
            r">\s*(\d{6})\s*<",
            r"(?<![#&])\b(\d{6})\b",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for code in matches:
                if code == "177010":  # 已知误判
                    continue
                return code
        return None

    def wait_for_verification_code(self, email, timeout=60, exclude_codes=None):
        """
        等待验证邮件并提取验证码
        """
        if not self.token:
            print("  [!] 未设置 DuckMail Token")
            return None
            
        if exclude_codes is None:
            exclude_codes = set()
        
        all_exclude_codes = exclude_codes | self._used_codes
        print(f"  ⏳ 等待验证码 (最大 {timeout}s)...")
        
        start = time.time()
        
        while time.time() - start < timeout:
            messages = self.fetch_emails(email)
            for msg in messages:
                sb = msg.get("subject", "")
                intro = msg.get("intro", "")
                content = msg.get("content", "")
                
                # 提取验证码 (不仅限于标题中带相关关键字，全面提取)
                code = self.extract_verification_code(content) or self.extract_verification_code(sb)
                
                if code and code not in all_exclude_codes:
                    print(f"  ✅ 验证码: {code}")
                    self._used_codes.add(code)
                    return code
            
            elapsed = time.time() - start
            if elapsed < 10:
                time.sleep(3)
            else:
                time.sleep(5)
                
        print("  ⏰ 等待验证码超时")
        return None

def init_duckmail_client(config):
    """
    初始化 DuckMail 客户端
    """
    proxy = config.get("proxy", "")
    client = DuckMailClient(proxy=proxy)
    
    print(f"📧 正在初始化 DuckMail 客户端...")
    try:
        print(f"✅ DuckMail 客户端准备就绪")
        return client
    except Exception as e:
        print(f"❌ DuckMail 初始化失败: {e}")
        sys.exit(1)
