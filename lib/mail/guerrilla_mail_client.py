"""
Guerrilla Mail 临时邮箱客户端模块 (兼容 SkymailClient 接口)
参考: https://www.guerrillamail.com/GuerrillaMailAPI.html
"""

import sys
import time
import re
from curl_cffi.requests import Session

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

class GuerrillaMailClient:
    """Guerrilla Mail 邮箱服务客户端，适配了原先 SkymailClient 的接口"""

    def __init__(self, proxy=None):
        self.proxy = proxy
        self.api_base = "http://api.guerrillamail.com/ajax.php"
        self.current_email = None
        self.session_id = None
        self._used_codes = set()
        
        # 建立持久会话以保持 PHPSESSID
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
        self.session = Session(proxies=proxies, impersonate="chrome120")
        self.session.headers.update({
            "User-Agent": UA,
            "Accept": "application/json, text/javascript, */*; q=0.01"
        })

    def _req(self, function_name, params=None):
        """发送 API 请求"""
        if params is None:
            params = {}
        
        params['f'] = function_name
        params['ip'] = '127.0.0.1'  # API 要求，可以写死或用真实的
        params['agent'] = 'Mozilla_foo_bar' # API 要求
        
        try:
            r = self.session.get(self.api_base, params=params, timeout=20)
            if r.status_code == 200:
                return r.json()
            return None
        except Exception as e:
            print(f"  [!] Guerrilla Mail API 请求异常: {e}")
            return None

    def create_temp_email(self):
        """
        获取/创建 Guerrilla Mail 临时邮箱 (兼容原 create_temp_email 接口)
        
        Returns:
            tuple: (email, token/session_id)
        """
        data = self._req("get_email_address")
        if not data or "email_addr" not in data:
            raise Exception("获取 Guerrilla Mail 邮箱失败")
            
        self.current_email = data["email_addr"]
        self.session_id = data.get("sid_token", "")
        return self.current_email, self.session_id

    def fetch_emails(self, email=None):
        """
        获取邮件列表 (兼容原 fetch_emails 接口)
        """
        # 注意：Guerrilla API 使用 get_email_list 来获取列表
        # 参数 offset: seq 序号，获取比这个序号更新的邮件。设为 0 获取全部
        data = self._req("get_email_list", {"offset": 0})
        if not data or "list" not in data:
            return []
            
        result_list = []
        for m in data["list"]:
            # 过滤掉默认的欢迎邮件 (通常 mail_id=1 或者是特定的发件人)
            if m.get("mail_from") == "no-reply@guerrillamail.com":
                continue
                
            # 拉取详情
            detail = self._req("fetch_email", {"email_id": m.get("mail_id")})
            if detail:
                result_list.append({
                    "emailId": m.get("mail_id"),
                    "subject": detail.get("mail_subject", ""),
                    "intro": detail.get("mail_excerpt", ""),
                    "content": detail.get("mail_body", ""),
                    "text": detail.get("mail_body", "")
                })
        return result_list

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
        """
        if exclude_codes is None:
            exclude_codes = set()
        
        all_exclude_codes = exclude_codes | self._used_codes
        print(f"  ⏳ 等待验证码 (最大 {timeout}s)...")
        
        start = time.time()
        last_seq = 0
        
        while time.time() - start < timeout:
            # 使用 check_email 只拉取新邮件
            data = self._req("check_email", {"seq": last_seq})
            if data and "list" in data and len(data["list"]) > 0:
                for m in data["list"]:
                    mail_id = m.get("mail_id")
                    
                    # 避免抓取欢迎邮件
                    if m.get("mail_from") == "no-reply@guerrillamail.com":
                        continue
                        
                    sb = m.get("mail_subject", "")
                    intro = m.get("mail_excerpt", "")
                    
                    if "OpenAI" in sb or "ChatGPT" in sb or "code" in intro:
                        detail = self._req("fetch_email", {"email_id": mail_id})
                        if detail:
                            content = detail.get("mail_body", "")
                            code = self.extract_verification_code(content) or self.extract_verification_code(sb)
                            
                            if code and code not in all_exclude_codes:
                                print(f"  ✅ 验证码: {code}")
                                self._used_codes.add(code)
                                return code
                
                # 更新 seq，以便下一次只获取更新的邮件
                last_seq = data["list"][0].get("mail_id", last_seq)
            
            elapsed = time.time() - start
            if elapsed < 10:
                time.sleep(5) # Guerrilla Mail 建议不要过于频繁
            else:
                time.sleep(10)
                
        print("  ⏰ 等待验证码超时")
        return None

def init_guerrilla_mail_client(config):
    """
    初始化 Guerrilla Mail 客户端
    """
    proxy = config.get("proxy", "")
    client = GuerrillaMailClient(proxy=proxy)
    
    print(f"📧 正在初始化 Guerrilla Mail 客户端...")
    try:
        # 预先获取一次，验证 API 是否连通
        client.create_temp_email()
        print(f"✅ Guerrilla Mail 初始化成功")
        return client
    except Exception as e:
        print(f"❌ Guerrilla Mail 初始化失败: {e}")
        sys.exit(1)
