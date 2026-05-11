<div align="center">

# ReqRadar

**需求透镜 — AI 编程时代的项目需求中间层**

**业务即产品**：统一团队对需求的理解口径，为每位开发者的 AI 编码助手提供一致、准确的项目上下文

[![Version: 0.8.0](https://img.shields.io/badge/version-0.8.0-blue.svg)](https://github.com/easy12138s/reqradar/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

</div>

---

## 为什么需要 ReqRadar

在 AI 编程时代（Cursor / Windsurf / Copilot），每个开发者都在用 AI 写代码。但问题在于：

- **需求理解不一致**：10 个开发者对同一需求有 10 种理解
- **上下文缺失**：AI 编码助手不知道项目的业务背景、术语定义、历史决策
- **重复劳动**：每个人都要花时间向 AI 解释"这个项目是做什么的"

ReqRadar 解决的核心问题：**统一需求口径，让 AI 编码助手获得一致的项目上下文**

---

## 核心能力

- **结构化需求分析** — AI Agent 自动提取术语、检索代码、识别风险，生成标准化需求文档
- **自定义报告模板** — 灵活配置报告结构和内容，适配不同团队的评审流程
- **项目记忆系统** — 积累领域知识库（术语表、模块关系、历史经验），越用越懂你的项目
- **多格式文档支持** — PDF / DOCX / PPTX / XLSX / HTML / Markdown 等 15+ 种格式自动解析
- **隐私优先架构** — 本地部署，支持 OpenAI / Ollama / 自定义 LLM 接口
- **MCP 模式集成** — 以 MCP Server 形式运行，让 Cursor / Windsurf 等工具直接获取项目需求上下文

---

## 使用示例：一次完整的需求开发流程

### 场景：产品经理提出"实现用户登录功能"

#### 第一步：提交需求到 ReqRadar

产品经理将需求描述（或 PRD 文档）提交给 ReqRadar：

```
输入: "用户需要能够通过邮箱和密码登录系统，
      登录后能查看个人信息，支持记住登录状态。
      安全要求：密码必须加密存储，连续失败5次锁定账户。"
```

#### 第二步：ReqRadar 自动分析需求

AI Agent 自动执行以下操作：

1. **术语提取与标准化**
   - "用户登录" → 映射到 `user_login` / `authentication` / `login_module`
   - "邮箱和密码" → 识别为 credential-based authentication
   - "记住登录状态" → 对应 session/token persistence (JWT/Redis Session)
   - "加密存储" → bcrypt hashing + salt
   - "锁定账户" → brute-force protection, rate limiting

2. **代码库匹配**
   - 发现已有 `src/auth/login.py`（部分实现）
   - 找到 `models/user.py` 已有 User model
   - 检测到缺少 password reset flow 和 2FA 相关代码

3. **风险识别**
   - **安全风险**: 未提及 CSRF protection for login form
   - **影响范围**: 需修改 auth module, 新增 rate limiter middleware, 更新 User schema
   - **依赖风险**: 当前使用 JWT v1，建议评估是否升级到 v2 (refresh token rotation)

4. **生成结构化报告**
   
   **决策摘要（给产品经理）**:
   ```
   需求清晰度: 85% ✅
   实现复杂度: 中等
   建议工期: 3-5 天
   主要风险: CSRF防护缺失、密码策略需确认
   待定问题: 是否支持第三方登录(GitHub/Google)？
   ```

   **技术细节（给开发者）**:
   ```
   涉及模块:
   - src/auth/ (新增 login handler, rate limiter)
   - models/user.py (新增 failed_login_count 字段)
   - middleware/security.py (新增 CSRF check)
   
   数据库变更:
   - ALTER TABLE users ADD COLUMN failed_attempts INTEGER DEFAULT 0
   - ALTER TABLE users ADD COLUMN locked_until TIMESTAMP
   
   API 端点:
   POST /api/auth/login (已存在，需增强)
   POST /api/auth/logout (已存在)
   POST /api/auth/password-reset (新增)
   ```

#### 第三步：开发者基于分析结果开始编码

此时，开发者打开 Cursor 开始实现：

```cursor
// 开发者无需手动解释背景，因为 ReqRadar 已经提供了完整的上下文

// 通过 MCP 直接获取需求分析结果：
@reqradar get-requirement-context --task-id=login-001

// Cursor 自动获得：
// 1. 标准化的术语定义（user_login = email+password认证）
// 2. 已有代码位置（auth/login.py 第45行）
// 3. 需要修改的文件清单
// 4. 安全要求 checklist
// 5. 数据库 schema 变更

// 开发者直接开始写代码，AI 助手已经"理解"了这个需求的全部上下文
```

#### 第四步：持续追问与迭代

开发过程中遇到问题？

```cursor
@reqradar ask "这个项目的认证机制是用 session 还是 jwt？"
→ 回答: "当前使用 JWT (HS256)，token 存储在 localStorage，
  有效期24小时，配置在 .reqradar.yaml 的 llm.jwt.secret_key"

@reqradar ask "之前有没有类似的登录功能实现过？"
→ 回答: "是的，2024年1月有过 v1.0 实现（见 analysis-042）， 
  但后来因安全审计发现 XSS 漏洞在3月重写了。
  建议：参考当时的 decision log（decision-015），避免重复踩坑"
```

---

## 快速开始

```bash
pip install reqradar && reqradar serve
```

启动后访问 http://localhost:8000/app/

默认账号: `admin@reqradar.io` / `Admin12138%`

---

## 主要功能

| 功能 | 说明 |
|------|------|
| LLM 配置 | 支持 OpenAI / Ollama / 自定义 API，一键测试连通性 |
| 项目管理 | ZIP 上传或 Git 克隆，自动索引代码和文档 |
| 需求提交 | 文本输入或多文件上传，支持 15+ 种文档格式 |
| 实时分析 | WebSocket 进度推送 + AI 对话追问 |
| 项目画像 | AI 生成技术栈、模块结构、术语表，可编辑可共享 |
| 团队协作 | 多用户支持，权限管理，记忆共享 |
| MCP 集成 | 为 Cursor / Windsurf / Copilot 提供标准化的需求上下文接口 |

---

## 系统要求

- Python 3.12 或更高版本
- 4GB+ RAM
- OpenAI API Key 或 Ollama（本地运行无需 GPU）

---

## 其他安装方式

<details>
<summary>Docker / 源码 / 部署脚本</summary>

```bash
# Docker（推荐生产环境）
cd docker && docker-compose up -d

# 源码安装
git clone https://github.com/easy12138s/reqradar.git
cd reqradar && poetry install && poetry run reqradar serve

# 一键部署脚本
./scripts/deploy.sh        # Linux/macOS
.\scripts\deploy.ps1      # Windows PowerShell
```

</details>

---

## 适用场景

- **新功能评审**：在写代码前，用 AI 分析需求的完整性和风险
- **需求澄清会议**：生成结构化报告，统一团队对需求的理解
- **技术方案评估**：自动匹配代码库和历史记录，评估影响范围
- **项目交接**：通过项目画像和记忆系统，快速传递业务上下文
- **AI 辅助编程**：为 Cursor / Windsurf 等工具提供标准化的需求接口，减少重复解释成本

---

## 许可证与贡献

MIT License | [贡献指南](CONTRIBUTING.md) | [问题反馈](https://github.com/easy12138s/reqradar/issues)

<div align="center">

如果这个项目对你有帮助，欢迎 Star 支持！

</div>
