"""
ChatGPT 批量自动注册工具 v3.0 - 混合模块化版本
使用 Mail.tm 临时邮箱，并发自动注册 ChatGPT 账号
"""

import sys
import time
import threading
import argparse
import warnings
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait

# 禁用 SSL 警告
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# 导入自定义模块
from lib.config import load_config, as_bool
from lib.mail.factory import init_mail_client
from lib.token_manager import TokenManager
from lib.chatgpt_client import ChatGPTClient
from lib.oauth_client import OAuthClient
from lib.utils import generate_random_password, generate_random_name, generate_random_birthday


def register_one_account(idx, total, mail_client, token_manager, oauth_client, config, max_retries=3):
    """
    注册单个账号的完整流程（带重试机制）
    
    Args:
        idx: 账号序号
        total: 总账号数
        mail_client: 临时邮箱客户端
        token_manager: Token 管理器
        oauth_client: OAuth 客户端
        config: 配置字典
        max_retries: 最大重试次数
        
    Returns:
        tuple: (success, email, password, message)
    """
    tag = f"[{idx}]" if total is None else f"[{idx}/{total}]"
    
    for attempt in range(max_retries):
        if attempt > 0:
            print(f"\n{tag} 重试注册 (尝试 {attempt + 1}/{max_retries})...")
            time.sleep(1)  # 重试前等待
        else:
            print(f"\n{tag} 开始注册...")
        
        try:
            # 1. 创建临时邮箱
            print(f"{tag} 创建临时邮箱...")
            email, mail_token = mail_client.create_temp_email()
            print(f"{tag} 邮箱: {email}")
            
            # 2. 生成随机密码和个人信息
            password = generate_random_password()
            first_name, last_name = generate_random_name()
            birthdate = generate_random_birthday()
            
            print(f"{tag} 密码: {password}")
            print(f"{tag} 姓名: {first_name} {last_name}")
            
            # 3. 创建 ChatGPT 客户端
            proxy = config.get("proxy", "")
            chatgpt_client = ChatGPTClient(proxy=proxy, verbose=True)
            
            # 4. 执行注册流程
            print(f"{tag} 开始注册流程...")
            success, msg = chatgpt_client.register_complete_flow(
                email, password, first_name, last_name, birthdate, mail_client
            )
            
            if not success:
                # 检查是否是 TLS 错误，如果是则重试
                is_tls_error = "TLS" in msg or "SSL" in msg or "curl: (35)" in msg
                if is_tls_error and attempt < max_retries - 1:
                    print(f"{tag} ⚠️ TLS 错误，准备重试: {msg}")
                    continue
                else:
                    print(f"{tag} ❌ 注册失败: {msg}")
                    return False, email, password, msg
            
            print(f"{tag} ✅ 注册成功")
            
            # 5. OAuth 登录获取 Token（固定启用且必需成功）
            print(f"{tag} 开始 OAuth 登录...")
            
            # 直接使用 ChatGPT 客户端的 session 进行 OAuth（关键！）
            # 不创建新的 OAuthClient，而是复用注册时的 session
            oauth_client_reuse = OAuthClient(config, proxy=config.get("proxy", ""), verbose=True)
            # 在初始化后立即替换 session，保留注册时的所有 cookies
            oauth_client_reuse.session = chatgpt_client.session
            
            tokens = oauth_client_reuse.login_and_get_tokens(
                email, password,
                chatgpt_client.device_id,
                chatgpt_client.ua,
                chatgpt_client.sec_ch_ua,
                chatgpt_client.impersonate,
                mail_client
            )
            
            if tokens and tokens.get("access_token"):
                print(f"{tag} ✅ OAuth 成功")
                token_manager.save_tokens(email, tokens)
                
                # 保存账号信息
                output_file = config.get("output_file", "registered_accounts.txt")
                with threading.Lock():
                    with open(output_file, "a", encoding="utf-8") as f:
                        f.write(f"{email}----{password}----oauth=ok\n")
                
                return True, email, password, "注册成功 + OAuth 成功"

            print(f"{tag} ⚠️ OAuth 失败")
            if attempt < max_retries - 1:
                print(f"{tag} OAuth 失败，准备重试整个流程...")
                continue
            return False, email, password, "OAuth 失败（必需）"
            
        except Exception as e:
            error_msg = str(e)
            is_tls_error = "TLS" in error_msg or "SSL" in error_msg or "curl: (35)" in error_msg
            
            if is_tls_error and attempt < max_retries - 1:
                print(f"{tag} ⚠️ 异常 (TLS 错误)，准备重试: {error_msg[:100]}")
                continue
            else:
                print(f"{tag} ❌ 注册失败: {e}")
                import traceback
                traceback.print_exc()
                return False, "", "", str(e)
    
    # 所有重试都失败
    return False, "", "", "重试次数已用尽"


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='ChatGPT 批量自动注册工具 v2.0')
    parser.add_argument('-n', '--num', type=int, default=None, help='注册账号数量（默认: 不限）')
    parser.add_argument('-w', '--workers', type=int, default=1, help='并发线程数（默认: 1）')
    args = parser.parse_args()
    
    print("=" * 60)
    print("  ChatGPT 批量自动注册工具 v3.0 (混合模块化版本)")
    print("  使用 Mail.tm 临时邮箱")
    print("=" * 60)
    
    # 加载配置
    config = load_config()
    
    # 命令行参数覆盖配置文件
    total_accounts = args.num
    max_workers = args.workers
    # 初始化临时邮箱客户端
    mail_client = init_mail_client(config)
    
    # 初始化 Token 管理器
    token_manager = TokenManager(config)
    
    # 初始化 OAuth 客户端
    oauth_client = OAuthClient(config, proxy=config.get("proxy", ""), verbose=True)
    
    # 获取配置参数
    output_file = config.get("output_file", "registered_accounts.txt")
    print(f"\n配置信息:")
    print(f"  注册数量: {total_accounts if total_accounts is not None else '无限'}")
    print(f"  并发数: {max_workers}")
    print(f"  输出文件: {output_file}")
    print(f"  邮箱来源: {mail_client.api_base}")
    print(f"  Token 目录: {token_manager.token_dir}")
    print(f"  启用 OAuth: True")
    print()
    
    # 批量注册
    success_count = 0
    failed_count = 0
    start_time = time.time()
    
    if max_workers == 1 and total_accounts is not None:
        # 串行执行
        for i in range(1, total_accounts + 1):
            success, email, password, msg = register_one_account(
                i, total_accounts, mail_client, token_manager, oauth_client, config
            )
            if success:
                success_count += 1
            else:
                failed_count += 1
    elif max_workers == 1:
        # 无限串行执行
        i = 1
        while True:
            success, email, password, msg = register_one_account(
                i, None, mail_client, token_manager, oauth_client, config
            )
            if success:
                success_count += 1
            else:
                failed_count += 1
            i += 1
    elif total_accounts is not None:
        # 并发执行
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for i in range(1, total_accounts + 1):
                future = executor.submit(
                    register_one_account,
                    i, total_accounts, mail_client, token_manager, oauth_client, config
                )
                futures.append(future)
            
            for future in as_completed(futures):
                try:
                    success, email, password, msg = future.result()
                    if success:
                        success_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    print(f"❌ 任务异常: {e}")
                    failed_count += 1
    else:
        # 无限并发执行
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            next_idx = 1
            futures = {
                executor.submit(
                    register_one_account,
                    next_idx, None, mail_client, token_manager, oauth_client, config
                )
                for next_idx in range(1, max_workers + 1)
            }
            next_idx = max_workers + 1

            while True:
                done, pending = wait(futures, return_when=FIRST_COMPLETED)
                futures = set(pending)

                for future in done:
                    try:
                        success, email, password, msg = future.result()
                        if success:
                            success_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        print(f"❌ 任务异常: {e}")
                        failed_count += 1

                    futures.add(
                        executor.submit(
                            register_one_account,
                            next_idx, None, mail_client, token_manager, oauth_client, config
                        )
                    )
                    next_idx += 1
    
    end_time = time.time()
    total_time = end_time - start_time
    processed_count = success_count + failed_count
    
    # 输出统计
    print("\n" + "=" * 60)
    print(f"注册完成！")
    print(f"  成功: {success_count}")
    print(f"  失败: {failed_count}")
    print(f"  总计: {total_accounts if total_accounts is not None else processed_count}")
    print(f"  总耗时: {total_time:.1f}s")
    if processed_count > 0:
        print(f"  平均耗时: {total_time/processed_count:.1f}s/账号")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
