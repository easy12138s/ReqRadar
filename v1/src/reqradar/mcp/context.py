import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import async_sessionmaker

from reqradar.infrastructure.config import Config
from reqradar.web.services.content_reader import ContentReader
from reqradar.web.services.report_storage import ReportStorage

logger = logging.getLogger("reqradar.mcp.context")


@dataclass
class MCPRuntimeContext:
    config: Config
    session_factory: async_sessionmaker
    paths: dict
    report_storage: ReportStorage
    content_reader: ContentReader = field(init=False)

    def __post_init__(self):
        self.content_reader = ContentReader(
            session_factory=self.session_factory,
            report_storage=self.report_storage,
            memory_storage_path=str(self.paths.get("memories", "")),
        )
