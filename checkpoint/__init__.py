"""Checkpoint system stubs for git-claw v4."""
FileBackup = None
Snapshot = None
MAX_SNAPSHOTS = 10
track_file_edit = lambda *a, **k: None
make_snapshot = lambda *a, **k: None
list_snapshots = lambda *a, **kw: []
get_snapshot = lambda *a, **k: None
rewind_files = lambda *a, **k: None
files_changed_since = lambda *a, **k: []
delete_session_checkpoints = lambda *a, **k: None
cleanup_old_sessions = lambda *a, **k: None
reset_file_versions = lambda *a, **k: None
