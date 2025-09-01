# 导入必要的库
import httpx  # 用于发送异步 HTTP 请求，与 Keycloak 通信
import secrets  # 用于生成加密安全的随机字符串，用于 state 和 code_verifier
import hashlib  # 用于计算哈希值，PKCE 流程中需要
import base64  # 用于 Base64 编码，PKCE 流程中需要
from fastapi import Request, HTTPException, Depends  # FastAPI 框架的核心组件
from jwt import PyJWKClient  # 用于从 JWKS URI 获取验证 JWT 签名的公钥
import os  # 用于访问环境变量
from dotenv import load_dotenv  # 用于从 .env 文件加载环境变量
from typing import List, Union # 导入类型提示，增强代码可读性

# 加载 .env 文件中的环境变量
load_dotenv() 

# --- Keycloak OIDC 配置 ---
# 从环境变量中获取 Keycloak 的连接信息
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL")  # Keycloak 服务器的基础 URL
REALM_NAME = os.getenv("REALM_NAME")      # 使用的 Realm 名称
CLIENT_ID = os.getenv("CLIENT_ID")        # 在 Keycloak 中配置的客户端 ID
CLIENT_SECRET = os.getenv("CLIENT_SECRET")# 在 Keycloak 中配置的客户端密钥

# 检查所有必要的环境变量是否都已设置
if not all([KEYCLOAK_URL, REALM_NAME, CLIENT_ID, CLIENT_SECRET]):
    # 如果有任何一个缺失，则抛出异常，阻止程序启动
    raise ValueError("一个或多个 Keycloak 环境变量未设置。请检查 .env 文件。")

# --- OIDC 配置自动发现 ---
try:
    # 构建 OIDC 的 "Well-Known" 配置 URL，这是一个标准化的 OIDC 功能
    OIDC_CONFIG_URL = f"{KEYCLOAK_URL}/realms/{REALM_NAME}/.well-known/openid-configuration"
    # 使用 httpx 发送同步 GET 请求获取 OIDC 配置
    response = httpx.get(OIDC_CONFIG_URL)
    # 如果请求失败（例如，网络错误或 Keycloak 关闭），则抛出 HTTP 错误
    response.raise_for_status()
    # 将返回的 JSON 数据解析为 Python 字典
    OIDC_CONFIG = response.json()
    
    # 从 OIDC 配置中提取关键的端点 URL
    AUTHORIZATION_ENDPOINT = OIDC_CONFIG["authorization_endpoint"]  # 授权端点，用于启动登录流程
    TOKEN_ENDPOINT = OIDC_CONFIG["token_endpoint"]                  # 令牌端点，用于交换授权码获取令牌
    JWKS_URI = OIDC_CONFIG["jwks_uri"]                              # JWKS 端点，用于获取验证签名的公钥
    LOGOUT_ENDPOINT = OIDC_CONFIG.get("end_session_endpoint")       # 登出端点，用于单点登出
    REVOCATION_ENDPOINT = OIDC_CONFIG.get("revocation_endpoint")    # 令牌撤销端点

# 捕获在获取和解析 OIDC 配置过程中可能发生的错误
except (httpx.RequestError, KeyError) as e:
    # 打印致命错误信息并退出程序，因为没有 OIDC 配置，认证无法工作
    print(f"致命错误: 无法从 {OIDC_CONFIG_URL} 获取 OIDC 配置。错误: {e}")
    exit(1)

# 初始化 PyJWKClient，它会自动从 JWKS_URI 下载和缓存用于验证 JWT 的公钥
jwks_client = PyJWKClient(JWKS_URI)

# --- PKCE (Proof Key for Code Exchange) 辅助函数 ---
def generate_pkce_codes():
    """
    生成 PKCE 所需的 code_verifier 和 code_challenge。
    这是 OAuth 2.0 的一个安全增强功能，可以防止授权码被截获后盗用。
    """
    # 1. 生成一个足够长的加密安全的随机字符串作为 code_verifier
    code_verifier = secrets.token_urlsafe(64)
    # 2. 使用 SHA256 对 code_verifier 进行哈希计算
    hashed = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    # 3. 对哈希结果进行 URL-safe Base64 编码，并移除末尾的 '='，生成 code_challenge
    code_challenge = base64.urlsafe_b64encode(hashed).rstrip(b"=").decode("utf-8")
    # 返回 verifier 和 challenge，verifier 需要在后续步骤中发送给令牌端点
    return code_verifier, code_challenge

