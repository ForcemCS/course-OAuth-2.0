# 导入 FastAPI 和相关模块
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware # 用于处理服务器端会话
import os
from dotenv import load_dotenv # 用于从 .env 文件加载环境变量
import httpx # 用于发送异步 HTTP 请求
import jwt # 用于解码和验证 JWT (JSON Web Tokens)
import secrets # 用于生成安全的随机字符串 (用于 state)

# 从 security.py 模块导入自定义的安全相关函数和常量
from security import (
    generate_pkce_codes,      # 生成 PKCE code_verifier 和 code_challenge
    AUTHORIZATION_ENDPOINT,   # Keycloak 授权端点 URL
    TOKEN_ENDPOINT,           # Keycloak 令牌端点 URL
    LOGOUT_ENDPOINT,          # Keycloak 登出端点 URL
    CLIENT_ID,                # OIDC 客户端 ID
    CLIENT_SECRET,            # OIDC 客户端密钥
    OIDC_CONFIG,              # 从 Keycloak 获取的 OIDC 配置
    jwks_client,              # 用于验证 JWT 签名的 JWK 客户端
    get_current_user,         # FastAPI 依赖项：获取当前用户
    require_authentication,   # FastAPI 依赖项：要求用户必须登录
    require_role,             # FastAPI 依赖项：要求用户必须拥有特定角色
    revoke_token              # 函数：撤销 Keycloak 中的 refresh_token
)

# 加载 .env 文件中的环境变量
load_dotenv()
# 从环境变量中获取会话密钥，用于签名会话 cookie
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")
# 如果没有设置会话密钥，则程序无法安全运行，抛出错误
if not SESSION_SECRET_KEY:
    raise ValueError("SESSION_SECRET_KEY 未在 .env 文件中设置。")

# 创建 FastAPI 应用实例
app = FastAPI()

# 添加 SessionMiddleware 中间件，用于启用基于 cookie 的会话管理
# secret_key 用于对会话数据进行签名，防止篡改
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

# 初始化 Jinja2 模板引擎，并指定模板文件所在的目录
templates = Jinja2Templates(directory="templates")

