## Local Token Validation

接下来我们将介绍**API验证`Access Token`的第二种方法，也是更高级、更高效的方法：本地令牌验证 (Local Token Validation)**。

### 核心思想：API自己成为一个“合格的验票员”，无需再打电话问总部

当`Access Token`是JWT格式时，你的API（资源服务器）可以被“训练”成一个能够**独立、离线**完成所有验证工作的专家。它不再需要每次都去远程内省，从而极大地提升了性能和系统的解耦性。

### 前提：不要自己造轮子

强烈建议：

> **“by far the easiest way to handle this is to use a library for everything.”**
> (到目前为止，处理这件事最简单的方法就是对所有事情都使用一个库。)

- **原因**：JWT验证涉及密码学操作和一系列繁琐的检查。手写代码极易出错，并可能引入严重的安全漏洞。
- **建议**：总是使用经过社区检验的、成熟的JWT库（比如Python的`python-jose`或`PyJWT`）。如果你的授权服务器提供了官方的SDK，那更是首选。

此文档目的是让你**理解这些库在后台做了什么**，以便你能正确地使用它们，并确认它们没有遗漏任何关键的验证步骤。

### 本地验证的完整步骤

你的FastAPI后端在收到一个JWT格式的`Access Token`后，需要按照以下严格的顺序进行验证。

#### 第零步：一个重要的安全前提

- 在验证签名**之前**，JWT的Header和Payload里的所有内容都是**不可信的**。
- 重要推论：你不能完全相信Header里声明的签名算法（alg）。
  - **经典攻击 (`none`算法)**：如果一个库允许`alg`为`none`，攻击者就可以构造一个没有签名的令牌，库会直接认为它“有效”。现代规范已禁止使用`none`算法。
  - **算法混淆攻击**：如果你的服务器用的是非对称算法`RS256`，攻击者可以伪造一个Header，声明`alg`是**对称算法`HS256`**。如果你的验证库配置不当，它可能会错误地将`RS256`的**公钥**当作`HS256`的**共享密钥**来使用，从而导致验证被绕过。
- **你的对策**：在你的API代码中，应该**硬编码一个可接受的算法列表**（比如只接受`['RS256']`），并强制验证库只使用这个列表中的算法。

#### 第一步：找到正确的公钥 (Find the Public Key)

1. **解码Header**：从令牌的第一部分解码出Header JSON。
2. **获取`kid` (Key ID)**：从Header中找到`kid`声明。这个ID告诉我们应该用哪个公钥来验证。
3. 发现JWKS URI：
   - API需要知道授权服务器的**元数据URL**。这通常是通过配置得到的，或者可以根据`iss`（签发者）URL拼接`.well-known/openid-configuration`来构建。
   - 你的API向这个元数据URL发起一次**GET请求**（这个操作可以在API启动时做一次，然后缓存结果）。
   - 从返回的JSON中（如第一个JSON示例所示），找到`jwks_uri`的值。
4. 获取公钥列表：
   - 你的API向`jwks_uri`这个地址再发起一次**GET请求**。
   - 它会得到一个包含一个或多个公钥的JSON数组（如第二个JSON示例所示）。每个公钥对象都有自己的`kid`。
5. **匹配公钥**：你的API在公钥列表中，根据之前从令牌Header中获取的`kid`，找到那个完全匹配的公钥对象。

#### 第二步：验证签名 (Validate the Signature)

- **动作**：将**完整的JWT字符串**、**上一步找到的公钥**和**预期的算法（`RS256`）**，一起交给JWT库的验证函数。
- **结果**：库会告诉你签名是否有效。如果无效，立即拒绝请求。

#### 第三步：验证核心声明 (Verify the Claims)

签名有效只代表令牌是真的且没被篡改。现在需要验证它的内容是否符合要求。

1. **`iss` (Issuer)**：检查令牌的`iss`声明，是否与你API配置中信任的那个授权服务器的Identifier完全匹配。
2. **`aud` (Audience)**：检查令牌的`aud`声明，是否与你API自身的Identifier完全匹配。
3. **`exp` 和 `iat` (Timestamps)**：检查令牌是否已过期，以及签发时间是否合理（比如不能是未来的时间）。

