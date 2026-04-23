# Issue: ChromaDB 版本不兼容导致索引失效

**发现日期**: 2026-04-23
**严重级别**: 中
**影响范围**: 向量检索功能
**状态**: ✅ 已修复

## 现象

运行 `reqradar analyze` 时，ChromaDB 报错：

```
sqlite3.OperationalError: no such column: collections.topic
```

## 根因分析

`.reqradar/index/vectorstore/` 目录中的 SQLite 数据库是用旧版 ChromaDB（~0.4.x）创建的。

当前 Poetry 环境安装的 ChromaDB 版本较新，schema 发生了变更（新增了 `collections.topic` 列等）。

## 临时修复

删除旧索引并重建：
```bash
rm -rf .reqradar/index/vectorstore
poetry run reqradar index -r ./src -o .reqradar/index
```

## 长期修复建议

1. **版本兼容性检测** — 启动时检查 ChromaDB 版本与索引版本是否匹配
2. **自动迁移** — 如果检测到版本不兼容，自动重建索引（或提供明确的错误提示）
3. **索引版本标记** — 在索引目录中写入 `version.json`，记录创建时的 ChromaDB 版本
4. **锁定 ChromaDB 版本** — 在 `pyproject.toml` 中精确锁定版本，避免升级导致不兼容

## 相关文件

- `src/reqradar/modules/vector_store.py` — `ChromaVectorStore.__init__`
- `pyproject.toml` — chromadb 依赖版本
