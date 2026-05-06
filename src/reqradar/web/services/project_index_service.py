import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.infrastructure.config import Config, WebConfig, load_config
from reqradar.infrastructure.config_manager import ConfigManager
from reqradar.web.models import Project
from reqradar.web.services.project_file_service import ProjectFileService

logger = logging.getLogger("reqradar.web.services.project_index_service")


class ProjectIndexService:
    def __init__(self, web_config: WebConfig):
        self._file_service = ProjectFileService(web_config)

    async def build_index(self, project: Project, db: AsyncSession, config: Config) -> None:
        from reqradar.web.services.project_store import project_store

        svc = self._file_service
        project_id = project.id
        repo_path = svc.detect_code_root(project.name)
        index_path = svc.get_index_path(project.name)

        cm = ConfigManager(db, config)

        try:
            await self._build_code_graph(repo_path, index_path)

            await self._build_vector_store(project, config, svc, index_path)

            await self._build_git_index(project, config, svc, index_path)

            await self._load_memory(project, project_id, cm, svc, config)

            await project_store.invalidate(project_id)

            logger.info("Index build completed for project %d", project_id)
        except Exception:
            logger.exception("Index build failed for project %d", project_id)

    async def _build_code_graph(self, repo_path, index_path) -> None:
        from reqradar.modules.code_parser import PythonCodeParser

        parser = PythonCodeParser()
        code_graph = parser.parse_directory(repo_path)

        def _write_graph():
            index_path.mkdir(parents=True, exist_ok=True)
            graph_file = index_path / "code_graph.json"
            with open(graph_file, "w", encoding="utf-8") as f:
                f.write(code_graph.to_json())

        await asyncio.to_thread(_write_graph)

    async def _build_vector_store(
        self, project: Project, config: Config, svc: ProjectFileService, index_path
    ) -> None:
        try:
            from reqradar.modules.vector_store import ChromaVectorStore, CHROMA_AVAILABLE

            if CHROMA_AVAILABLE:
                req_dir = svc.get_requirements_path(project.name)
                vectorstore_path = index_path / "vectorstore"

                if req_dir.exists() and any(req_dir.iterdir()):
                    from reqradar.modules.loaders import LoaderRegistry
                    from reqradar.modules.vector_store import Document

                    vs = ChromaVectorStore(
                        persist_directory=str(vectorstore_path),
                        embedding_model=config.index.embedding_model,
                    )

                    for doc_path in req_dir.rglob("*"):
                        if doc_path.is_file():
                            loader = LoaderRegistry.get_for_file(doc_path)
                            if loader is None:
                                continue
                            try:
                                loaded_docs = loader.load(
                                    doc_path,
                                    chunk_size=config.loader.chunk_size,
                                    chunk_overlap=config.loader.chunk_overlap,
                                )
                                documents = [
                                    Document(
                                        id=f"{doc_path.stem}_{i}",
                                        content=doc.content,
                                        metadata={**doc.metadata, "format": doc.format},
                                    )
                                    for i, doc in enumerate(loaded_docs)
                                ]
                                if documents:
                                    vs.add_documents(documents)
                            except Exception:
                                logger.warning("Failed to index file %s", doc_path)

                    vs.persist()
                    logger.info("Vector store built for project %d", project.id)
        except Exception:
            logger.warning("Vector store build failed for project %d", project.id, exc_info=True)

    async def _build_git_index(self, project, config, svc, index_path) -> None:
        from reqradar.modules.git_analyzer import GitAnalyzer
        from reqradar.modules.vector_store import ChromaVectorStore, Document

        repo_path = svc.detect_code_root(project.name)
        if not repo_path or not (repo_path / ".git").exists():
            logger.info("No git repo found for project %s, skipping commit indexing", project.id)
            return

        logger.info("Building git commit index for project %s", project.id)
        try:
            ga = GitAnalyzer(
                str(repo_path),
                lookback_months=config.git.lookback_months if hasattr(config, "git") else 6,
            )
            commits = await asyncio.to_thread(ga.get_all_commits)
        except Exception as e:
            logger.warning("Failed to read git history for project %s: %s", project.id, e)
            return

        if not commits:
            return

        vectorstore_path = index_path / "vectorstore"
        vs = ChromaVectorStore(
            persist_directory=str(vectorstore_path),
            embedding_model=config.index.embedding_model,
            collection_name="commits",
        )

        documents = []
        for c in commits:
            content = (
                f"Commit {c['hash']}: {c['summary']}\n"
                f"Author: {c['author_name']}\n"
                f"Date: {c['committed_date']}\n"
                f"Files: {', '.join(c['files_changed'][:10])}"
                + (
                    f" (+{len(c['files_changed']) - 10} more)"
                    if len(c["files_changed"]) > 10
                    else ""
                )
                + f"\n\n{c['message']}"
            )
            documents.append(
                Document(
                    id=f"commit-{c['hash']}",
                    content=content,
                    metadata={
                        "type": "commit",
                        "hash": c["hash"],
                        "author": c["author_name"],
                        "date": c["committed_date"],
                        "files_count": len(c["files_changed"]),
                    },
                )
            )

        vs.add_documents(documents)
        vs.persist()
        logger.info("Indexed %d commits for project %s", len(commits), project.id)

    async def _load_memory(
        self,
        project: Project,
        project_id: int,
        cm: ConfigManager,
        svc: ProjectFileService,
        config: Config,
    ) -> None:
        memory_enabled = await cm.get_bool(
            "memory.enabled", project_id=project_id, default=config.memory.enabled
        )
        if memory_enabled:
            from reqradar.modules.memory import MemoryManager

            memory_path = svc.get_memory_path(project.name)
            memory_manager = MemoryManager(storage_path=str(memory_path))
            memory_manager.load()
