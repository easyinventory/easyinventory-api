from pathlib import Path


def test_alembic_versions_directory_exists():
    versions_dir = Path("alembic/versions")
    assert versions_dir.exists(), "alembic/versions directory missing"


def test_at_least_one_migration_exists():
    versions_dir = Path("alembic/versions")
    migrations = list(versions_dir.glob("*.py"))
    migrations = [m for m in migrations if not m.name.startswith("__")]
    assert len(migrations) >= 1, "No migration files found"
