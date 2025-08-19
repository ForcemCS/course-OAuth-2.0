## What is an ID Token

接下来我们将刨析**OpenID Connect的核心产物——ID令牌 (ID Token)**，解释ID Token是什么，它长什么样，以及它为什么对“用户登录”这个场景至关重要。

```json
{
"kid": "gaNTVZLLCZ1Nyz1fB4AED-yXy15dlvC5vIfgiknJ620",
"alg": "RS256",
"sub": "{USER_ID}",
"email": "user@example.com",
"iss": "https://authorization-server.com/oauth2/ausdlNY9hBoyvKrY0h7",
"aud": "{CLIENT_ID}",
"iat": 1524237221,
"exp": 1524240821,
"nonce": "{NONCE}",
"auth_time": 1524606562
}
```

### 核心思想：ID Token是一张由权威机构签发的、不可伪造的“数字身份证”

OAuth和OpenID Connect的区别：

- **OAuth 2.0**：核心是**授权 (Authorization)**，即“让应用能做事”。它的产物是**`Access Token`**，就像一张**门禁卡**。
- **OpenID Connect (OIDC)**：核心是**认证 (Authentication)**，即“让应用知道你是谁”。它的**新增产物**是**`ID Token`**，就像一张**身份证**。

### 1. ID Token的“格式”是什么？—— 必须是JWT

课程首先强调了一个关键区别：

- **`Access Token`的格式**：OAuth 2.0规范**没有定义**`Access Token`必须长什么样。它可以是一个随机字符串（不透明令牌），也可以是一个JWT（结构化令牌）。这完全由授权服务器自己决定。
- **`ID Token`的格式**：OpenID Connect规范**严格规定**，`ID Token`**必须是JWT (JSON Web Token)**。

**为什么必须是JWT？**
因为ID Token的**唯一目的**就是向**客户端应用 (Client)** 传递关于用户的、可验证的身份信息。JWT的结构化和自包含签名的特性，完美地满足了这个需求。客户端拿到JWT后，可以直接在本地解码、读取信息，并验证其真实性。

### 2. JWT的结构：三段式“数字信封”

它由三个部分组成，用点`.`隔开：`xxxxx.yyyyy.zzzzz`

1. **Header (信封的封面)**：`xxxxx`
   - **内容**：描述这个JWT本身元数据（metadata）的JSON对象。
   - **作用**：告诉接收者“如何处理我”。
   - 截图中的例子 (`Decoded ID Token`的第一部分)：
     - `"alg": "RS256"`: (Algorithm) 声明了这个JWT是使用`RS256`非对称加密算法签名的。
     - `"kid": "gaNTV..."`: (Key ID) 声明了应该使用ID为`gaNTV...`的那个**公钥**来验证我的签名。这非常重要，因为授权服务器可能有多个公钥，`kid`可以帮助客户端快速找到正确的那个。
2. **Payload (信封里的信件)**：`yyyyy`
   - **内容**：包含了**你真正关心的所有数据**的JSON对象，也就是关于用户的身份信息。这些信息被称为“**声明 (Claims)**”。
   - **作用**：传递核心信息。
3. **Signature (信封的火漆封印)**：`zzzzz`
   - **内容**：一个通过将Header和Payload用指定算法（如RS256）和**私钥**加密后生成的签名。
   - **作用**：**防伪**。接收方可以用对应的**公钥**来验证这个签名。如果签名验证通过，就证明这个JWT在传输过程中**没有被篡改过**，并且确实是由持有私钥的那个**权威机构（授权服务器）签发的**。

### 3. Payload详解：身份证上的每一项信息 (Claims)

- **`sub` (Subject)**:
  - **含义**：**主题**，即**用户的唯一标识符 (User ID)**。
  - **这是最重要的声明！** 它是用户在授权服务器那里的、稳定不变的、独一无二的ID。你的应用后端应该用这个`sub`来作为用户在你系统里的主键或外键。
  - `sub`的格式不固定（可能是数字、字符串、邮箱等），但它对每个用户是唯一的且稳定的。

- **`iss` (Issuer)**:
  - **含义**：**签发者**。即这个ID Token是由哪个授权服务器签发的。
  - **安全作用**：你的应用在验证时，**必须**检查这个值是否和你预期的授权服务器地址完全匹配。
- **`aud` (Audience)**:
  - **含义**：**受众**。即这个ID Token是颁发给哪个**客户端应用 (Client)** 使用的。
  - **安全作用**：它的值**必须**是你的应用的`client_id`。这可以防止“令牌重放攻击”——即在A应用获取的ID Token不能被用在B应用上。
- **`exp` (Expiration Time)**:
  - **含义**：**过期时间**。一个Unix时间戳，表示这个ID Token在此时间之后就失效了。
- **`iat` (Issued At)**:
  - **含义**：**签发时间**。一个Unix时间戳，表示这个ID Token是何时创建的。
- **`auth_time` (Authentication Time)**:
  - **含义**：**用户认证时间**。一个Unix时间戳，表示用户是何时在授权服务器上完成登录的。
- **`nonce` (Nonce)**:
  - **含义**：一个在授权请求时由客户端生成的随机字符串。授权服务器会原封不动地把它放回ID Token里。
  - **安全作用**：用于防止重放攻击，确保收到的ID Token是针对本次特定授权请求的响应。
- **其他个人资料声明 (Profile Claims)**:
  - 比如 **`email`**, `name`, `picture` 等。这些是可选的，取决于你在发起授权请求时申请了哪些`scope`（如`profile`, `email`）。