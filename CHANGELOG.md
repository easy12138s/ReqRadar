# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-14

### Added

- Initial MVP release of ReqRadar
- CLI commands: `reqradar index` and `reqradar analyze`
- Python code parser based on AST
- Vector search with Chroma + BGE-large-zh embedding model
- Git contributor analysis with weighted scoring algorithm
- LLM client supporting OpenAI and Ollama backends
- Fixed 5-step analysis pipeline (Read → Extract → Retrieve → Analyze → Generate)
- Jinja2-based Markdown report generation with fixed template
- Configuration system with YAML + Pydantic + environment variable support
- Structured logging with structlog
- Rich CLI progress display
- Graceful degradation when sub-modules fail
- Analysis context with confidence and completeness tracking

### Changed

- Nothing yet (first release)

### Deprecated

- Nothing yet

### Removed

- Nothing yet

### Fixed

- Nothing yet

### Security

- Nothing yet