# --- FastAPI 依赖项 (Dependencies) ---

async def get_current_user(request: Request):
    """
    一个简单的依赖项，用于从会话中获取当前用户信息。
    如果用户未登录，返回 None。
    """
    return request.session.get("user")

async def require_authentication(request: Request, user: dict = Depends(get_current_user)):
    """
    一个依赖项，用于保护需要登录才能访问的路由。
    如果用户未登录，它会重定向到登录页面。
    """
    if not user:
        # 如果会话中没有用户信息，表示用户未登录
        # 将用户原本想访问的 URL 存入会话，以便登录后可以重定向回去
        request.session["redirect_after_login"] = str(request.url)
        # 抛出 307 临时重定向异常，指示浏览器重定向到 /login 页面
        # FastAPI 会将这个异常转换为一个 HTTP 重定向响应
        raise HTTPException(status_code=307, detail="Not authenticated", headers={"Location": "/login"})
    # 如果用户已登录，则返回用户信息
    return user

def require_role(allowed_roles: Union[str, List[str]]):
    """
    【已修改】一个依赖项工厂函数，用于创建检查用户角色的依赖项。
    它现在可以接受单个角色字符串或一个角色列表。
    """
    # 如果传入的是单个角色字符串，将其转换为单元素的列表，以统一处理
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    async def role_checker(user: dict = Depends(require_authentication)):
        """
        这是实际的依赖项函数，它会检查用户的角色。
        """
        # 获取用户拥有的角色列表，如果用户没有角色信息，则返回空列表
        user_roles = user.get("roles", [])
        # 检查用户角色列表与要求的角色列表是否有任何交集
        if not any(role in user_roles for role in allowed_roles):
            # 如果没有任何一个要求的角色存在于用户的角色列表中，则授权失败
            # 打印详细的日志，方便问题排查
            print(f"授权失败: 用户 '{user.get('username')}' (角色: {user_roles}) 尝试访问需要 {allowed_roles} 角色的资源。")
            # 抛出 403 Forbidden 错误，告知用户权限不足
            raise HTTPException(status_code=403, detail=f"禁止访问: 你需要拥有 {allowed_roles} 中的至少一个角色。")
        
        # 如果权限检查通过，打印成功日志
        print(f"授权成功: 用户 '{user.get('username')}' 访问了需要 {allowed_roles} 角色的资源。")
        # 返回用户信息，以便路由函数可以继续使用
        return user
    
    # 返回内部定义的 role_checker 函数，FastAPI 会将其作为一个依赖项使用
    return role_checker

async def revoke_token(refresh_token: str):
    """
    在 Keycloak 中撤销用户的 refresh_token。
    这会立即使该 refresh_token 失效，从而增强安全性。
    """
    # 如果 OIDC 配置中没有令牌撤销端点，则直接返回
    if not REVOCATION_ENDPOINT:
        print("警告: OIDC 提供商没有配置 revocation_endpoint，无法撤销令牌。")
        return
        
    # 准备要发送到撤销端点的数据
    payload = {
        "token": refresh_token,
        "token_type_hint": "refresh_token"  # 告知服务器我们正在撤销的是一个 refresh_token
    }
    # 客户端认证信息，因为这是一个后端操作，需要客户端 ID 和密钥
    auth = (CLIENT_ID, CLIENT_SECRET)
    
    # 使用 httpx 异步发送 POST 请求
    async with httpx.AsyncClient() as client:
        try:
            # 发送请求到 Keycloak 的令牌撤销端点
            response = await client.post(REVOCATION_ENDPOINT, data=payload, auth=auth)
            # 检查响应状态码，如果不成功则记录日志
            if response.status_code != 200:
                print(f"警告: 撤销令牌失败，状态码: {response.status_code}, 响应: {response.text}")
        except httpx.RequestError as e:
            # 捕获并记录网络请求相关的错误
            print(f"错误: 撤销令牌时发生网络错误: {e}")
