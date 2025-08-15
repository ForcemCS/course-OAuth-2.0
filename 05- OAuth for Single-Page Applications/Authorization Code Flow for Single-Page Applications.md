## Authorization Code Flow for Single-Page Applications

SPA是“裸露在外的代码”，必须依赖PKCE和浏览器API来保障安全

强调了SPA的本质：

- **公共客户端**：所有JavaScript代码都在用户浏览器中，无法隐藏`client_secret`。
- **必须使用无`client_secret`的流程**。
- **PKCE是其安全的基石**。

### 流程详解：与原生应用流程的对比与强调

整个数据流转的步骤（前通道送`code`，后通道换`token`）与原生应用是完全一致的，但也有不同的地方，以突出SPA的特点。

#### 第一幕：SPA内部的准备与“页面跳转” (前通道)

1. **用户点击“登录”按钮**。
2. 生成PKCE凭证：
   - SPA的**JavaScript代码**在浏览器中生成一次性的`code_verifier`（秘密）。
   - **一个重要的实现细节**：课程提到，`code_verifier`通常需要被**临时存储起来**，以便在用户被重定向回来后还能找到它。最常见的地方是 **`localStorage`** 或 **`sessionStorage`**。
   - JS代码对`code_verifier`进行哈希运算，得到`code_challenge`（公开的指纹）。
3. 构建授权URL并发起重定向：
   - JS代码拼接出完整的`Authorization URL`。
   - JS代码通过执行 `window.location.href = '...'` 来让整个页面**跳转**到授权服务器。

#### 第二幕：用户在授权服务器认证

这个过程与原生应用完全相同：用户在授权服务器的官方页面上登录、同意，然后授权服务器生成`code`，并将其与`code_challenge`绑定。

#### 第三幕：返回SPA并交换令牌 (前通道结束，后通道开始)

1. **浏览器跳转回SPA**：授权服务器将用户的浏览器重定向回预注册的`redirect_uri`（比如 `https://ops.mygame.com/callback`），URL中附带着`code`和`state`。
2. SPA接收并解析`code`：
   - 你的SPA（比如React应用）在`/callback`这个路由对应的组件加载时，会执行JS代码。
   - 这段代码从URL中提取出`Authorization Code`。
3. SPA发起后通道请求：
   - **一个关键的澄清**：课程强调，即使是运行在浏览器中的JavaScript，当它通过`fetch`或`XMLHttpRequest`（AJAX）发起一个HTTPS POST请求时，这依然是一个**后通道 (Back Channel)** 请求。因为它是一个直接的点对点连接，数据在请求体中，而不是在地址栏里。
   - JS代码从`localStorage`或`sessionStorage`中**取回**之前存的那个`code_verifier`。
   - JS代码向授权服务器的`/token`端点发起一个POST请求，请求体中包含`grant_type`, `code`, `redirect_uri`, `client_id`, 和 `code_verifier`。**同样，没有`client_secret`**。
4. 一个重要的技术要求：CORS
   - 特别指出一个SPA独有的技术问题：**跨源资源共享 (Cross-Origin Resource Sharing - CORS)**。
   - 因为你的SPA运行在`ops.mygame.com`这个域，而它需要向`auth.mygame.com`这个**不同的域**发起POST请求。
   - 为了让浏览器允许这个跨域请求，**授权服务器（Auth0/Keycloak）必须正确配置CORS头**，明确允许来自`ops.mygame.com`的请求。否则，浏览器会出于安全原因阻止这个请求。
5. 服务器进行PKCE验证并返回令牌：
   - 这个过程与原生应用完全一样。服务器验证`code_verifier`成功后，返回`access_token`。

#### 第四幕：SPA使用令牌

1. SPA的JS代码拿到`access_token`后，通常会将它存储在**内存中的变量**里（这是比`localStorage`更安全的选择），用于后续对你的FastAPI后端的API请求。

### 总结：SPA流程与原生应用流程的异同

- **几乎完全相同**：
  - **核心安全模型**：都是公共客户端，都依赖PKCE来保护授权码流程。
  - **数据流**：都是通过前通道（浏览器跳转）获取`code`，再通过后通道（API POST请求）用`code`和`code_verifier`换取`token`。
  - **参数**：在授权请求和令牌请求中使用的参数基本一致（都没有`client_secret`）。
- **细微但重要的差异**：
  - **用户体验**：原生应用使用**系统级的安全浏览器视图**，体验更无缝；SPA则是**整个页面跳转**，然后再跳回来。
  - **PKCE Verifier的存储**：原生应用可以存在设备的安全存储区，而SPA通常只能存在`sessionStorage`或`localStorage`中（这增加了被XSS攻击窃取的风险）。
  - **技术依赖**：SPA的后通道请求**强依赖于授权服务器正确配置CORS**。

尽管SPA和原生应用都是公共客户端，但由于SPA完全运行在“危机四伏”的浏览器环境中，你在实现这个标准流程时，需要额外关注像**CORS配置**和**令牌存储安全**（尽量避免`localStorage`）这样的浏览器特有问题。