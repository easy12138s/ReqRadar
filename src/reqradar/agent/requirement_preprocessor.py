import logging
from pathlib import Path

from reqradar.agent.llm_utils import _call_llm_structured
from reqradar.agent.prompts.requirement_preprocess import (
    CONSOLIDATION_SYSTEM_PROMPT,
    build_consolidation_user_prompt,
)
from reqradar.agent.schemas import CONSOLIDATION_SCHEMA
from reqradar.modules.loaders import LoaderRegistry

logger = logging.getLogger("reqradar.agent.preprocessor")


def _load_file_content(file_path: Path, llm_client=None) -> dict:
    result = {
        "filename": file_path.name,
        "type": file_path.suffix.lower(),
        "content": "",
    }

    try:
        loader = LoaderRegistry.get_for_file(str(file_path))
        if loader:
            docs = loader.load(str(file_path))
            result["content"] = "\n\n".join(d.content for d in docs)
            return result

        ext = file_path.suffix.lower()
        if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"):
            if llm_client:
                import base64

                image_bytes = file_path.read_bytes()
                b64 = base64.b64encode(image_bytes).decode()
                data_uri = f"data:image/{ext.lstrip('.')};base64,{b64}"

                vision_result = llm_client.describe_image(
                    data_uri,
                    "请详细描述这张图片的内容，包括界面元素、文字、流程关系等所有可观察的信息。",
                )
                result["content"] = vision_result
            else:
                result["content"] = f"[图片: {file_path.name}, 无法处理（无 Vision LLM）]"
        else:
            result["content"] = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.warning("Failed to load file %s: %s", file_path, e)
        result["content"] = f"[加载失败: {str(e)}]"

    return result


async def preprocess_requirements(
    file_paths: list[Path],
    llm_client,
    title: str = "",
) -> dict:
    loaded_contents = []
    for fp in file_paths:
        logger.info("Loading file: %s", fp.name)
        content = _load_file_content(fp, llm_client)
        loaded_contents.append(content)

    user_prompt = build_consolidation_user_prompt(loaded_contents, title)

    logger.info("Calling LLM for requirement consolidation (%d files)", len(loaded_contents))
    result = await _call_llm_structured(
        llm_client,
        messages=[
            {"role": "system", "content": CONSOLIDATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        schema=CONSOLIDATION_SCHEMA,
    )

    if not result:
        logger.warning("LLM consolidation returned empty result")
        result = {
            "consolidated_text": _build_fallback_consolidation(loaded_contents, title),
            "sections_found": [],
            "ambiguities": [],
            "warnings": ["LLM 调用失败，使用后备整合"],
        }

    return result


def _build_fallback_consolidation(loaded_contents: list[dict], title: str) -> str:
    lines = [f"# {title or '需求文档'}", "", "## 原始文件内容", ""]
    for item in loaded_contents:
        lines.append(f"### {item.get('filename', '未知文件')}")
        lines.append(item.get("content", ""))
        lines.append("")
    return "\n".join(lines)
