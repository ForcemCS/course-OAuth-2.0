## Authorization Code Flow for Web Applications

我们基于正在构建的**“基于FastAPI和React的游戏运维平台”**这个案例进行说明

**角色扮演：**

- **Alice (User)**：运维工程师。
- **浏览器 (User-Agent)**：Alice正在使用的Chrome浏览器。
- **React运维前端 (Public Client)**：你在 `http://ops.mygame.com` 上部署的React单页应用。
- **FastAPI运维后端 (Resource Server)**：你在 `https://api.ops.mygame.com` 上部署的API服务。
- **Keycloak (Authorization Server)**：你搭建的、位于 `https://auth.mygame.com` 的独立认证中心。

### 序幕：Alice访问你的平台

Alice在浏览器里输入 `http://ops.mygame.com`，看到了一个简洁的登录按钮：“使用公司账号登录”。

### 第一幕：前端的准备与“出差” (PKCE与前通道)

Alice点击了登录按钮。这时，在她的**浏览器里运行的React代码**开始行动了。

1. **生成“一次性暗号” (`code_verifier`)**

   - **术语**：`Code Verifier`
   - **含义**：一个“密码验证器”，一个只有当前这次登录流程知道的、随机生成的、绝密的字符串。
   - **你的React代码做的事**：调用一个函数生成一个像 `E9j...VpA` 这样的长随机字符串，并把它**临时存放在浏览器的内存中**。

   ```
   // 伪代码，实际会使用库
   const code_verifier = "4A6hBupTkAtgbaQs39RSELUEqtSWDTCRzVh1PpxD5YVK11u"; 
   // 存入内存
   sessionStorage.setItem('pkce_verifier', code_verifier);
   ```

2. **制作“公开的谜题” (`code_challenge`)**

   - **术语**：`Code Challenge` 和 `Code Challenge Method`
   - **含义**：一个“代码挑战”。它是对上面那个“一次性暗号”进行单向加密（哈希）后得到的“谜题”。别人看到谜题，猜不出谜底（暗号）。
   - **你的React代码做的事**：用SHA256算法处理`code_verifier`，得到一个像 `Lp...yXg` 这样的字符串。这就是`code_challenge`。

   ```
   // 伪代码，实际会使用库
   const code_challenge = base64url(sha256(code_verifier)); 
   // 得到 -> "ipSBt30y481401NGBbLjo026cqwsRQzr5KI40AuLAdZ8"
   ```

3. **打包“出差申请”并发起重定向**

   - **术语**：`Authorization Request`, `Redirect`

   - **含义**：准备好所有材料，让Alice的浏览器跳转到Keycloak去办正事。

   - 你的React代码做的事：构建一个URL，然后执行

     ```
     window.location.href = '...'
     ```

     这个URL包含了：

     - **`client_id`**: "ops-frontend" (告诉Keycloak，是“运维平台前端”这个应用发起的请求)
     - **`redirect_uri`**: "http://ops.mygame.com/callback" (告诉Keycloak，办完事后把Alice送回这个地址)
     - **`scope`**: "openid profile email roles" (告诉Keycloak，我想知道登录用户的身份信息和角色)
     - **`response_type`**: "code" (告诉Keycloak，我走的是授权码流程，请给我一个`code`)
     - **`code_challenge`**: "Lp...yXg" (把那个“公开的谜题”带上)
     - **`code_challenge_method`**: "S256" (告诉Keycloak，谜题是用SHA256加密的)
     - **`state`**: 一个随机字符串 (用于防止一种叫CSRF的攻击，确保回来的人是当初出去的那个)

     ```
     https://dev-xxxxxxxxxxx.us.auth0.com/authorize?
       response_type=code&
       client_id=V9D7B7Ix6FRakZQqhrFHoOglXaDdgIRr&
       state=my_random_test_state_0815&
       redirect_uri=https://ops.mygame.com/callback&
       code_challenge=V9TyJqK5z-U5KdIB85CpxlFnGg8dQ2l_YWrqiQpLTu4&
       code_challenge_method=S256
     ```

Alice的浏览器地址栏瞬间从 `ops.mygame.com` 变成了 `auth.mygame.com`。她现在面对的是Keycloak的官方登录页面。**React前端的任务暂时完成了，它在静静等待Alice“出差”归来。**

### 第二幕：在Keycloak认证并拿到“临时通行证”

1. Alice在Keycloak页面输入她的公司邮箱和密码。

2. Keycloak验证成功，弹出一个**同意页面 (Consent Screen)**：“运维平台前端 正在申请获取您的个人资料和角色信息，是否同意？”

3. Alice点击“同意”。

