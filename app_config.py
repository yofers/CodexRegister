"""
项目配置文件

优先修改这个文件，不需要改 lib/config.py。
如需临时覆盖，也可以使用同名环境变量。
"""

# 邮箱来源，可选: custom / duckmail / mailtm / guerrilla
MAIL_PROVIDER = "custom"

# 代理地址，例如 "http://127.0.0.1:7890"
PROXY = ""

# 注册结果输出文件
OUTPUT_FILE = "registered_accounts.txt"

# token JSON 保存目录
TOKEN_JSON_DIR = "tokens"

# 可选：上传 token JSON 的接口地址
UPLOAD_API_URL = ""

# 可选：上传接口 Bearer Token
UPLOAD_API_TOKEN = ""
