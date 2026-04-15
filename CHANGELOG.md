# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-15

### Added

- Document loader framework: `DocumentLoader` ABC, `LoadedDocument`, `LoaderRegistry`
- TextLoader: migrated from CLI, supports .md/.txt/.rst with GBK fallback
- PDFLoader: pdfplumber-based, optional dependency (`pip install pdfplumber`)
- DocxLoader: python-docx-based, optional dependency (`pip install python-docx`)
- ImageLoader: LLM vision integration for UI screenshots (.png/.jpg/.jpeg/.gif/.bmp/.webp)
- ChatLoader: Feishu JSON + generic CSV chat record parsing
- `VisionConfig`: independent vision LLM configuration block (provider/model/api_key/base_url)
- `MemoryConfig`: project memory configuration (enabled/storage_path)
- `LoaderConfig`: loader configuration (chunk_size/chunk_overlap/format toggles)
- `MemoryManager`: per-project memory system (terminology/team/analysis_history)
  - Auto-accumulates terminology extracted from analysis
  - Auto-records team members from Git contributors
  - Persists analysis history (capped at 50 records)
  - Terminology injection into step_extract prompt
  - Post-generate hook updates memory after each analysis
- `complete_vision()` method on OpenAIClient for image understanding
- `create_vision_client()` factory function
- `VisionNotConfiguredError`: clear error when vision is needed but not configured
- `LoaderException` exception class
- CLI `index` command refactored to use LoaderRegistry (supports all file types)

### Changed

- `AnalysisContext` now includes `memory_data` field for project memory injection
- `step_extract` injects known project terminology into LLM prompt
- `analyze` command loads memory before pipeline and updates it after
- `.reqradar.yaml.example` updated with vision, memory, and loader config sections

### Removed

- `infrastructure/errors.py`: dead code, superseded by `core/exceptions.py`

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