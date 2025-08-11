## Role

### 角色扮演：谁是谁？

首先，我们来确定这个场景中的各个“角色”：

- **你 (Resource Owner)**：你，拥有你的谷歌账户和里面的数据（姓名、邮箱、头像等）。
- **你的浏览器 (User-Agent)**：你进行所有操作的工具。
- Canva的网站 (Client)：那个想要确认你身份的应用。
  - 更精确地说，Canva的系统扮演了两个客户端角色：
    1. **Canva的前端（你在浏览器里看到的页面）**：是一个**公共客户端 (Public Client)**，因为它运行在你的浏览器里，藏不住秘密。
    2. **Canva的后端服务器**：是一个**机密客户端 (Confidential Client)**，因为它运行在Canva自己的服务器上，可以安全地保管`client_secret`。
- **谷歌 (Authorization Server)**：负责验证你的身份，并征求你的同意，是整个流程的“认证中心”。
- **你的谷歌账户信息 (Resource)**：Canva想要获取的数据，比如你的姓名和邮箱地址，以便为你创建或登录账户。
- **谷歌的用户信息API (Resource Server)**：存放你账户信息的服务器。

------

### 慢动作回放：登录的全过程

#### 第1步：你发起请求

你在Canva的网站上，点击了那个熟悉的 "Continue with Google" 按钮。

**背后发生了什么？**
Canva的前端JavaScript代码并不会弹出一个密码框。相反，它会把你的浏览器**重定向**到一个精心构造好的谷歌URL。这个URL看起来可能像这样：

```
https://accounts.google.com/o/oauth2/v2/auth?
  client_id=CANVAS_CLIENT_ID.apps.googleusercontent.com  // 告诉谷歌：“我是Canva”
& redirect_uri=https://www.canva.com/login/google/callback // 告诉谷歌：完事后跳回这里
& scope=openid%20profile%20email                          // 告诉谷歌：我想要这些权限
& response_type=code                                      // 告诉谷歌：请给我一个授权码
& ... (其他参数，比如PKCE)
```

- `client_id`：Canva在谷歌那里注册时获得的公开身份ID。
- `redirect_uri`：**极其重要的安全设置**。谷歌只会把用户重定向到这个预先注册好的地址。
- `scope`：Canva申请的权限。这里的`openid`, `profile`, `email`是OIDC的标准权限，意思分别是：“我需要确认你的身份”、“我想要你的基本资料（姓名、头像）”、“我想要你的邮箱地址”。

#### 第2步：你在谷歌的环境中进行认证

你的浏览器地址栏现在变成了 `accounts.google.com`。你处在一个**完全由谷歌控制的安全环境中**。

你在这里输入你的谷歌邮箱和密码。**Canva永远、永远也看不到你的密码。**

如果这是你第一次用谷歌登录Canva，谷歌会弹出一个**同意页面 (Consent Screen)**，问你：“Canva申请获取你的姓名、邮箱和头像，你同意吗？”。你点击“同意”。

#### 第3步：谷歌发给你一张“临时票据”

谷歌验证了你的身份和你对Canva的授权后，它会把你的浏览器**重定向**回第1步中指定的`redirect_uri`。在重定向的URL后面，会附带一个重要的参数：`code`。

```
https://www.canva.com/login/google/callback?code=A_VERY_LONG_TEMPORARY_CODE
```

这个`code`（授权码）就像一张**一次性的、有时效的电影票根**。它本身不能用来直接看电影（访问API），但可以用来去售票处换取真正的电影票（令牌）。

#### 第4步：Canva的后端用“票根”换取“正式票”

你的浏览器带着这个`code`回到了Canva的网站。Canva的前端JavaScript拿到这个`code`后，立刻把它发送给**Canva的后端服务器**。

现在，**Canva的后端服务器（机密客户端）** 开始行动了。它向谷歌的服务器发起一个**安全、直接的后端到后端的API请求**。这个请求包含了：

1. 刚刚从你那里获得的`code`（临时票根）。
2. 它自己的`client_id`（我是Canva）。
3. 它自己的`client_secret`（**这是它的秘密，用来向谷歌证明它就是真正的Canva，而不是冒名顶替者**）。

#### 第5步：谷歌颁发令牌 (Tokens)

谷歌的服务器收到了Canva后端的请求。它会进行验证：

- 这个`code`是我刚刚颁发的吗？有效吗？
- 这个`client_id`和`client_secret`匹配吗？

一切无误后，谷歌就会向Canva的后端颁发**两个关键的令牌**：

1. **Access Token**：这是**OAuth 2.0**的核心。如果Canva还申请了其他权限（比如访问你的Google Drive文件），它就会用这个令牌去调用Google Drive的API。
2. **ID Token**：这是**OpenID Connect**的核心，也是我们登录场景的关键！它是一个JWT格式的字符串，里面包含了经过谷歌**签名**的用户信息。

`ID Token`解码后，内容大致如下：

```json
{
  "iss": "https://accounts.google.com", // 签发者
  "sub": "11223344556677889900",       // 你在谷歌的唯一ID
  "email": "your.email@gmail.com",
  "email_verified": true,
  "name": "你的名字",
  "picture": "你的头像URL",
  "aud": "CANVAS_CLIENT_ID.apps.googleusercontent.com", // 接收者
  "exp": 167... // 过期时间
}
```

#### 第6步：Canva让你登录成功

Canva的后端拿到了这个`ID Token`。它会：

1. **验证签名**：用谷歌的公钥来验证这个`ID Token`的签名，确保它没有被篡改过，确实是谷歌颁发的。
2. **提取信息**：从Token中安全地取出你的邮箱和名字。
3. 处理账户：在自己的用户数据库里查找这个邮箱。
   - **如果找到了**：说明你是老用户，直接让你登录。
   - **如果没找到**：说明你是新用户，用这些信息为你自动创建一个新的Canva账户，然后让你登录。
4. **创建Canva会话**：为你生成一个Canva自己的会话（Session Cookie），并返回给你的浏览器。

现在，你的浏览器里有了Canva的登录凭证。你成功登录了！之后你在Canva上的所有操作，都只和Canva的服务器打交道，和谷歌已经没关系了（直到你的Canva会话过期需要重新登录）。

### 总结

这个流程的精妙之处在于：

- **安全**：你的谷歌密码从未离开过谷歌的服务器。Canva无法获取它。
- **方便**：你不需要为Canva再记一套新的密码。
- **信任委托**：Canva完全信任谷歌提供的用户信息是准确的，因为它有谷歌的数字签名。
- **责任分离**：谷歌负责**认证**（你是谁），Canva负责**授权和会话管理**（你在Canva里能做什么）。

这就是一个将OAuth 2.0（用于授权流程和Access Token）和OpenID Connect（用于身份认证和ID Token）完美结合的生动实践。