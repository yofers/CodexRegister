"""
Mail.tm 临时邮箱客户端模块 (兼容 SkymailClient 接口)
"""

import sys
import time
import random
import string
import re
from curl_cffi.requests import Session

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def rstr(n=10): 
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

class MailTmClient:
    """Mail.tm 邮箱服务客户端，适配了原先 SkymailClient 的接口"""

    def __init__(self, proxy=None):
        self.proxy = proxy
        self.api_base = "https://api.mail.tm"
        self.mail_pw = "at41rvxgptye"  # 固定密码用于创建邮箱
        self.current_domain = None
        self.current_token = None
        self.current_email = None
        self._used_codes = set()
        
        self._init_domain()

    def _mreq(self, mt, pt, js=None, tk=None):
        hdrs = {
            "content-type": "application/json",
            "accept": "application/json",
            "user-agent": UA,
            "pragma": "no-cache"
        }
        if tk: 
            hdrs["authorization"] = f"Bearer {tk}"
        try:
            proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
            with Session(proxies=proxies) as s:
                return s.request(mt, f"{self.api_base}{pt}", json=js, headers=hdrs, timeout=20)
        except: 
            return None

    def _init_domain(self):
        """动态获取当前可用的邮箱域名"""
        domain_res = self._mreq("GET", "/domains")
        if not domain_res or domain_res.status_code != 200:
            print("  [!] 无法获取可用邮箱域名")
            return
        
        try:
            js_data = domain_res.json()
            if isinstance(js_data, list):
                domains_data = js_data
            elif isinstance(js_data, dict):
                domains_data = js_data.get("hydra:member", js_data.get("hydra:collection", []))
            else:
                domains_data = []

            if not domains_data:
                print("  [!] 域名列表为空")
                return
                
            self.current_domain = domains_data[0].get("domain")
        except Exception as e:
            print(f"  [!] 解析域名失败: {e}")

    def create_temp_email(self):
        """
        创建 Mail.tm 临时邮箱 (兼容原 create_temp_email 接口)
        
        Returns:
            tuple: (email, token)
        """
        if not self.current_domain:
            self._init_domain()
            if not self.current_domain:
                raise Exception("无法获取 mail.tm 域名")

        email = f"{rstr(10)}@{self.current_domain}"
        
        # 注册 mail.tm 邮箱
        r = self._mreq("POST", "/accounts", {"address": email, "password": self.mail_pw})
        if not r or r.status_code not in [200, 201]: 
            raise Exception(f"Mail.tm 邮箱注册被拒: {r.text if r else '无响应'}")
            
        # 获取 mail.tm 的 Token
        r = self._mreq("POST", "/token", {"address": email, "password": self.mail_pw})
        if not r or r.status_code != 200: 
            raise Exception("获取 Mail.tm 邮箱 Token 失败")
            
        self.current_token = r.json().get("token")
        self.current_email = email
        return email, self.current_token

    def fetch_emails(self, email):
        """
        从 Mail.tm 获取邮件列表 (兼容原 fetch_emails 接口)
        
        Args:
            email: 邮箱地址 (实际上这里使用 current_token 即可，不用 email 字段)
            
        Returns:
            list: 邮件列表 (包含 content 字段供后续提取)
        """
        if not self.current_token:
            return []
            
        r = self._mreq("GET", "/messages", tk=self.current_token)
        if r and r.status_code == 200:
            try: 
                dat = r.json()
            except: 
                return []
                
            msgs = dat.get("hydra:member", []) if isinstance(dat, dict) else dat
            if not isinstance(msgs, list): msgs = []
            
            result_list = []
            for m in msgs:
                if not isinstance(m, dict): continue
                # 获取邮件详情内容
                rb = self._mreq("GET", f"/messages/{m.get('id')}", tk=self.current_token)
                if rb and rb.status_code == 200:
                    msg_detail = rb.json()
                    result_list.append({
                        "emailId": m.get("id"),
                        "subject": m.get("subject", ""),
                        "intro": m.get("intro", ""),
                        "content": msg_detail.get("text", "") or m.get("intro", ""),
                        "text": msg_detail.get("text", "")
                    })
            return result_list
        return []

    def extract_verification_code(self, content):
        """从邮件内容提取6位验证码 (兼容原 extract_verification_code)"""
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
        等待验证邮件并提取验证码 (兼容原 wait_for_verification_code)
        
        Args:
            email: 邮箱地址
            timeout: 超时时间（秒）
            exclude_codes: 要排除的验证码集合（避免重复使用）
            
        Returns:
            str: 验证码，失败返回 None
        """
        if exclude_codes is None:
            exclude_codes = set()
        
        all_exclude_codes = exclude_codes | self._used_codes
        
        print(f"  ⏳ 等待验证码 (最大 {timeout}s)...")
        
        start = time.time()
        last_email_ids = set()
        
        # 为了不频繁拉取详情，可以先拉取列表检查 subject/intro，如果是目标邮件再拉取详情
        while time.time() - start < timeout:
            r = self._mreq("GET", "/messages", tk=self.current_token)
            if r and r.status_code == 200:
                try:
                    dat = r.json()
                    msgs = dat.get("hydra:member", []) if isinstance(dat, dict) else dat
                    if not isinstance(msgs, list): msgs = []
                    
                    for m in msgs:
                        if not isinstance(m, dict): continue
                        email_id = m.get("id")
                        if not email_id or email_id in last_email_ids:
                            continue
                            
                        sb = m.get("subject", "")
                        intro = m.get("intro", "")
                        if "OpenAI" in sb or "ChatGPT" in sb or "code" in intro:
                            # 拉取详情
                            rb = self._mreq("GET", f"/messages/{email_id}", tk=self.current_token)
                            if rb and rb.status_code == 200:
                                last_email_ids.add(email_id)
                                content = rb.json().get("text", "")
                                code = self.extract_verification_code(content) or self.extract_verification_code(sb)
                                
                                if code and code not in all_exclude_codes:
                                    print(f"  ✅ 验证码: {code}")
                                    self._used_codes.add(code)
                                    return code
                except Exception as e:
                    pass
            
            elapsed = time.time() - start
            if elapsed < 10:
                time.sleep(2)
            else:
                time.sleep(5)
                
        print("  ⏰ 等待验证码超时")
        return None

def init_mail_tm_client(config):
    """
    初始化 Mail.tm 客户端
    
    Args:
        config: 配置字典
        
    Returns:
        MailTmClient: 初始化好的客户端实例
    """
    proxy = config.get("proxy", "")
    client = MailTmClient(proxy=proxy)
    
    print(f"📧 正在初始化 Mail.tm 客户端...")
    if not client.current_domain:
        print("❌ 无法获取 Mail.tm 域名，请检查网络")
        sys.exit(1)
        
    print(f"✅ 可用域名: {client.current_domain}")
    return client
