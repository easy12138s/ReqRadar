# V1 → V2 四层模型数据迁移方案

## 1. 概述

本文档定义从 V1 单体数据库迁移到 V2 四层认知资产模型的完整方案。

### 1.1 迁移范围

| V1 来源 | V2 目标 | 说明 |
|---------|---------|------|
| `project_memory` JSON | L3-A `glossary` + `module_profile` + `architecture_constraint` | 术语表拆分为独立表，模块画像和约束分离 |
| `user_memory` JSON | L3-A `decision_record` | 用户偏好沉淀为决策记录 |
| `memory_evolution` 日志 | L3-A `risk_evolution` | 风险历史演化为风险演化记录 |
| V1 Evidence 快照 | L2 `evidence_records` | 保留原始证据，补充治理元数据 |
| V1 ReportVersion | L2 `report_versions` | 保留报告版本，关联到 V2 Session |

### 1.2 迁移原则

1. **只读迁移**：V1 数据只读不写，迁移脚本幂等可重跑
2. **字段级映射**：每个 V1 字段有明确的 V2 目标字段
3. **回滚支持**：每个迁移步骤有对应回滚操作
4. **分批执行**：按 L0 → L1 → L2 → L3 顺序，每批验证后再继续

---

## 2. 迁移脚本框架

### 2.1 脚本结构

```
scripts/migration/
├── migrate_v1_to_v2.py          # 主迁移入口
├── migrate_l0_raw_context.py    # L0: 原始上下文归档
├── migrate_l1_structured.py     # L1: 结构化事实索引
├── migrate_l2_records.py        # L2: 分析记录迁移
├── migrate_l3_knowledge.py      # L3: 知识沉淀迁移
├── validate_migration.py        # 迁移验证脚本
└── rollback_migration.py        # 回滚脚本
```

### 2.2 L3 迁移映射

#### project_memory → glossary

| V1 字段 | V2 字段 | 转换规则 |
|---------|---------|---------|
| `terms[].name` | `canonical_name` | snake_case 规范化 |
| `terms[].definition` | `definition` | 直接复制 |
| `terms[].aliases` | `aliases` | JSON 数组 |
| `terms[].confidence` | `confidence_score` | V1 3 级 → V2 0.0-1.0 |

#### project_memory → module_profile

| V1 字段 | V2 字段 | 转换规则 |
|---------|---------|---------|
| `modules[].name` | `module_name` | 直接复制 |
| `modules[].description` | `responsibility` | 直接复制 |
| `modules[].dependencies` | `dependencies` | JSON 数组 |
| `modules[].complexity` | `complexity_score` | 直接复制 |

#### project_memory → architecture_constraint

| V1 字段 | V2 字段 | 转换规则 |
|---------|---------|---------|
| `constraints[].rule` | `description` | 直接复制 |
| `constraints[].scope` | `scope` | 直接复制 |
| `constraints[].type` | `constraint_type` | 枚举映射 |

### 2.3 回滚操作手册

```bash
# 回滚 L3 迁移
python scripts/migration/rollback_migration.py --target l3 --project-id <uuid>

# 回滚 L2 迁移
python scripts/migration/rollback_migration.py --target l2 --project-id <uuid>

# 完全回滚
python scripts/migration/rollback_migration.py --target all --confirm
```

---

## 3. 验证检查清单

- [ ] V1 项目数 = V2 项目数
- [ ] V1 术语数 ≤ V2 术语数（合并后可能减少）
- [ ] V1 模块数 = V2 模块画像数
- [ ] V1 约束数 = V2 架构约束数
- [ ] 所有 V2 知识记录 `confidence_score >= 0.3`（迁移默认值）
- [ ] 所有 V2 知识记录 `freshness = 'active'`
- [ ] 迁移后 `pytest tests/` 全部通过