#### 第四步：进行业务相关的授权检查 (Business-level Authorization)

在完成了上述所有**认证和基础验证**后，现在才进入到你自己的业务逻辑。

- **`scope`**：检查令牌的`scope`声明中，是否包含了当前API端点所必需的权限。比如，`/servers/reboot`需要`reboot:server`这个scope。
- **自定义声明**：检查其他自定义声明，如`groups`，来判断用户是否属于“管理员”组。
- **`acr` / `amr`**：如果需要，检查认证上下文和方法，以强制实施更高的安全策略。

### 本地验证的“代价”：信息可能是过时的

- 这是本地验证的**核心权衡**。
- **你验证的，是令牌在“被签发那一刻”的快照**。
- 你**无法**通过本地验证得知，在令牌被签发之后，系统状态是否发生了变化（比如用户被删除、权限被修改）。
- **解决方案**：**设置较短的令牌生命周期 (`exp`)**。如果令牌每15分钟就过期，那么你依赖的信息最多也就过时15分钟，风险是可控的。生命周期越长，信息过时的风险就越大。

### 总结

- **本地验证**是处理JWT `Access Token`的**高性能、高可扩展性**的方法，是现代微服务架构的首选。
- 它要求API开发者遵循一个**严谨的多步验证流程**：验证签名 -> 验证核心声明 -> 验证业务权限。
- **绝对不要自己实现密码学部分**，必须使用成熟的库。
- 开发者必须理解其**“过时信息”**的特性，并通过**设置合理的令牌生命周期**来管理这种风险。

## 举例说明

### 背景：你的FastAPI后端收到了一个API请求

你的FastAPI后端的一个受保护端点（比如`/servers/list`）收到了一个请求，请求的`Authorization`头里包含了一个长长的`Access Token`（JWT格式）。现在，你的FastAPI安全依赖项需要开始工作了。

### 第一步：找到正确的公钥

FastAPI需要找到用于验证这个JWT签名的公钥。这个过程涉及到前两个JSON示例。

#### 步骤1.1: 发现JWKS URI (使用第一个JSON)

你的FastAPI应用在**启动时**（或者第一次需要验证令牌时），会去访问授权服务器的**元数据端点**。

> 服务器元数据 (Server Metadata)

```json
{
  "issuer": "https://authorization-server.com/",
  "authorization_endpoint": "https://authorization-server.com/authorize",
  "token_endpoint": "https://authorization-server.com/token",
  "jwks_uri": "https://authorization-server.com/keys",  // <-- FastAPI要找的就是这个！
  "response_types_supported": [
    "code",
    "id_token",
    "code_id_token"
  ],
  "response_modes_supported": [
    "query",
    "form_post"
  ],
  "grant_types_supported": [
    "authorization_code",
    "refresh_token",
    "client_credentials"
  ],
  "scopes_supported": [
    "openid",
    "profile",
    "email",
    "address",
    "phone",
    "offline_access"
  ],
  "token_endpoint_auth_methods_supported": [
    "client_secret_basic",
    "refresh_token",
    "client_credentials"
  ]
}
```

- **对应关系**：你的FastAPI代码会向 `https://authorization-server.com/.well-known/openid-configuration` (或者类似的地址) 发起一个GET请求，然后得到这个JSON。
- **你的代码做的事**：从这个JSON中，解析并提取出`jwks_uri`的值，也就是 `https://authorization-server.com/keys`。现在，它知道去哪里找公钥了。

#### 步骤1.2: 获取公钥列表并匹配

接下来，FastAPI会向刚刚找到的`jwks_uri`发起另一个GET请求。

