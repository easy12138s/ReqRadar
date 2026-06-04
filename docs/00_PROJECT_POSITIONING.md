---

# ReqRadar 项目定位与未来方向

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 文档定位 | 项目愿景与设计哲学（重构宪法前置文档） |
| 用途 | 作为所有架构决策和重构计划的设计依据 |

---

## 一、项目定位（Project Positioning）

### 1.1 项目定义

ReqRadar 不是：

- AI 聊天机器人
- 通用 Agent 平台
- 自动编码工具
- 企业知识库
- RAG 问答系统
- Prompt Workflow 编排器

ReqRadar 的本质定位是：

> **面向软件工程领域的 Project Cognitive Runtime（项目认知运行时）**
>
> 一个围绕「需求 → 分析 → 决策 → 风险 → 证据 → 历史 → 组织记忆」构建的 AI-native 工程认知系统。

---

## 二、核心问题（ReqRadar 真正解决什么）

现代软件团队最大的损耗，往往不是代码不会写、工具不够多、模型不够强，而是：

> **组织认知持续流失**

具体表现为：为什么这样设计没人知道、哪些模块不能动没人知道、历史风险没人记得、需求演化无法追踪、隐式约束依赖口口相传、新成员理解项目成本极高、AI 只能理解代码无法理解项目。

ReqRadar 的目标不是替代开发者，而是：

> **将软件工程中的「组织认知」结构化、可追溯化、长期化。**

---

## 三、项目核心理念（Core Philosophy）

### 3.1 从「代码智能」走向「项目认知」

Coding Agent 关注：**如何修改代码 / 如何完成任务 / 如何执行操作**

ReqRadar 关注：**为什么这样设计 / 哪些风险正在积累 / 哪些历史决策不能破坏 / 哪些约束来自组织与业务 / 哪些需求会影响长期演化**

### 3.2 从「文档检索」走向「认知运行时」

ReqRadar 不是「文档搜索 + AI 问答」，而是「持续运行的项目认知系统」。

核心对象不是文档、chunk、embedding，而是：Cognitive Session、Evidence、Decision、Risk、Requirement Evolution、Organizational Memory。

---

## 四、核心价值主张

> **让组织不再失忆**

---

## 五、系统核心能力（Core Capabilities）

### 5.1 Requirement Intelligence（需求认知）

- 分析需求影响范围
- 识别潜在风险
- 建立需求与代码关系
- 追踪需求演化历史
- 形成需求证据链

### 5.2 Evidence-backed Cognition（证据驱动认知）

所有结论必须具备：

```
结论
← 推理过程
← 工具调用
← 代码证据
← 历史需求
← Git 历史
← 项目记忆
```

系统不输出「不可解释的 AI 判断」，而输出「可追溯的工程认知」。

### 5.3 Organizational Memory（组织记忆）

系统持续沉淀：历史决策、风险记录、需求上下文、架构约束、项目术语、演化路径、发布基线、历史事故经验。

### 5.4 Cognitive Runtime（认知运行时）

ReqRadar 的核心不是单次 Prompt，而是长期运行的认知状态机：

```
Cognitive Session / Context Pipeline / Event Stream
Checkpoint / Tool Runtime / Memory Evolution
```

---

## 六、与现有 AI 产品的差异

### 6.1 与 Coding Agent 的差异

| 维度 | Coding Agent | ReqRadar |
|------|-------------|----------|
| 核心目标 | 完成代码任务 | 建立项目认知 |
| 核心对象 | 文件/函数 | 项目/需求/风险 |
| 长期记忆 | 代码上下文 | 组织认知 |
| 输出 | 代码修改 | 认知分析 |
| 时间维度 | 当前任务 | 长期演化 |
| 核心能力 | 执行 | 理解与追溯 |

### 6.2 与企业知识库的差异

| 维度 | 企业知识库 | ReqRadar |
|------|----------|----------|
| 核心能力 | 搜索与问答 | 认知建模 |
| 数据对象 | 文档 | 工程系统 |
| 推理能力 | RAG | Runtime Cognition |
| 结构 | chunk | cognitive state |
| 时间维度 | 静态 | 演化 |
| 核心结果 | 信息 | 工程认知 |

---

## 七、系统未来演化方向（Roadmap Vision）

### Phase 1：需求分析 Agent（当前阶段）

能力：ReAct 分析、Evidence Chain、7 维度追踪、Requirement Analysis、向量检索、项目画像、Chatback

目标：建立「需求 → 风险 → 证据」分析能力

### Phase 2：Project Cognitive Runtime（V2 核心阶段）

核心升级：CognitiveSession、Event Stream、Context Pipeline、ToolRuntime、Checkpoint、Runtime State

目标：建立 AI-native 工程认知运行时

### Phase 3：Project Memory Evolution

核心升级：长期组织记忆、历史决策链、风险演化模型、Requirement Evolution Graph、发布谱系、架构演化历史

目标：建立「项目长期认知」

### Phase 4：Engineering Cognitive Infrastructure

从「需求分析系统」演化为「软件工程认知基础设施」：

- 工程认知图谱
- 风险演化网络
- 组织约束建模
- 决策追踪
- AI-assisted Architecture Reasoning
- 历史演化智能分析

---

## 八、核心技术方向（Technical Direction）

### 8.1 Runtime-first

系统核心不是 HTTP API，而是 AI Runtime。Runtime 将成为系统内核：Session / Event / Checkpoint / Context / Tool / Memory

### 8.2 Context Engineering

未来 Prompt 不再是 f-string 拼接，而是 Token-aware Context Pipeline：relevance scoring / compression / selection / memory injection / context budgeting

### 8.3 Evidence-driven AI

系统输出必须具备：证据 / 来源 / 推理链 / 风险依据 / 决策上下文

核心原则：**AI 不是「回答」，AI 是「可验证认知」**

### 8.4 Long-term Engineering Memory

建立工程组织长期认知层：architecture memory / requirement lineage / decision history / release evolution / incident memory / organizational constraints

---

## 九、项目战略边界

**不做**：通用 AI 平台 / AutoGPT 类 Agent OS / 通用 Workflow 编排 / AI 办公助手 / 全行业 Agent / 万能智能体

**聚焦**：软件工程组织认知——这是系统长期战略边界。

---

## 十、长期愿景（Long-term Vision）

未来的软件工程不再只是代码仓库，而是：

> **认知仓库**

ReqRadar 的长期愿景是成为软件团队的长期认知系统，不仅记录代码，更记录：为什么这样设计 / 哪些风险正在积累 / 哪些历史不能遗忘 / 哪些约束不能破坏 / 项目如何持续演化

最终形成：

> **AI-native Engineering Cognitive Infrastructure**

---

## 十一、最终定位（一句话版本）

| 维度 | 定位 |
|------|------|
| 技术定位 | AI-native Project Cognitive Runtime |
| 产品定位 | 面向软件工程领域的组织认知系统 |
| 长期定位 | Software Engineering Cognitive Infrastructure |

---
