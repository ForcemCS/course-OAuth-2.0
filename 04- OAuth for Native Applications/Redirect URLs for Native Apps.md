## Redirect URLs for Native Apps

**什么是 Native Applications (原生应用)？**

**原生应用** 指的是那些被编译成特定操作系统（如iOS, Android, Windows, macOS）的本地机器码，并直接安装在该操作系统上运行的应用程序。

这个范畴包括：

- 移动应用 (Mobile Apps)：
  - iOS应用 (用Swift/Objective-C编写)
  - Android应用 (用Kotlin/Java编写)
- 桌面应用 (Desktop Apps)：
  - Windows应用 (.exe文件，用C#, C++等编写)
  - macOS应用 (.app文件，用Swift/Objective-C等编写)
  - Linux应用

### 挑战一：无法安全存储`Client Secret`

这是移动应用与Web后端应用最根本的区别。

- **Web后端应用 (机密客户端)**：
  - 代码和`client_secret`都存放在你自己的、受保护的服务器上。最终用户无法接触到它们。
  - 因此，它可以用`client_secret`来向授权服务器证明自己的真实身份。
- **移动应用 (公共客户端)**：
  - **你写的代码最终会被编译打包，然后分发到成千上万个用户的手机上。**
  - 如果把`client_secret`硬编码到代码里，就意味着**你把这个“秘密”复制了成千上万份，并交给了每一个用户**。
  - 虽然用户不能直接“查看源代码”，但有专业技能的人可以使用**反编译工具 (decompiler)**、**字符串提取工具**等手段，从你的App安装包（`.apk`或`.ipa`文件）中把这个`client_secret`挖出来。
  - 一旦`client_secret`泄露，它就不再是秘密了。任何攻击者都可以用这个`secret`去冒充你的官方App，造成严重的安全问题。
- **解决方案**：
  - **坦然接受现实：干脆就不用`client_secret`！**
  - 正因为移动应用无法保密，所以现代的OAuth实践就是将移动应用归类为**公共客户端**，在注册时根本不为其分配`client_secret`。
  - 但这留下了一个问题：没有了`client_secret`，应用如何证明自己的身份，以及如何防止授权码被盗用呢？这正是PKCE要解决的问题。

### 挑战二：不可靠的重定向URI (Redirect URI)

这是移动应用独有的、更微妙的一个安全挑战。它涉及到用户授权后，如何安全地从**浏览器**环境“跳回”到你的**App**中。

在Web应用中，整个流程都在同一个浏览器标签页里发生，浏览器自身的安全机制（DNS验证、HTTPS证书验证）保证了重定向的相对安全。但在移动应用中，情况变得复杂：

- **流程**：你的App -> **启动一个应用内浏览器或系统浏览器** -> 用户在浏览器里登录Auth0 -> Auth0**尝试把用户和`code`送回你的App**。

这个“送回”的过程，主要有两种技术实现，它们各有安全隐患：

#### 1. 自定义URL方案 (Custom URL Scheme) - 旧的、不安全的方式

- **工作方式**：你的App向手机操作系统注册一个自定义的“协议”，比如 `mytodoapp://`。
- **例子**：当浏览器尝试访问 `mytodoapp://callback?code=...` 这个地址时，操作系统会发现这个协议，然后启动你的`MyTodoApp`，并将这个URL传递给它。
- 安全漏洞（致命的）：
  - **没有中央注册机构**：这个`mytodoapp://`协议是你自己随便起的，**任何其他App也可以声称自己能处理这个协议**。
  - **“协议冲突”和“劫持”**：如果一个恶意App也注册了`mytodoapp://`，当用户手机上同时安装了你的App和恶意App时，系统在收到这个重定向后，**哪个App会被唤醒是不确定的**（不同操作系统行为不同）。
  - **结果**：恶意App有很大机会可以**“抢”在你的App之前截获这个重定向**，从而偷走URL里携带的宝贵的`Authorization Code`。

#### 2. “应用声明的URL模式” (App-claimed URL Patterns) - 新的、更安全的方式

**工作方式**：也叫**深度链接 (Deep Linking)**、**应用链接 (App Links - Android)** 或 **通用链接 (Universal Links - iOS)**。

#### 它是如何工作的？为什么更安全？

这个机制的精髓在于**双向验证**，建立了一个**手机App**和**网站域名**之间不可伪造的信任关系。用JD商城举例说明

##### 1. 京东App的“声明”

- 京东的iOS和Android开发团队，在他们的App代码里配置了：“我的App可以处理所有指向 `*.jd.com` 和 `*.jd.hk` 等域名的链接。”

##### 2. 京东网站的“证明” (最关键的一步)

- 光App自己说没用，必须得到网站的官方认可。

- 京东的网站运维团队，必须在 jd.com` 这个域名的服务器根目录

  下，放置一个特定的小文件。

  - **对于iOS (Universal Links)**：这个文件必须在 `https://jd.com/.well-known/apple-app-site-association`。
  - **对于Android (App Links)**：这个文件必须在 `https://jd.com/.well-known/assetlinks.json`。

- 这个文件里的内容，是用**数字签名**加密过的，它声明了：“我，`jd.com`这个网站，**正式授权**那个Bundle ID为`com.360buy.jdmobile`的iOS应用（或者包名为`com.jingdong.app.mall`的Android应用）来处理我的链接。”

##### 3. 手机操作系统的“验证与绑定”

- 当你从App Store或应用商店**安装京东App**时，你的手机操作系统（iOS/Android）会自动去访问 `https://jd.com/`，下载并验证上面说的那个`apple-app-site-association`或`assetlinks.json`文件。
- 验证通过后，操作系统就在你的手机本地建立了一个**绑定关系**：“`jd.com`的链接 <=> 京东App”。