> **第二个JSON示例：公钥集 (JSON Web Key Set - JWKS)**
>
> ```json
> {
>   "keys": [
>     {
>       "kty": "RSA",
>       "alg": "RS256",
>       "kid": "gaNTVZLLCZlNyZ1fB4AED-yXy1sdIvCV5ViFgikNJ620",   // <-- Key ID 1
>       "use": "sig",
>       "e": "AQAB",
>       "n": "jWgbM8vdrxZpY6ZYd2CP1aAHNyIOeb1XFvns_kXICeBBQPM LGS1c33NTGUTSb4ODkSJjKKm4xK35DFte5ewnJBL028a4QQqXr2LPjrjghlt1c8zmgw3IGS0SKvwHL5J5mwLMzvIknPHbi wFErSa_4KqtgTNYIZBFQ7-dObHw-Wx9UY8h7FlS4M4GKw"
>     },
>     {
>       "kty": "RSA",
>       "alg": "RS256",
>       "kid": "Hwj6AYoloeCkIrLZ3JzgY2oRBLO-RD9qNiOBp98Qpm",    // <-- Key ID 1
>       "use": "sig",
>       "e": "AQAB",
>       "n": "gCkbzHZQq5Y21L2DdVPcYNTxRu3SlgsKT8HTLFeWCeBBQPQ MLGS1c33NTGUTSb4ODkSJjKKm4xK35DFte5ewnJBL028a4QQ qXr2LPprjghlt1c8zmgw3IGS0SKvwHL5J5mwLMzvIknPHbi wFErSa_4KqtgTNYIZBFwQ7-doBHw-8K2S6Ru3dncGdQg"
>     }
>   ]
> }
> ```

- **对应关系**：这是从`https://authorization-server.com/keys`返回的公钥列表。
- 你的代码做的事：
  1. 首先，从收到的那个`Access Token`的**Header**部分，解码出`kid`。
  2. 假设解码出的`kid`是 `"gaNTVZLLCZlNyZ1fB4AED-yXy1sdIvCV5ViFgikNJ620"`。
  3. 你的代码就会在这个`keys`数组中遍历，找到那个`kid`与之完全匹配的公钥对象。
  4. 现在，它手里就拿到了那个**正确的、用于验证签名的公钥**。

### 第二、三、四步：验证令牌和声明 

现在，FastAPI万事俱备，可以开始对收到的`Access Token`本身进行验证了。

> **解码后的Access Token Payload**
>
> ```json
> { 
>   "iss": "https://authorization-server.com",
>   "aud": "api://default",
>   "exp": 1606944556,
>   "iat": 1606940956,
>   "sub": "00ui0fjkielY46ma00h7",
>   "client_id": "00aHzpp3tcpFfrcWlOh7",
>   "scope": [ "offline_access", "photo" ],
>   ... 
> }
> ```

- **对应关系**：这是你的FastAPI从请求头中拿到的`Access Token`，在经过**签名验证成功后**，解码其Payload部分得到的内容。
- 你的代码（通过JWT库）做的事：
  1. **验证签名**：使用第一步获取的公钥，对完整的`Access Token`字符串进行签名验证。
  2. 验证核心声明：
     - 检查`"iss"`的值是否等于`"https://authorization-server.com/"`（从元数据中获取的issuer）。 -> **匹配！**
     - 检查`"aud"`的值是否等于你API配置的Identifier，比如`"api://default"`。 -> **匹配！**
     - 检查`"exp"` (1606944556) 是否大于当前时间。 -> **假设匹配！**
  3. 进行业务授权检查：
     - 假设`/servers/list`这个接口需要`read:servers`这个scope。
     - 你的代码会检查`"scope"`数组 `[ "offline_access", "photo" ]`。
     - 发现里面**没有`read:servers`**。
     - **授权失败！** 你的FastAPI会立即返回一个`403 Forbidden`错误，并告诉客户端“权限不足”。

### 总结：数据流与验证链

1. **FastAPI启动时** -> 请求**元数据JSON** -> 找到`jwks_uri`。
2. **FastAPI需要公钥时** -> 请求**JWKS JSON** -> 拿到公钥列表并缓存。
3. 每次API请求到达时：
   - FastAPI解码收到的`Access Token`的Header，拿到`kid`。
   - 从缓存的公钥列表中，用`kid`找到对应的公钥。
   - 用公钥验证`Access Token`的签名。
   - 签名通过后，得到**解码后的Payload JSON**。
   - 逐一检查Payload中的`iss`, `aud`, `exp`等核心声明。
   - 最后，检查`scope`等业务相关声明，做出最终的授权决定。