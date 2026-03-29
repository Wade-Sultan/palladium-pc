from app.core.db import SessionLocal
from app.data.refbuilds import BUILDS
from app.models.pcparts import PCPart
from app.models.reference_build import ReferenceBuild, ReferenceBuildPart


def _component_to_part_type(component: str) -> str:
    return {
        "CPU": "cpu",
        "CPU Cooler": "cpucooler",
        "Motherboard": "motherboard",
        "RAM": "ram",
        "Storage": "storage",
        "GPU": "gpu",
        "PSU": "psu",
        "Case": "case",
    }[component]


def _get_or_create_part(db, component: str, brand: str, model: str) -> PCPart:
    existing = db.query(PCPart).filter_by(name=model).first()
    if existing:
        return existing
    part = PCPart(
        name=model,
        manufacturer=brand,
        part_type=_component_to_part_type(component),
    )
    db.add(part)
    db.flush()
    return part


def seed():
    db = SessionLocal()
    try:
        for build_key, build in BUILDS.items():
            existing = db.query(ReferenceBuild).filter_by(build_key=build_key).first()
            if existing:
                print(f"Skipping {build_key} (already exists)")
                continue

            ref = ReferenceBuild(
                build_key=build_key,
                label=build["label"],
                description=build["description"],
                total_approx=build["total_approx"],
            )
            db.add(ref)
            db.flush()

            for i, part in enumerate(build["parts"]):
                pc_part = _get_or_create_part(db, part["component"], part["brand"], part["model"])
                db.add(ReferenceBuildPart(
                    build_id=ref.id,
                    part_id=pc_part.id,
                    component=part["component"],
                    approx_price=part["approx_price"],
                    sort_order=i,
                ))

            print(f"Seeded {build_key}")

        db.commit()
        print("Done.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()