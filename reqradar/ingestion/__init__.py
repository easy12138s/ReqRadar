"""Ingestion 模块 — 文档/代码/Git 数据摄取核心逻辑。

子模块：
  parsers/       — 文档解析器 (markitdown)、代码解析器 (AST)、Git 解析器 (git log)
  chunking/      — Markdown 切分器
  vectorizer.py  — ChromaDB 向量化
"""
