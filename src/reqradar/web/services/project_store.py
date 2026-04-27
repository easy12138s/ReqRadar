import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("reqradar.web.services.project_store")


class ProjectStore:
    MAX_CACHED_PROJECTS = 32

    def __init__(self):
        self._code_graphs: dict[int, object] = {}
        self._vector_stores: dict[int, object] = {}
        self._lock = asyncio.Lock()

    async def get_code_graph(self, project_id: int, index_path: str) -> Optional[object]:
        async with self._lock:
            if project_id in self._code_graphs:
                return self._code_graphs[project_id]

        code_graph_path = Path(index_path) / "code_graph.json"
        if not code_graph_path.exists():
            return None

        try:
            from reqradar.modules.code_parser import CodeFile, CodeGraph, CodeSymbol

            with open(code_graph_path, encoding="utf-8") as f:
                graph_data = json.load(f)

            code_graph = CodeGraph(
                files=[
                    CodeFile(
                        path=f["path"],
                        symbols=[CodeSymbol(**s) for s in f.get("symbols", [])],
                        imports=f.get("imports", []),
                    )
                    for f in graph_data.get("files", [])
                ]
            )

            async with self._lock:
                self._code_graphs[project_id] = code_graph
                while len(self._code_graphs) > self.MAX_CACHED_PROJECTS:
                    oldest_key = next(iter(self._code_graphs))
                    del self._code_graphs[oldest_key]

            return code_graph
        except Exception:
            logger.exception("Failed to load code graph for project %d", project_id)
            return None

    async def get_vector_store(self, project_id: int, index_path: str) -> Optional[object]:
        async with self._lock:
            if project_id in self._vector_stores:
                return self._vector_stores[project_id]

        vectorstore_path = Path(index_path) / "vectorstore"
        if not vectorstore_path.exists():
            return None

        try:
            from reqradar.modules.vector_store import ChromaVectorStore, CHROMA_AVAILABLE

            if not CHROMA_AVAILABLE:
                logger.warning("chromadb not available, skipping vector store for project %d", project_id)
                return None

            vector_store = ChromaVectorStore(persist_directory=str(vectorstore_path))

            async with self._lock:
                self._vector_stores[project_id] = vector_store
                while len(self._vector_stores) > self.MAX_CACHED_PROJECTS:
                    oldest_key = next(iter(self._vector_stores))
                    del self._vector_stores[oldest_key]

            return vector_store
        except Exception:
            logger.exception("Failed to load vector store for project %d", project_id)
            return None

    async def invalidate(self, project_id: int):
        async with self._lock:
            self._code_graphs.pop(project_id, None)
            self._vector_stores.pop(project_id, None)
        logger.info("Project store cache invalidated for project %d", project_id)


project_store = ProjectStore()