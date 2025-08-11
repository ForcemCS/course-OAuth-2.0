## Application Identity

**授权码流程 (Authorization Code Flow)** 以及它的安全增强——**PKCE**和**重定向URI (Redirect URI)**

核心是“**应用身份 (Application Identity)**”。就像用户有身份一样，每个向授权服务器发起请求的应用（Client）也有自己的身份。这个身份主要由`client_id`来标识。但关键问题是：**如何证明你就是你所声称的那个应用？**

我们通过一个场景进行说明：

**我们的故事：**

- **你**：用户张三。
- **你的应用 (Client)**：一个在手机上安装的第三方笔记应用，叫做 **“SuperNotes”**。它是一个**公共客户端 (Public Client)**。
- **你想做的事**：你想让SuperNotes能够读取并保存笔记到你的**谷歌云盘 (Google Drive)**。
- **授权服务器 (Authorization Server)**：**Google的账户和授权服务** (`accounts.google.com`)。

------

### 第零步：准备工作 (SuperNotes开发者做的)

SuperNotes的开发者在Google API控制台注册了他的应用。

- 他获得了一个 **`client_id`**：`12345-supernotes.apps.googleusercontent.com` (这是公开的)。
- 他将应用类型设置为 **“公共客户端 (Public Client)”**，所以**没有`client_secret`**。
- 他注册了一个极其重要的 **`redirect_uri`**：`https://auth.supernotes.app/google/callback`。这是他自己服务器上的一个地址，并且他通过了Google的域名验证，证明`supernotes.app`这个域名归他所有。

------

### 第一步：张三发起授权，SuperNotes生成PKCE凭证

1. 张三在SuperNotes应用里，点击了“连接到Google Drive”按钮。

2. 在SuperNotes的**代码内部**（在张三的手机上运行），立刻发生了两件事：

   - 生成`code_verifier`：SuperNotes的程序生成了一个非常长、非常随机的秘密字符串。

     > **`code_verifier`**: `a_very_long_and_random_secret_string_that_only_supernotes_knows_for_this_session`

   - 生成`code_challenge`：程序对上面的

     ```
     code_verifier
     ```

     进行SHA256哈希运算，得到一个“指纹”。

     > **`code_challenge`**: `hashed_fingerprint_of_the_verifier_string` (这个指纹无法被反向计算出原始的`code_verifier`)

3. SuperNotes现在要**把张三送到Google去**。它构建了一个URL，并让手机的浏览器打开它。这个过程就是**前通道 (Front Channel)** 的开始。

   > **URL内容**:
   > `https://accounts.google.com/o/oauth2/v2/auth?`
   > `response_type=code`
   > `& client_id=12345-supernotes.apps.googleusercontent.com` *(我是谁)*
   > `& scope=https://www.googleapis.com/auth/drive.file` *(我想要什么权限：读写你自己的文件)*
   > `& redirect_uri=https://auth.supernotes.app/google/callback` *(完事后请把用户送回这里)*
   > `& code_challenge=hashed_fingerprint_of_the_verifier_string` *(这是我的“任务指纹”)*
   > `& code_challenge_method=S256` *(我用的是SHA256算法)*
   > `& state=random_string_xyz` *(一个随机值，防止CSRF攻击)*

------

### 第二步：张三在Google上授权

1. 张三的浏览器跳转到了`accounts.google.com`。

2. 他看到了熟悉的谷歌登录页面，输入了他的谷歌账号和密码。

3. 接着，他看到了**同意页面 (Consent Screen)**：“**SuperNotes** 正在申请 **查看、修改、创建和删除您的Google云端硬盘中的特定文件** 的权限。您同意吗？”

4. 张三点击了“同意”。

