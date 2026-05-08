import bcrypt
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from reqradar.web.models import ReportTemplate, User
from reqradar.infrastructure.template_loader import TemplateLoader

logger = logging.getLogger("reqradar.seed")


async def seed_admin_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == "admin@reqradar.io"))
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    password = "Admin12138%"
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    admin = User(
        email="admin@reqradar.io",
        password_hash=password_hash,
        display_name="Admin",
        role="admin",
        created_at=datetime.now(timezone.utc),
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    logger.info("Seeded default admin user (email=admin@reqradar.io)")
    return admin


async def seed_default_template(db: AsyncSession) -> ReportTemplate:
    result = await db.execute(select(ReportTemplate).where(ReportTemplate.is_default == True))
    existing = result.scalar_one_or_none()
    if existing:
        logger.info("Default template already exists (id=%d), skipping seed", existing.id)
        return existing

    loader = TemplateLoader()
    defn = loader.load_definition(loader.get_default_template_path())
    template_path = loader.get_default_render_template_path()
    render_content = template_path.read_text(encoding="utf-8")

    import yaml

    definition_yaml = yaml.dump(
        {
            "template_definition": {
                "name": defn.name,
                "description": defn.description,
                "sections": [
                    {
                        "id": s.id,
                        "title": s.title,
                        "description": s.description,
                        "requirements": s.requirements,
                        "required": s.required,
                        "dimensions": s.dimensions,
                    }
                    for s in defn.sections
                ],
            }
        },
        allow_unicode=True,
        default_flow_style=False,
    )

    default = ReportTemplate(
        name=defn.name,
        description=defn.description,
        definition=definition_yaml,
        render_template=render_content,
        is_default=True,
    )
    db.add(default)
    await db.commit()
    await db.refresh(default)
    logger.info("Seeded default template (id=%d)", default.id)
    return default


async def seed_all(db: AsyncSession):
    await seed_admin_user(db)
    await seed_default_template(db)
