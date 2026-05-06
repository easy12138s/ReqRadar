# ReAct 循环重构 & 记忆自进化 设计文档

> 日期: 2026-05-06
> 版本: v0.7.0

---

## 一、问题诊断

对当前 `agent/` 目录逐行审查，发现以下核心问题：

### 致命缺陷

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| 1 | **维度状态机断裂**：`mark_sufficient()` 从未被调用，`all_sufficient()` 永远返回 False，循环总是跑满 max_steps | `dimension.py:27`, `runner.py:63` | 维度追踪系统形同虚设，无法提前终止 |
| 2 | **系统提示词仅构建一次**：循环前构建，维度状态信息全程不过期 | `runner.py:176` | LLM 始终看到过时的维度状态 |
| 3 | **无链断裂检测**：LLM 可能持续调用工具但从不在本轮产出 JSON | `tool_use_loop.py:57-78` | 进入无限空转 |

### 显著缺陷

| # | 问题 | 位置 |
|---|------|------|
| 4 | 提示词缺乏策略指导：无工具选择策略、无维度充分性定义、无阶段引导 | `prompts/analysis_phase.py:3-21` |
| 5 | ANALYZE_SCHEMA 14 个顶层字段，LLM 认知负荷过大 | `schemas.py:104-264` |
| 6 | Token 预算仅统计工具返回文本（`len(text)//3`），不统计对话历史膨胀 | `tool_call_tracker.py:11` |
| 7 | `update_agent_from_tool_result` 仅处理 terms/impact_modules/risks 三类 | `runner.py:52-87` |
| 8 | 内外双层循环边界模糊，各自有终止条件 | `runner.py:190`, `tool_use_loop.py:57` |
| 9 | 记忆更新完全缺失：`update_from_analysis()` 是死代码，分析成果从不回写 | `memory.py:442` |

---

## 二、目标架构

### 2.1 新循环结构（单层统一循环）

```
run_react_analysis(agent, llm_client, tool_registry):

    while True:
        step += 1

        1. 动态构建系统提示词（当前阶段 + 维度状态 + 项目记忆）
        2. 构建用户提示词（CoT 模板 + 薄弱维度缺口）
        3. 单次 LLM 调用（tool_calls + 结构化输出并存）
        4. 若有工具调用 → 执行工具 + 追加结果 → continue
        5. 若有结构化输出 → 更新 agent（维度状态 + 证据）
        6. 终止检查（LLM 自声明 或 max_steps 或 连续空步）
        ↓
    循环结束 → 最终报告生成 → 记忆自进化 → 返回

关键变化：
- 去掉 tool_use_loop.py（内层子循环）
- 系统提示词每步动态重建
- LLM 自主声明终止（final_step=true）
- 中间输出用轻量 schema（5 字段），最终报告用完整 schema
```

### 2.2 提示词体系

#### 系统提示词（分节组织，每步动态重建）

```
## 角色
专业需求分析架构师，通过"思考→行动→评估"循环完成分析。

## 分析阶段引导
阶段1 理解与提取 → 优先工具: get_terminology, search_requirements, get_project_profile
阶段2 范围定位   → 优先工具: search_code, read_file, list_modules, get_dependencies
阶段3 风险评估   → 优先工具: read_file, search_code, get_contributors
阶段4 综合建议   → 优先工具: read_file, get_project_profile

## 工具速查
[9 种工具的简要说明和参数]

## 维度充分性标准
understanding: ≥1 术语定义 + 需求拆解 → sufficient
impact: ≥2 受影响模块/文件，有路径和理由 → sufficient
risk: ≥2 结构化风险 → sufficient
change: ≥2 变更评估 → sufficient
decision: 决策总结 + ≥1 建议项 → sufficient
evidence: ≥3 条不同来源证据 → sufficient
verification: ≥3 条验证要点 → sufficient

## 当前上下文
项目记忆 / 用户偏好 / 历史需求 / 维度状态 / 上轮遗留计划
```

#### 用户提示词（CoT 模板）