5. **Google的授权服务器 (Authorization Server)** 现在做了几件重要的事：

   - 它生成了一个一次性的

     授权码 (Authorization Code)

     > **`Authorization Code`**: `4/0AeaYSHB_a_very_long_and_temporary_code`

   - 它在自己的数据库里，把这个`code`和之前收到的`code_challenge`**绑定**在了一起。它心里记着：“谁要用这个`code`，就必须拿出能生成这个`code_challenge`的原始秘密。”

   - 它把张三的浏览器**重定向**回SuperNotes预先注册的`redirect_uri`。

   > **重定向URL内容**:
   > `https://auth.supernotes.app/google/callback?`
   > `code=4/0AeaYSHB_a_very_long_and_temporary_code`
   > `& state=random_string_xyz` *(把之前收到的state原样送回，让SuperNotes确认这是它自己发起的流程)*

------

### 第三步：SuperNotes交换令牌 (Token)

1. 张三的手机浏览器自动跳转到了`https://auth.supernotes.app/google/callback...`。SuperNotes的应用捕获了这个跳转，并从URL中提取出了**授权码 (`code`)**。

2. 现在，SuperNotes的应用要通过**后通道 (Back Channel)** 去换取真正的**访问令牌 (`Access Token`)**。它向Google的令牌端点发起一个**HTTPS POST请求**。

   > **POST请求的目标**: `https://oauth2.googleapis.com/token`
   >
   > **POST请求的正文 (Body)**:
   > `{`
   > `"grant_type": "authorization_code",`
   > `"code": "4/0AeaYSHB_a_very_long_and_temporary_code",` *(这是我拿到的临时凭证)*
   > `"redirect_uri": "https://auth.supernotes.app/google/callback",` *(我当初是从这里发起的)*
   > `"client_id": "12345-supernotes.apps.googleusercontent.com",`
   > `"code_verifier": "a_very_long_and_random_secret_string_that_only_supernotes_knows_for_this_session"` *(**这是我的“秘密暗号”！**)*
   > `}`

3. **Google的授权服务器 (Authorization Server)** 收到了这个**后通道**请求。它开始进行**PKCE验证**：

   - 首先，根据收到的`code`，找到之前存下的`code_challenge`。
   - 然后，它拿起请求中发来的`code_verifier`，用SHA256算法对它进行哈希运算。
   - **它比较自己计算出的哈希值，和当初存下的`code_challenge`是否完全一样。**
   - **如果一样**，Google就放心了：“太好了！来换令牌的，就是当初发起请求的那个应用，`code`没有被小偷偷走后冒用。”

4. 验证通过后，Google通过这个安全的**后通道**连接，返回一个JSON响应给SuperNotes的应用。

   > **JSON响应内容**:
   > `{`
   > `"access_token": "ya29.A0AR...a_super_secret_and_powerful_token",` *(**这就是通行证！**)*
   > `"expires_in": 3599,` *(有效期约1小时)*
   > `"refresh_token": "1//04...another_long_term_token",` *(用于以后刷新通行证)*
   > `"scope": "https://www.googleapis.com/auth/drive.file",`
   > `"token_type": "Bearer"`
   > `}`

------

### 第四步：SuperNotes使用令牌

1. SuperNotes的应用安全地存储了这个`access_token`。

2. 现在，当张三在SuperNotes里写完一篇笔记，点击“保存到Google Drive”时，SuperNotes的应用就会向**Google Drive的API（资源服务器, Resource Server）** 发起一个请求。

   > **API请求**:
   > `POST https://www.googleapis.com/upload/drive/v3/files`
   >
   > **HTTP请求头 (Headers)**:
   > `Authorization: Bearer ya29.A0AR...a_super_secret_and_powerful_token` *(出示通行证)*
   > `Content-Type: application/json`
   >
   > **HTTP请求体 (Body)**:
   > `{ "name": "我的笔记.md", ... }`

3. Google Drive的API服务器收到请求，看到`Authorization`头里的令牌，验证其有效性后，成功地将文件保存到了张三的云盘里。

这个完整的例子展示了所有关键概念是如何协同工作的，特别是PKCE如何通过`code_verifier`和`code_challenge`这对“暗号”和“指纹”，为没有`client_secret`的公共客户端提供了一层至关重要的安全保护。