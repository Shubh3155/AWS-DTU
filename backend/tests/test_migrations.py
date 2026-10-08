import pytest

from scripts.migrate_database import migration_files, validate_history


def test_history_rejects_edited_missing_and_out_of_order_migrations():
    files = [("001_first.sql", "first", "sql"), ("002_second.sql", "second", "sql")]
    validate_history(files, {})
    validate_history(files, {"001_first.sql": "first"})
    for invalid in (
        {"001_first.sql": "edited"},
        {"003_missing.sql": "unknown"},
        {"002_second.sql": "second"},
    ):
        with pytest.raises(ValueError):
            validate_history(files, invalid)


def test_duplicate_version_rejected_and_checksum_changes_with_content(tmp_path):
    path = tmp_path / "001_first.sql"
    path.write_text("SELECT 1;")
    first = migration_files(tmp_path)[0][1]
    path.write_text("SELECT 2;")
    assert migration_files(tmp_path)[0][1] != first
    (tmp_path / "001_duplicate.sql").write_text("SELECT 3;")
    with pytest.raises(ValueError):
        migration_files(tmp_path)
