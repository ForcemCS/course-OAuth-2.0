## Defining Scopes for your API

**API开发者最需要发挥创造力和业务理解力的环节：如何为你的API设计`scope`**。

**没有标准答案，只有指导原则。`scope`的设计完全取决于你的业务，但好的`scope`设计能极大地提升你系统的安全性和灵活性。**

### 核心前提：`scope`的本质

- **`scope`只是一个字符串**：OAuth规范本身不关心这个字符串是什么，`read`、`write`、`a:b:c`、`https://...` 都可以。它的**含义完全由你的API来解释和执行**。
- **`scope`是应用的“请求”**：它不是用户的“能力”，而是应用为了完成特定任务，向用户申请的“临时许可”。
- **API是最终的执行者**：授权服务器只负责记录和颁发带有`scope`的令牌。最终，是你的API代码需要检查令牌中的`scope`，并以此来决定是否允许某个操作。

------

### `scope`的设计原则与模式

虽然没有硬性规定，但课程通过分析业界实践，总结出了几种常见且有效的设计模式和指导原则。

#### 1. 格式与命名约定 (Formatting)

- **简单单词**：使用简短、易于理解的单词，比如`read`, `write`, `profile`。
- 命名空间/层级：为了避免冲突和增加结构性，可以使用分隔符。
  - **下划线**：`repo_deployment` (GitHub)
  - **冒号**：`server:read`, `server:reboot` (你的游戏运维平台可以这样设计)
  - **点号**：`contacts.readonly` (Google)
  - **URL格式**：`https://api.example.com/data.read`
- **结论**：选择哪种格式不重要，重要的是**保持一致性**，并**清晰地文档化**，让应用开发者知道该用哪个。

#### 2. 最基础的设计：读/写分离 (Read vs. Write)

> 如果别的都不加，这是你应该添加的最基本的scope。

- **这是最简单、也最有效的权限分割**。
- **`scope=read`**: 允许应用执行所有只读操作。
- **`scope=write`**: 允许应用执行所有修改性操作（创建、更新、删除）。
- **例子 (Twitter)**：一个第三方Twitter客户端，默认可能只申请`read`权限，这样它可以显示你的时间线。如果你想用它来发推，它就需要额外申请`write`权限，并且这会在同意页面上明确告知你。

#### 3. 基于“敏感度”的设计 (Restricting Access to Sensitive Information)

- **原则**：识别出你API中那些处理敏感信息或执行高风险操作的端点，并为它们创建专门的`scope`。
- “敏感”的定义：
  - **返回敏感信息**：比如返回用户的家庭住址、完整的交易历史。
  - **修改敏感信息**：比如修改用户的信用卡信息、账单地址。
- 例子：
  - `read:profile` (读取公开资料) vs. `read:address` (读取私密地址)
  - `update:profile` (更新昵称) vs. `update:billing` (更新支付信息)
- **好处**：应用可以只申请它真正需要的最小权限，避免了“过度授权”。一个只需要显示用户昵称的应用，就不应该被授予访问用户家庭住址的权限。

#### 4. 基于“功能模块”的设计 (Segmenting Unrelated Parts of an API)

- **原则**：如果你的API非常庞大，包含了多个互不相关的业务模块，你应该为每个模块设计独立的`scope`体系。
- 例子 (Google)：这是一个完美的范例。
  - `Gmail API`有自己的scope体系 (如`gmail.send`, `gmail.readonly`)。
  - `Calendar API`有自己的scope体系 (如`calendar.events.readonly`)。
  - `YouTube API`也有自己的scope体系 (如`youtube.upload`)。
- 好处：
  - **实现了极高的隔离性**。一个申请了“上传视频到YouTube”权限的应用，绝对不可能用同样的令牌去“发送你的Gmail邮件”。
  - 这对于构建一个庞大的API生态系统至关重要。

#### 5. 基于“金钱成本”的设计 (Restricting Billable Actions)

- **原则**：任何可能导致用户**产生费用**的操作，都应该被一个专门的、高风险的`scope`所保护。
- 例子 (Amazon Web Services - AWS)：
  - `ec2:RunInstances`：这个API操作会创建一台新的云服务器，这会**立刻开始计费**。
- 好处：
  - **明确的用户告知**：当应用申请这个`scope`时，同意页面上必须清晰地告知用户：“此应用将能够创建需要付费的资源，这可能会导致您的账户产生费用。”
  - 这给了用户一个明确的警告和最终的控制权，防止恶意或有bug的应用在用户不知情的情况下“烧掉”他们的钱。

### 总结：如何为你的游戏运维平台设计Scope

为你提供了设计`scope`的“工具箱”。对于你的游戏运维平台，你可以这样思考：

1. 基础层（读/写分离）：
   - `server:read`: 查看服务器列表、状态、日志。
   - `server:write`: 创建、删除服务器。
2. 功能模块层：
   - **服务器管理**：`server:read`, `server:reboot`, `server:shutdown`
   - **用户管理**：`player:read`, `player:ban`, `player:unban`
   - **日志系统**：`logs:read`, `logs:search`
   - **账单系统**：`billing:read` (查看账单), `billing:charge` (发起扣费)
3. 敏感度层：
   - `billing:charge` 就是一个典型的“金钱成本”和“高敏感度”的scope，应该被特殊对待。

最终，`scope`的设计是你作为API架构师，对你的业务进行**深度理解和抽象**的结果。一个好的`scope`设计，能让你的API在未来的发展中，保持高度的安全性、灵活性和可扩展性。