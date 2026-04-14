# IDE 集成支持

## 背景

ReqRadar 当前只能通过 CLI 使用，开发者需要在终端手动执行命令并查看报告。为了提升使用体验，需要将 ReqRadar 直接集成到开发者常用的 IDE 中（PyCharm 和 VS Code），使需求分析能力触手可及。

## 需求

1. **VS Code 扩展**：提供 VS Code 扩展，支持右键菜单触发分析、侧边栏查看报告、状态栏提示索引状态
2. **PyCharm 插件**：提供 PyCharm 插件，支持在编辑器中直接触发 reqradar analyze、内联显示分析报告
3. **配置文件识别**：IDE 自动识别 `.reqradar.yaml` 配置文件，提供语法高亮和配置补全
4. **报告预览**：在 IDE 内直接预览 Markdown 格式的分析报告，支持跳转到关联代码文件

## 技术约束

- VS Code 扩展使用 TypeScript + VS Code Extension API
- PyCharm 插件使用 Kotlin + IntelliJ Platform SDK
- 与现有 CLI 完全解耦，IDE 扩展仅调用 CLI 命令或读取索引数据
- 不引入额外的运行时依赖