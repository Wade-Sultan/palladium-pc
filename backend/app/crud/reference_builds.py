from sqlalchemy.orm import Session, joinedload
from app.models.reference_build import ReferenceBuild, ReferenceBuildPart
from app.data.refbuilds import Build, Part


def get_all_active(db: Session) -> dict[str, Build]:
    rows = (
        db.query(ReferenceBuild)
        .options(joinedload(ReferenceBuild.parts).joinedload(ReferenceBuildPart.part))
        .filter(ReferenceBuild.is_active == True)
        .all()
    )
    return {row.build_key: _to_build(row) for row in rows}


def get_by_key(db: Session, build_key: str) -> tuple[str, Build] | None:
    row = (
        db.query(ReferenceBuild)
        .options(joinedload(ReferenceBuild.parts).joinedload(ReferenceBuildPart.part))
        .filter(ReferenceBuild.build_key == build_key, ReferenceBuild.is_active == True)
        .first()
    )
    if row is None:
        return None
    return build_key, _to_build(row)


def _to_build(row: ReferenceBuild) -> Build:
    return Build(
        label=row.label,
        description=row.description,
        total_approx=row.total_approx,
        parts=[
            Part(
                component=rbp.component,
                brand=rbp.part.manufacturer or "",
                model=rbp.part.name,
                approx_price=rbp.approx_price,
            )
            for rbp in sorted(row.parts, key=lambda p: p.sort_order)
        ],
    )