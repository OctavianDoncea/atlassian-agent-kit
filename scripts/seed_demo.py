from agentkit.config import get_settings
from agentkit.db.models import Integration, IntegrationType
from agentkit.db.session import SessionLocal

def main() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        for name, type_ in [('jira', IntegrationType.jira), ('confluence', IntegrationType.confluence)]:
            existing = db.query(Integration).filter_by(name=name).one_or_none()
            if existing:
                print(f'= {name} already exists (id={existing.id})')
                continue
            db.add(Integration(name=name, type=type_, base_url=settings.atlassian_site_url))
            print(f'+ created integration: {name}')
        db.commit()

if __name__ == '__main__':
    main()