```
## 需求
{requirement_text}

## 当前进度
步骤 {step}/{max_steps} | 维度缺口: {weak} | 证据数: {count}

## 按以下步骤思考
第一步 — 理解当前状态：回顾证据，判断当前阶段和维度缺口
第二步 — 选择行动：选择 1-3 个工具，说明目的
第三步 — 评估结果：审查工具返回，更新维度状态

## 输出格式
需收集信息 → tool_calls + analysis 字段
维度已达标 → final_step=true + 总结性评估
```

### 2.3 中间输出 Schema

```python
STEP_OUTPUT_SCHEMA = {
    "name": "step_assessment",
    "parameters": {
        "type": "object",
        "properties": {
            "reasoning": {"type": "string"},
            "dimension_status": {"type": "object",  # 7 维度，每维度 sufficient/in_progress/insufficient
                "properties": {dim: {"type": "string", "enum": ["insufficient", "in_progress", "sufficient"]}
                               for dim in DEFAULT_DIMENSIONS}},
            "key_findings": {"type": "array", "items": {"type": "object", "properties": {
                "dimension": {"type": "string"}, "finding": {"type": "string"},
                "confidence": {"type": "string", "enum": ["low", "medium", "high"]}
            }}},
            "next_actions": {"type": "array", "items": {"type": "object", "properties": {
                "priority": {"type": "integer"}, "action": {"type": "string"},
                "reason": {"type": "string"}, "suggested_tools": {"type": "array", "items": {"type": "string"}}
            }}},
            "final_step": {"type": "boolean"},
        },
        "required": ["reasoning", "dimension_status"],
    },
}
```

### 2.4 维度状态机

| 状态 | 触发条件 | 来源 |
|------|----------|------|
| pending → in_progress | 首次记录该维度的证据 | `record_evidence()` |
| in_progress → sufficient | LLM 在 `dimension_status` 中声明 sufficient | `update_agent_from_step_result()` |
| sufficient 回退 → in_progress | LLM 后续发现新缺口，主动在 dimension_status 中降级 | LLM 自管理 |
| 任意状态 → 强制终止 | max_steps 或连续 3 空步 | `should_terminate()` |

### 2.5 终止条件

```python
def should_terminate(agent):
    if agent._cancelled: return True
    if agent.step_count >= agent.max_steps: return True
    if agent._llm_declared_terminal: return True      # LLM 说够了
    if agent.dimension_tracker.all_sufficient(): return True  # 兜底
    if agent._consecutive_empty_steps >= 3: return True
    if agent._consecutive_failures >= 3: return True
    return False
```

### 2.6 边界处理

| 场景 | 策略 |
|------|------|
| LLM 持续工具调用不产出评估 | 不强制中断，`max_steps` 做绝对上限 |
| LLM 声明 final_step 但维度有缺口 | 注入一次软性提醒，LLM 坚持则信任 |
| Token 预算控制 | 单次工具返回 4000 字符截断；历史>10条消息时保留 system + 最近 3 轮 |
| 工具执行异常 | 返回错误字符串，不中断循环 |
| LLM 连续 3 步无 key_findings | 终止循环 |
| LLM 连续 3 次调用失败 | 终止循环 |
| LLM 输出格式错误 | 提示注入 "请输出 JSON"，连续 2 次则降级纯文本模式 |
| 深度自适应 | quick=10/standard=15/deep=25 步，quick 模式提示词标注 "快速模式" |

### 2.7 工具调用去重与预算

保留 `ToolCallTracker`，简化为去重 + 计数：

```python
class ToolCallTracker:
    def is_duplicate(tool_name, args) -> bool  # 精确去重
    def track(tool_name, args) -> None
    def is_over_limit() -> bool  # 同工具最多调用次数限制
```

去掉旧的 token 预算估算（`len(text)//3`），改为单结果截断（4000 字符）。

---

## 三、记忆自进化

### 3.1 流程

```
分析完成 → 提取候选知识（规则驱动，无 LLM）
         → 加载已有 ProjectMemory
         → 一次 LLM 调用（CoT 比对 + 更新）
         → 执行更新操作（ProjectMemory 方法）
         → 写入 changelog
```

### 3.2 候选知识提取