4. Keycloak现在生成一个

   授权码 (Authorization Code)。

   - **术语**：`Authorization Code`
   - **含义**：一个**一次性的、短时效的临时通行证**。它不是最终的门禁卡，只是用来换取门禁卡的凭证。
   - Keycloak做的事：
     - 生成一个像 `f1c...a3b` 这样的`code`。
     - 把这个`code`和之前收到的`code_challenge`（那个“谜题”）在后台**绑定**起来。
     - 将Alice的浏览器重定向回 `http://ops.mygame.com/callback`，并在URL后面附上这个`code`。

   ```
   https://ops.mygame.com/callback?code=Q-mxifBLk4A98fSUunlcdB_UXwm3yXLJjH7JSQ_qAaCKR&state=my_random_test_state_0815
   ```

Alice的浏览器地址栏现在变成了 `http://ops.mygame.com/callback?code=f1c...a3b&state=...`。她“出差”回来了！

------

### 第三幕：前端用“临时证”换“正式卡” (后通道交易)

React应用被重新加载，它在启动时检查URL。

1. **接收“临时通行证”**

   - **你的React代码做的事**：从URL中解析出`code`和`state`。检查`state`是否和当初发出去的一致，确认无误。

2. **发起“后台交易” (`Token Request`)**

   - **术语**：`Back Channel`, `Token Endpoint`

   - **含义**：现在，React代码要通过一个**安全的、浏览器到服务器的直接API请求（后通道）**，去Keycloak的`/token`接口换取真正的令牌。这个过程用户是看不到的。

   - 你的React代码做的事：使用`fetch`或者`axios`向

     ```
     https://auth.mygame.com/token
     ```

     发起一个POST请求。请求体中包含了：

     - **`grant_type`**: "authorization_code" (表明我的意图：用code换token)
     - **`code`**: "f1c...a3b" (我带回来的临时通行证)
     - **`redirect_uri`**: "http://ops.mygame.com/callback" (再次确认我的身份)
     - **`client_id`**: "ops-frontend"
     - **`code_verifier`**: "E9j...VpA" (**亮出当初藏起来的“一次性暗号”！**)

   ```
   curl -X POST https://dev-xxxxxxxxxxxxe.us.auth0.com/oauth/token \
     -d grant_type=authorization_code \
     -d redirect_uri=https://ops.mygame.com/callback \
     -d client_id=V9D7B7Ix6FRakZQqhrFHoOglXaDdgIRr \
     -d client_secret=xxxxxxxxxxxxxx \
     -d code_verifier=xxxxxxxxx \
     -d code=07luAfMNHbTcfxxxxxxxxxxxxxx
   ```

3. **Keycloak的终极验证**

   - Keycloak收到这个请求后，进行PKCE验证：
     1. 根据`code`找到绑定的`code_challenge`（谜题）。
     2. 用SHA256算法处理这次请求中的`code_verifier`（暗号）。
     3. **对比两个结果。如果一致，验证通过！** Keycloak确信，来换令牌的，就是刚刚发起登录的那个浏览器会话，中途没有被坏人掉包。

4. **发放“正式门禁卡” (`Access Token`)**

   - Keycloak生成一个JWT格式的`access_token`，并通过这个安全的后通道连接返回给React应用。

5. 返回结果如下

   ```json
   {"access_token":"xxxxxxxxx","expires_in":86400,"token_type":"Bearer"}
   ```

   

------

### 第四幕：Alice使用平台，前端与后端交互

React应用拿到了宝贵的`access_token`。

1. **你的React代码做的事**：

   - 将`access_token`安全地存储在内存中。

   - 配置HTTP客户端（如axios），让以后所有对FastAPI后端的请求，都在请求头里自动加上：

     > `Authorization: Bearer <the_long_access_token_string>`

2. Alice在运维界面上，点击了“重启GS-01服务器”按钮。

3. React应用向你的FastAPI后端发起请求：`POST https://api.ops.mygame.com/servers/GS-01/reboot`。这个请求头里，带着那个`access_token`。

------

### 第五幕：FastAPI后端的“门禁检查”

你的FastAPI应用收到了这个请求。

1. **你的FastAPI代码做的事 (`verify_token` 依赖项)**：

   - 从`Authorization`头里取出令牌。

   - 去`https://auth.mygame.com`获取公钥。

   - 验证令牌：

     - 签名对吗？（确保是Keycloak颁发的，没被伪造）
     - 过期了吗？
     - `iss`（签发者）和`aud`（受众）对吗？

   - 令牌有效，解码它，看到里面的信息，比如：

     > `{ "preferred_username": "alice", "realm_access": { "roles": ["game-admin", ...] } }`

2. **你的FastAPI代码做的事 (`require_role` 依赖项)**：

   - 检查`/servers/{server_id}/reboot`这个接口，发现它需要`game-admin`角色。
   - 查看解码后的令牌，发现Alice的`roles`列表里**有`game-admin`**。
   - **门禁检查通过！**

3. FastAPI继续执行后面的业务逻辑，向游戏服务器发送重启命令，并返回成功信息给前端。Alice看到了“服务器重启成功”的提示。