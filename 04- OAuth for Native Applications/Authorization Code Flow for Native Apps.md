## Authorization Code Flow for Native Apps

原生应用（特别是分发到应用商店的移动App）的本质：**它是一个公共客户端 (Public Client)，无法安全地保管任何秘密。**

因此，整个流程中最大的变化就是：

- **注册时**：授权服务器（如果设计得好）根本不会给你分配`client_secret`。
- **交换令牌时**：在最后的后通道请求中，**绝对不包含`client_secret`参数**。

### 实践差异：如何“启动浏览器”

- **Web服务器应用**：整个流程都在用户的同一个浏览器标签页中通过**服务器端重定向**完成。
- 原生应用：流程需要从App环境跳转到浏览器环境，再跳回来。最佳实践：
  - **不使用**会“跳出App”的系统浏览器。
  - **不使用**不安全的内嵌WebView。
  - **必须使用**系统提供的**安全浏览器视图**（iOS的`SFSafariViewController` / `ASWebAuthenticationSession`，Android的`Chrome Custom Tabs`）。

### 流程详解：一步一步走完原生应用的授权之旅

我们用一个原生App（比如你用Swift写的iOS游戏运维App）的视角，来重新走一遍这个流程。

#### 第一幕：App内部的准备与“启动安全浏览器” (前通道)

1. **用户点击“登录”按钮**。
2. 生成PKCE凭证：
   - 你的iOS App代码**在设备上**生成一个一次性的、随机的`code_verifier`（秘密）。
   - 你的iOS App代码对`code_verifier`进行SHA256哈希运算，得到`code_challenge`（公开的指纹）。
3. 构建授权URL：
   - 你的iOS App代码拼接出一个完整的`Authorization URL`，包含`client_id`, `redirect_uri` (比如 `https://ops-callback.mygame.com/auth`), `scope`, `state`, `code_challenge`, 和 `code_challenge_method`。
4. 启动安全浏览器视图：
   - 你的iOS App代码调用`ASWebAuthenticationSession` API，并把上面构建好的URL传给它。
   - 操作系统会从屏幕底部滑出一个**安全浏览器窗口**，加载这个URL。

#### 第二幕：用户在安全浏览器中认证

1. 用户在这个弹出的、由系统控制的浏览器窗口中，看到了Auth0/Keycloak的官方登录页面。
2. **单点登录 (SSO) 的优势体现**：课程特别指出，因为这个安全浏览器视图**可以共享系统浏览器（Safari）的Cookie**，所以如果用户之前在Safari里登录过Auth0，那么在这个弹出的窗口里，他很可能**已经处于登录状态**，无需再次输入密码，极大地提升了用户体验。
3. 用户完成认证（可能需要输入密码，也可能只需要点击确认）并同意授权。
4. **Auth0生成`Authorization Code`**，并将其与`code_challenge`绑定。
5. **Auth0发起重定向**：它让这个安全浏览器视图尝试跳转到你指定的`redirect_uri` (`https://ops-callback.mygame.com/auth?code=...`)。

#### 第三幕：返回App并交换令牌 (前通道结束，后通道开始)

1. **操作系统捕获重定向**：iOS系统发现这个重定向的URL是你的App注册过的“通用链接 (Universal Link)”。
2. **关闭浏览器并传递数据**：
   - 系统会自动关闭那个弹出的安全浏览器视图。
   - 同时，它会将完整的返回URL（包含`code`和`state`）传递给你的iOS App。
3. **App接收并解析`code`**：你的iOS App代码从收到的URL中提取出`Authorization Code`。
4. **App发起后通道请求**：
   - 你的iOS App代码现在直接从**设备上**，向授权服务器的`/token`端点发起一个**HTTPS POST请求**。
   - 这个请求体中包含了：
     - `grant_type=authorization_code`
     - `code`（刚刚拿到的）
     - `redirect_uri`（当初使用的）
     - `client_id`
     - `code_verifier`（第一步中生成的那个原始秘密）
   - **注意：这个请求中没有`client_secret`！**
5. **服务器进行PKCE验证**：
   - 授权服务器收到请求，验证`code`的有效性。
   - 最关键的一步：它对请求中的`code_verifier`进行哈希运算，并与当初存下的`code_challenge`进行比较。
   - **匹配成功**，服务器就确信，来交换令牌的，就是当初那个发起了PKCE挑战的设备/应用实例。授权码没有被盗用。
6. **服务器返回令牌**：
   - 授权服务器通过这个安全的后通道连接，将`access_token`和`refresh_token`返回给你的iOS App。
   - 你的iOS App将这些令牌安全地存储在设备的**钥匙串 (Keychain)** 中。

#### 第四幕：App使用令牌

1. 你的iOS App现在可以使用`access_token`去访问你的FastAPI后端了。
2. 当`access_token`过期后，它可以使用存储在钥匙串中的`refresh_token`，通过后通道再次向`/token`端点请求一个新的`access_token`，而无需再次打扰用户。