从 `agent.final_report_data` + `agent.evidence_collector` 提取：

| 类别 | 来源 | 提取字段 |
|------|------|----------|
| terms | `report["terms"]` | term, definition, domain |
| modules | `report["impact_modules"]` | name, responsibility, key_classes |
| constraints | `report["structured_constraints"]` | description, type |
| tech_stack | `impact_domains` 推断 | languages, frameworks, databases |
| overview | `report["technical_summary"]` | overview text |

### 3.3 CoT Prompt 设计

```
第1步 — 逐条比对：对每条候选 vs 已有记忆，判断 add/update/skip/merge
第2步 — 控制质量：term定义≥10字、module名称来自代码路径、constraint有具体描述
第3步 — 输出操作列表
```

### 3.4 输出 Schema

```python
MEMORY_EVOLUTION_SCHEMA = {
    "name": "evolve_memory",
    "parameters": {
        "type": "object",
        "properties": {
            "comparisons": {"type": "array", "items": {"type": "object", "properties": {
                "category": {"type": "string"}, "candidate_key": {"type": "string"},
                "existing_match": {"type": "string"}, "action": {"type": "string"}, "reason": {"type": "string"}
            }}},
            "operations": {"type": "array", "items": {"type": "object", "properties": {
                "target": {"type": "string"}, "action": {"type": "string"}, "data": {"type": "object"}
            }}},
            "changelog_entry": {"type": "string"},
        },
        "required": ["operations", "changelog_entry"],
    },
}
```

### 3.5 安全设计

| 风险 | 对策 |
|------|------|
| LLM 产生错误术语 | definition ≥ 10 字才写入 |
| 重复写入 | `batch_add_*()` 内部去重 |
| 污染模块列表 | 仅写入 relevance ≥ medium 的模块 |
| LLM 失败 | 静默失败，不影响主流程 |
| 记忆无限膨胀 | terms/modules 各上限 200 条 |

### 3.6 配置

`config.yaml` 新增：
```yaml
memory_evolution:
  enabled: true  # 默认开启
```

---

## 四、改动文件清单

| 文件 | 改动 | 行数估算 |
|------|------|----------|
| `agent/runner.py` | 重写主循环 | ~180 行 |
| `agent/prompts/analysis_phase.py` | 重写提示词构建 | ~120 行 |
| `agent/schemas.py` | 新增 STEP_OUTPUT_SCHEMA + MEMORY_EVOLUTION_SCHEMA | ~80 行 |
| `agent/tool_use_loop.py` | **删除**（功能合并到 runner.py） | — |
| `agent/tool_call_tracker.py` | 保留，简化 | ~30 行 |
| `agent/analysis_agent.py` | 新增字段 + 修改 should_terminate | ~20 行 |
| `agent/memory_evolution.py` | **新建** | ~120 行 |
| `agent/prompts/memory_evolution.py` | **新建** | ~50 行 |
| `infrastructure/config.py` | 新增 memory_evolution 配置 | ~5 行 |

**不改的文件**: `dimension.py`, `evidence.py`, `tools/` 全部, `prompts/report_phase.py`, `prompts/chatback_phase.py`, `prompts/project_profile.py`, 所有 `modules/`, `web/`, `cli/`

---

## 五、向后兼容

- `run_react_analysis()` 签名不变
- `AnalysisAgent`, `DimensionTracker`, `EvidenceCollector` 公共方法不变（仅新增字段）
- `generate_report()` 签名不变
- 外部调用方（CLI、Web service）无需任何改动
- 工具注册和执行逻辑不动
- 报告格式和 Jinja2 模板不动

---

## 六、风险

| 风险 | 概率 | 缓解 |
|------|------|------|
| CoT 提示词质量不足导致 LLM 误判阶段 | 中 | 保留 max_steps 兜底 + 空步检测 |
| LLM 自评估过于乐观（过早声明 sufficient） | 中 | agent 做软性提醒，仍信任 LLM |
| 记忆自进化写入错误术语 | 低 | definition 长度门 + 去重 |
| 重构引入回归 | 低 | 保留所有测试，新增循环单元测试 |
