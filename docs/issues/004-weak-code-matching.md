# Issue: 代码匹配停留在关键词层面，语义关联能力弱

**发现日期**: 2026-04-23
**严重级别**: 高
**影响范围**: 所有分析任务的影响评估步骤
**状态**: ✅ 已修复

## 现象

对于"配置系统重构"这个需求，代码匹配只命中了 4 个文件：

| 命中文件 | 匹配原因 |
|:---|:---|
| `infrastructure/config.py` | 文件名包含 "config" |
| `modules/llm_client.py` | 与 LLM 配置相关 |
| `agent/llm_utils.py` | 与 LLM 调用相关 |
| `core/exceptions.py` | 未知原因 |

**大量明显相关的文件完全没有命中**：

| 未命中文件 | 为什么应该命中 |
|:---|:---|
| `web/app.py` | CORS 配置、配置初始化 |
| `web/models.py` | 需要新增 Config 模型 |
| `web/api/analyses.py` | 文件上传限制配置 |
| `web/api/auth.py` | token 过期时间配置 |
| `web/api/projects.py` | 索引参数配置 |
| `web/services/analysis_runner.py` | 分析配置读取 |
| `web/database.py` | 新增表需要改 schema |
| `infrastructure/registry.py` | 配置注册 |

## 根因分析

1. **关键词匹配太窄** — `find_symbols()` 基于关键词字符串匹配（如"config"），无法理解语义
2. **无调用链分析** — 能匹配 `config.py`，但无法追踪 `config.py` → `analysis_runner.py` → `analyses.py` 的调用链
3. **无架构约束理解** — 无法理解"新增数据库表"意味着要改 `models.py` 和 `database.py`
4. **文件截断导致信息丢失** — `EXTRACT_PROMPT` 中需求文本硬截断 4000 字符，完整需求被截断

## 相关文件

- `src/reqradar/modules/code_parser.py` — `find_symbols()` 实现
- `src/reqradar/agent/steps.py` — `step_map_keywords`, `step_analyze`
- `src/reqradar/agent/smart_matching.py` — `_smart_module_matching`
- `src/reqradar/agent/prompts.py` — `EXTRACT_PROMPT` 截断逻辑

## 修复建议

### 短期
1. **改进关键词扩展** — 在 `KEYWORD_MAPPING_PROMPT` 中增加更多同义词和关联词
2. **放宽匹配阈值** — 增加 `max_code_files` 默认值
3. **修复文档截断** — 需求文档超过 4000 字符时做智能分块，而非简单截断

### 中期
4. **引入调用图分析** — 基于 AST 构建函数/类调用关系图，支持"谁调用了 X"的反向查询
5. **基于文件类型的默认关联** — 如需求提到"数据库模型"，自动关联 `models.py`, `database.py`, `alembic/` 等

### 长期
6. **语义搜索替代关键词匹配** — 用 embedding 做代码语义检索，而非字符串匹配
7. **架构规则引擎** — 定义规则如"新增 Model → 改 models.py + database.py + alembic migration"
