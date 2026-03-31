# CodexRegister

ChatGPT 账号批量注册工具，支持自动收取验证码、完成 OAuth 登录，并将成功获取的 Token 保存为 JSON 文件。

项目当前提供单进程串行和多线程并发两种运行方式，支持多种邮箱来源：

- `custom`：手动输入自定义邮箱和验证码
- `duckmail`：DuckMail 临时邮箱
- `mailtm`：Mail.tm 临时邮箱
- `guerrilla`：Guerrilla Mail 临时邮箱

## 功能概览

- 自动生成随机邮箱密码、姓名和生日信息
- 自动执行 ChatGPT 注册流程
- 注册成功后继续执行 OAuth 流程
- 保存 `access_token`、`refresh_token`、`id_token` 到本地 JSON
- 可选上传 token JSON 到外部接口
- 支持代理
- 支持有限任务和无限循环任务
- 支持并发注册

## 项目结构

```text
CodexRegister/
├── app_config.py          # 主配置文件，建议优先修改这里
├── main.py                # 程序入口
├── README.md
└── lib/
    ├── chatgpt_client.py  # 注册流程
    ├── oauth_client.py    # OAuth 登录与 token 获取
    ├── token_manager.py   # token 保存与上传
    ├── config.py          # 配置加载逻辑
    ├── utils.py           # 通用工具函数
    └── mail/              # 各种邮箱客户端
```

## 环境要求

- Python 3
- 可访问目标服务的网络环境
- 如有需要，可用 HTTP/HTTPS 代理

当前仓库没有附带 `requirements.txt`，至少需要安装以下依赖：

```bash
pip install curl_cffi requests
```

`curl_cffi` 是核心依赖。注册流程、邮箱客户端和部分上传逻辑都依赖它模拟浏览器请求。

## 配置

推荐直接修改 [`app_config.py`](/Users/data/www/CodexRegister/app_config.py)。

默认配置如下：

```python
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
```

### 配置优先级

程序按以下顺序加载配置，后者覆盖前者：

`默认值 < config.json < app_config.py < 环境变量`

### 配置项说明

| 配置项 | 说明 |
| --- | --- |
| `MAIL_PROVIDER` | 邮箱来源，支持 `custom`、`duckmail`、`mailtm`、`guerrilla` |
| `PROXY` | 代理地址，例如 `http://127.0.0.1:7890` |
| `OUTPUT_FILE` | 成功注册后的账号输出文件 |
| `TOKEN_JSON_DIR` | Token JSON 保存目录，可填相对路径或绝对路径 |
| `UPLOAD_API_URL` | 可选，上传 token JSON 的接口地址 |
| `UPLOAD_API_TOKEN` | 可选，上传接口 Bearer Token |

### 关于 `TOKEN_JSON_DIR`

`TOKEN_JSON_DIR` 支持两种写法：

- 相对路径：相对于项目根目录，例如 `tokens`
- 绝对路径：例如 `/Users/mahiro/tokens`

示例：

```python
TOKEN_JSON_DIR = "/Users/mahiro/tokens"
```

## 运行方式

### 1. 有限数量注册

注册 5 个账号，使用 2 个线程：

```bash
python3 main.py -n 5 -w 2
```

### 2. 单线程无限运行

不指定 `-n` 时，程序会持续运行：

```bash
python3 main.py
```

### 3. 多线程无限运行

```bash
python3 main.py -w 3
```

### 命令行参数

| 参数 | 说明 |
| --- | --- |
| `-n`, `--num` | 注册账号数量；不传则无限运行 |
| `-w`, `--workers` | 并发线程数，默认 `1` |

## 邮箱来源说明

### `custom`

适合你自己控制邮箱收件的场景。运行时程序会：

- 提示你输入邮箱地址
- 在需要验证码时提示你手动输入 6 位验证码

这是最容易调试的模式。

### `duckmail`

自动创建 DuckMail 临时邮箱并轮询邮件。

### `mailtm`

自动创建 Mail.tm 临时邮箱并轮询邮件。

### `guerrilla`

自动创建 Guerrilla Mail 临时邮箱并轮询邮件。

## 输出结果

程序成功后会产生两类本地输出。

### 1. 账号结果文件

默认写入：

```text
registered_accounts.txt
```

每行格式：

```text
邮箱----密码----oauth=ok
```

### 2. Token JSON 文件

默认保存到项目根目录下的 `tokens/` 目录。

文件名格式：

```text
{email}.json
```

JSON 中包含以下关键字段：

- `email`
- `account_id`
- `access_token`
- `refresh_token`
- `id_token`
- `expired`
- `last_refresh`

## 运行示例

```bash
python3 main.py -n 2 -w 1
```

启动后会打印当前配置，例如：

- 注册数量
- 并发数
- 输出文件
- 邮箱来源
- Token 目录

任务结束后会输出统计信息：

- 成功数量
- 失败数量
- 总计
- 总耗时
- 平均每账号耗时

## 常见问题

### 1. Token 保存到哪里

默认保存到项目根目录下的 `tokens/`。

如果你把 `TOKEN_JSON_DIR` 设置成绝对路径，例如：

```python
TOKEN_JSON_DIR = "/Users/mahiro/tokens"
```

那就会直接保存到该目录。

### 2. 代理怎么设置

在 [`app_config.py`](/Users/data/www/CodexRegister/app_config.py) 中设置：

```python
PROXY = "http://127.0.0.1:7890"
```

### 3. 为什么推荐先用 `custom`

因为 `custom` 模式最容易确认问题出在哪一层：

- 邮箱是否可用
- 验证码是否收到
- 网络或代理是否异常
- OAuth 是否拿到 token

### 4. 如果出现 TLS / SSL 错误

程序内部已经对部分 TLS/SSL 异常做了重试，但如果持续失败，通常需要优先检查：

- 网络连通性
- 代理配置
- 本地出口 IP 环境

## 说明

本项目的核心流程分为两步：

1. 注册账号
2. 复用注册阶段的会话继续执行 OAuth，获取 token

OAuth 成功后，程序会立即保存 token JSON；如果同时配置了 `UPLOAD_API_URL`，还会继续将该 JSON 上传到指定接口。

## 免责声明

请在遵守目标平台服务条款、当地法律法规和你自身授权边界的前提下使用本项目。你需要自行承担由运行、修改或部署该项目带来的风险。