# --- 页面路由 ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user: dict = Depends(get_current_user)):
    """首页/根路径。如果用户已登录，则重定向到仪表盘；否则，显示登录页面。"""
    if user:
        # 如果会话中存在用户信息，说明用户已登录，重定向到仪表盘
        return RedirectResponse(url="/dashboard")
    # 如果用户未登录，渲染登录页面
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """显式地提供登录页面。"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, user: dict = Depends(require_authentication)):
    """仪表盘页面，此页面需要用户登录后才能访问。"""
    # 从用户信息中获取角色列表，默认为空列表
    user_roles = user.get("roles", [])
    # 打印用户角色用于调试
    print(f"用户 '{user.get('username')}' 登录，角色: {user_roles}")
    # 根据用户角色定义一个权限字典，用于在前端模板中控制 UI 元素的显示和隐藏
    permissions = {
        "can_view_details": "admin" in user_roles or "wukui" in user_roles,
        "can_update": "admin" in user_roles,
        "can_merge": "admin" in user_roles,
        "can_analyze": "admin" in user_roles or "wukui" in user_roles,
    }
    # 渲染仪表盘模板，并将用户信息和权限字典传递给模板
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "permissions": permissions})

# --- 认证流程路由 ---

@app.get("/auth/login")
async def start_oidc_login(request: Request):
    """启动 OIDC 登录流程，将用户重定向到 Keycloak 登录页面。"""
    # 1. 生成一个随机的、不可预测的 state 字符串，用于防止 CSRF 攻击
    state = secrets.token_urlsafe(32)
    # 2. 生成 PKCE 码
    code_verifier, code_challenge = generate_pkce_codes()
    # 3. 将 state 和 code_verifier 存储在用户会话中，以便在回调时验证
    request.session["state"] = state
    request.session["code_verifier"] = code_verifier
    
    # 4. 准备发送给 Keycloak 授权端点的参数
    params = {
        "response_type": "code",  # 指定使用授权码流程
        "client_id": CLIENT_ID,   # 我们的客户端 ID
        "redirect_uri": "http://127.0.0.1:8000/auth/callback", # Keycloak 登录成功后重定向回来的地址
        "scope": "openid profile email roles", # 请求的权限范围，包括 OIDC、用户信息、邮箱和角色
        "state": state, # CSRF 保护参数
        "code_challenge": code_challenge, # PKCE 挑战码
        "code_challenge_method": "S256", # 告知 Keycloak 我们使用的是 SHA-256
    }
    
    # 5. 构建完整的授权 URL 并重定向用户
    async with httpx.AsyncClient() as client:
        # 使用 httpx 构建请求对象以正确编码 URL 参数
        url = client.build_request("GET", AUTHORIZATION_ENDPOINT, params=params).url
        return RedirectResponse(url=str(url))

@app.get("/auth/callback")
async def oidc_callback(request: Request, code: str = None, state: str = None, error: str = None):
    """处理从 Keycloak 重定向回来的回调请求。"""
    # 如果 Keycloak 返回了错误信息，则直接报告错误
    if error: raise HTTPException(status_code=400, detail=f"来自 Keycloak 的错误: {error}")
    # 验证 state 参数是否与会话中存储的一致，防止 CSRF 攻击
    if state != request.session.pop("state", None): raise HTTPException(status_code=400, detail="无效的 state 参数")
    # 从会话中取出 code_verifier，用于下一步交换令牌
    code_verifier = request.session.pop("code_verifier", None)

    # 准备发送到令牌端点的数据，用授权码交换令牌
    token_data = {
        "grant_type": "authorization_code", # 授权类型
        "code": code, # 从 Keycloak 获取的授权码
        "redirect_uri": "http://127.0.0.1:8000/auth/callback", # 必须与之前请求时用的 redirect_uri 一致
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET, # 对于私有客户端，需要提供密钥
        "code_verifier": code_verifier, # PKCE 验证码
    }
    # 发送 POST 请求到令牌端点
    async with httpx.AsyncClient() as client:
        token_response = await client.post(TOKEN_ENDPOINT, data=token_data)
        # 如果请求失败，则报告错误
        if token_response.status_code != 200: raise HTTPException(status_code=token_response.status_code, detail=f"获取令牌失败: {token_response.text}")
        tokens = token_response.json() # 解析返回的 JSON 数据，其中包含 id_token, access_token, refresh_token
        print(tokens["id_token"])
    try:
        # 从 id_token 中获取签名密钥
        signing_key = jwks_client.get_signing_key_from_jwt(tokens["id_token"])
        # 解码并验证 id_token
        id_token_payload = jwt.decode(
            tokens["id_token"],      # 要解码的令牌
            signing_key.key,         # 用于验证签名的公钥
            algorithms=["RS256"],    # 指定签名算法
            audience=CLIENT_ID,      # 验证令牌的受众是否是我们的客户端
            issuer=OIDC_CONFIG["issuer"], # 验证令牌的签发者是否是我们的 Keycloak Realm
        )
    except jwt.PyJWTError as e:
        # 如果令牌验证失败，则抛出 401 未授权错误
        raise HTTPException(status_code=401, detail=f"无效的 ID 令牌: {e}")

    # 从验证后的 id_token 中提取用户信息并存入会话
    # 提取领域角色 (Realm Roles)
    realm_roles = id_token_payload.get("realm_access", {}).get("roles", [])
    
    # 提取客户端角色 (Client Roles)
    client_roles = []
    resource_access = id_token_payload.get("resource_access", {})
    if resource_access and CLIENT_ID in resource_access:
        client_roles = resource_access[CLIENT_ID].get("roles", [])
        
    # 合并领域角色和客户端角色，并去重
    combined_roles = list(set(realm_roles + client_roles))

    request.session["user"] = {
        "sub": id_token_payload.get("sub"), # 用户唯一标识符
        "username": id_token_payload.get("preferred_username"), # 用户名
        "name": id_token_payload.get("name"), # 用户全名
        "roles": combined_roles, # 使用合并后的角色
    }
    # 将 id_token 和 refresh_token 也存入会话，用于登出和未来的令牌刷新
    request.session["id_token"] = tokens["id_token"]
    request.session["refresh_token"] = tokens.get("refresh_token")
    
    # 登录成功，重定向到仪表盘页面
    return RedirectResponse(url="/dashboard")

@app.get("/auth/logout")
async def logout(request: Request):
    """处理用户登出流程。"""
    # 从会话中获取 refresh_token
    refresh_token = request.session.get("refresh_token")
    # 如果存在 refresh_token，则在 Keycloak 端将其撤销
    if refresh_token: await revoke_token(refresh_token)
    
    # 从会话中获取 id_token，用于 OIDC 的登出提示
    id_token_hint = request.session.get("id_token")
    # 清空本地应用会话
    request.session.clear()
    
    # 如果 Keycloak 提供了登出端点，则将用户重定向到那里以完成单点登出
    if LOGOUT_ENDPOINT:
        params = { 
            "client_id": CLIENT_ID, 
            "post_logout_redirect_uri": "http://127.0.0.1:8000/" # 登出后重定向回我们的应用首页
        }
        # 如果有 id_token，作为提示传给 Keycloak，可以避免 Keycloak 显示确认登出的页面
        if id_token_hint: params["id_token_hint"] = id_token_hint
        
        async with httpx.AsyncClient() as client:
            url = client.build_request("GET", LOGOUT_ENDPOINT, params=params).url
            return RedirectResponse(url=str(url))
            
    # 如果没有配置登出端点，则直接重定向到首页
    return RedirectResponse(url="/")


# --- 模拟的操作端点 ---
# 注意：这些是给仪表盘页面的表单提交用的 POST 请求端点，不是给用户直接访问的 API

@app.post("/actions/details")
# 【已修正】使用增强后的 require_role，允许 'admin' 或 'wukui' 角色访问
async def action_details(user: dict = Depends(require_role(["admin", "wukui"]))):
    return f"成功: 用户 '{user.get('username')}' 访问了 '游戏服详情' 功能。"

@app.post("/actions/update")
# 要求必须是 'admin' 角色才能访问
async def action_update(user: dict = Depends(require_role("admin"))):
    return f"成功: 用户 '{user.get('username')}' 访问了 '更新' 功能。"

@app.post("/actions/merge")
# 要求必须是 'admin' 角色才能访问
async def action_merge(user: dict = Depends(require_role("admin"))):
    return f"成功: 用户 '{user.get('username')}' 访问了 '合服' 功能。"

@app.post("/actions/analysis")
# 【已修正】使用增强后的 require_role，允许 'admin' 或 'wukui' 角色访问
async def action_analysis(user: dict = Depends(require_role(["admin", "wukui"]))):
    return f"成功: 用户 '{user.get('username')}' 访问了 '数据分析' 功能。"