"""Fast checks for the deployment path: backup/restore and pinned runtime."""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import subprocess
import tarfile
import tomllib
from pathlib import Path

import pytest

from app import db as db_module
from app.images import MAX_BYTES

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKUP_SCRIPT = REPO_ROOT / "deploy" / "backup.sh"
REQUIREMENTS_LOCK = REPO_ROOT / "server" / "requirements.lock"
UV_LOCK = REPO_ROOT / "server" / "uv.lock"
CONTAINERFILE = REPO_ROOT / "Containerfile"
NGINX_CONF = REPO_ROOT / "deploy" / "nginx.conf"
RUNBOOK = REPO_ROOT / "deploy" / "RUNBOOK.md"
SYSTEMD_UNIT = REPO_ROOT / "deploy" / "arkham-hunt.service"


def _canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _pinned_requirements(text: str) -> dict[str, tuple[str, str, tuple[str, ...]]]:
    """Parse a `--require-hashes` requirements file into name → (version, marker, hashes).

    The hashes are kept, not dropped, so a drift check can compare the artifact
    digests rather than just the versions.
    """

    pinned: dict[str, tuple[str, str]] = {}
    hashes: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        # Only requirement lines start at column zero; hashes and `# via`
        # comments are indented continuations.
        if raw and raw[0].isspace():
            if current is not None:
                hashes[current].extend(re.findall(r"--hash=sha256:([0-9a-f]{64})", raw))
            continue
        if not raw or raw.startswith("#"):
            continue
        line = raw.rstrip("\\").strip()
        match = re.fullmatch(r"([A-Za-z0-9._-]+)==([^\s;]+)\s*(?:;\s*(.*))?", line)
        assert match, f"not a fully pinned requirement: {raw!r}"
        name, version, marker = match.groups()
        current = _canonical(name)
        pinned[current] = (version, (marker or "").strip())
        hashes.setdefault(current, [])
    return {
        name: (version, marker, tuple(hashes[name]))
        for name, (version, marker) in pinned.items()
    }


def _uv_lock_versions(text: str) -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in tomllib.loads(text).get("package", []):
        versions[_canonical(package["name"])] = package["version"]
    return versions


def test_requirements_lock_is_fully_pinned():
    pinned = _pinned_requirements(REQUIREMENTS_LOCK.read_text())
    assert pinned, "requirements.lock is empty"
    assert len(pinned) > 10, "requirements.lock looks truncated"
    for name, (version, _, hashes) in pinned.items():
        assert version, f"{name} is not pinned to a version"
        assert hashes, f"{name} has no --hash entries"


def test_requirements_lock_versions_match_uv_lock():
    pinned = _pinned_requirements(REQUIREMENTS_LOCK.read_text())
    locked = _uv_lock_versions(UV_LOCK.read_text())
    assert set(pinned) <= set(locked), set(pinned) - set(locked)
    for name, (version, _, _) in pinned.items():
        assert version == locked[name], f"{name}: {version} != uv.lock {locked[name]}"


def test_requirements_lock_matches_fresh_uv_export():
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv not on PATH; scripts/check-quality.sh enforces this in CI")
    result = subprocess.run(
        [
            uv,
            "export",
            "--project",
            "server",
            "--locked",
            "--no-dev",
            "--no-emit-project",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert _pinned_requirements(REQUIREMENTS_LOCK.read_text()) == (
        _pinned_requirements(result.stdout)
    ), "server/requirements.lock is stale; regenerate it from uv.lock"


def test_containerfile_installs_the_hash_pinned_lock():
    containerfile = CONTAINERFILE.read_text()
    assert "--require-hashes -r ./server/requirements.lock" in containerfile
    assert "pip install --no-cache-dir -e" not in containerfile


def test_containerfile_base_images_are_digest_pinned():
    images = re.findall(
        r"^FROM\s+(\S+)(?:\s+AS\s+\S+)?", CONTAINERFILE.read_text(), re.MULTILINE
    )
    assert images, "Containerfile has no FROM lines"
    for image in images:
        assert "@sha256:" in image, f"base image is a mutable tag: {image}"


def test_nginx_upload_limit_sits_above_the_app_cap():
    match = re.search(r"client_max_body_size\s+(\d+)m;", NGINX_CONF.read_text())
    assert match, "nginx.conf has no client_max_body_size"
    proxy_bytes = int(match.group(1)) * 1024 * 1024
    assert proxy_bytes > MAX_BYTES, "nginx would cut off a body the app accepts"
    assert f"client_max_body_size {match.group(1)}m" in RUNBOOK.read_text()


def _tls_server_block(text: str) -> str:
    """Return the body of the `server { … }` block that listens on 443."""

    for match in re.finditer(r"server\s*\{", text):
        depth = 1
        cursor = match.end()
        while cursor < len(text) and depth:
            if text[cursor] == "{":
                depth += 1
            elif text[cursor] == "}":
                depth -= 1
            cursor += 1
        block = text[match.end() : cursor - 1]
        if re.search(r"^\s*listen\s+443\b", block, re.MULTILINE):
            return block
    raise AssertionError("nginx.conf has no server block listening on 443")


def test_nginx_https_block_sends_security_headers():
    block = _tls_server_block(NGINX_CONF.read_text())
    csp = (
        "default-src 'self'; script-src 'self' 'unsafe-inline';"
        " style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;"
        " font-src 'self' https://fonts.gstatic.com; img-src 'self';"
        " connect-src 'self' https://glitchtip.nulloctet.com;"
        " worker-src 'self'; manifest-src 'self';"
        " object-src 'none'; base-uri 'self'; form-action 'self';"
        " frame-ancestors 'none'"
    )
    for directive in (
        'add_header Strict-Transport-Security "max-age=31536000" always;',
        'add_header X-Content-Type-Options "nosniff" always;',
        'add_header X-Frame-Options "DENY" always;',
        f'add_header Content-Security-Policy "{csp}" always;',
    ):
        assert directive in block, f"missing or weakened directive: {directive}"


def test_systemd_unit_hardens_the_data_dir():
    unit = SYSTEMD_UNIT.read_text()
    assert "ProtectSystem=strict" in unit
    assert "ProtectHome=read-only" in unit
    assert "ReadWritePaths=%h/arkham/data" in unit


def test_oidc_environment_file_examples_use_bare_assignments():
    """`~/.config/arkham-hunt.env` is a systemd EnvironmentFile, not a shell.

    systemd drops a line it cannot read as `NAME=value`, so an
    `export NAME=value` example silently leaves SSO off — the operator sees
    no error and the issue is invisible until a login is refused. The fenced
    block under §6 that fills that file must therefore show bare
    assignments. (The shell blocks elsewhere in the runbook export into the
    running shell, which is a different reader.)
    """
    section = RUNBOOK.read_text().split("## 6. Single sign-on", 1)[1]
    section = section.split("\n## ", 1)[0]
    for match in re.finditer(r"```sh\n(.*?)```", section, re.DOTALL):
        for line in match.group(1).splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            assert not stripped.startswith("export "), (
                "EnvironmentFile example must not export: " + stripped
            )


def test_runbook_requests_the_groups_scope():
    """The Authentik groups mapping is emitted only when its scope is asked for.

    The app defaults `ARKHAM_OIDC_SCOPES` to `openid profile email`; a scope
    mapping with its own name (the documented `groups`) reaches the token
    only if the scope list includes it. If the runbook creates the mapping
    but never requests the scope, every login is refused.
    """
    runbook = RUNBOOK.read_text()
    assert "ARKHAM_OIDC_SCOPES=openid profile email groups" in runbook


def test_smoke_container_arms_csrf_and_sends_the_header():
    """The smoke's curl calls must satisfy the double-submit CSRF check.

    CSRF is safe-by-default (ADR 0015): every method outside GET/HEAD/OPTIONS
    is challenged, so the login and every later mutation 403s without a
    matching `arkham_csrf` cookie and `X-CSRF-Token` header. The smoke calls
    `curl --fail`, so a miss aborts the whole run. This is static — nobody
    wants a container runtime in the unit suite.

    Every unsafe curl invocation (one carrying `--data`, `--form`, or an
    explicit `--request POST`) must therefore send `X-CSRF-Token`, and each
    jar must be armed by a safe GET before it is first used.
    """
    script = (REPO_ROOT / "scripts" / "smoke-container.sh").read_text()

    # Bound each curl invocation at the next non-continuation line. The
    # script uses trailing backslashes, so a call is a maximal run of
    # `curl ... \` lines ending without a backslash. A call may be wrapped
    # in a substitution (`x="$(curl ...`), so match `curl` after any prefix
    # rather than only at the start of a line.
    calls: list[str] = []
    current: list[str] = []
    for line in script.splitlines():
        if current or re.search(r"\bcurl\b", line):
            current.append(line)
            if not line.rstrip().endswith("\\"):
                calls.append("\n".join(current))
                current = []

    unsafe_markers = ("--data", "--form", "--request POST")
    seen = 0
    for call in calls:
        if not any(marker in call for marker in unsafe_markers):
            continue
        seen += 1
        assert "X-CSRF-Token:" in call, "unsafe curl call missing CSRF header:\n" + call

    # Guard the parser itself: the script has several unsafe calls, and a
    # silent parse failure would make this test vacuous.
    assert seen >= 4, f"expected to find the smoke's unsafe calls, found {seen}"

    # Each jar is armed with a safe GET before its first unsafe call. The
    # helper is the only place that reads the planted cookie, so requiring
    # it for both jars keeps the handshake from being inlined incorrectly.
    assert 'arm_csrf "$admin_jar"' in script
    assert 'arm_csrf "$player_jar"' in script


def _write_stub(path: Path, body: str) -> None:
    path.write_text(f"#!/bin/sh\n{body}")
    path.chmod(0o755)


def _fail_on_marker_stub(real: str, marker: str) -> str:
    return (
        'for arg in "$@"; do\n'
        f'  case "$arg" in *"{marker}"*)'
        ' echo "simulated failure" >&2; exit 1;; esac\n'
        "done\n"
        f'exec "{real}" "$@"\n'
    )


def _restricted_path_without_sqlite_cli(
    root: Path,
    *,
    stamp: str = "20260101-000000",
    failing_cp_marker: str = "",
    failing_rm_marker: str = "",
    failing_mktemp: bool = False,
    mktemp_sequence: tuple[str, ...] = (),
) -> str:
    """Expose only the utilities backup.sh needs, never sqlite3.

    `date` is pinned to `stamp`, so a test can put two runs in the same second
    on purpose rather than relying on the wall clock. `failing_cp_marker`
    leaves a short file where `cp` would have written and then fails, to stand
    in for a mirror copy cut short. `failing_rm_marker` and `failing_mktemp`
    fail those utilities so a test can drive an error path. `mktemp_sequence`
    makes `mktemp` hand out those paths in order, so a test can pin the work
    directory and archive names.
    """

    bin_dir = root / "bin"
    bin_dir.mkdir()
    for name in ("dirname", "gzip", "mkdir", "mv", "stat", "tar"):
        source = shutil.which(name)
        assert source is not None, f"test host lacks {name}"
        (bin_dir / name).symlink_to(source)
    _write_stub(bin_dir / "date", f"echo {stamp}\n")

    real_cp = shutil.which("cp")
    assert real_cp is not None, "test host lacks cp"
    if failing_cp_marker:
        body = (
            'for arg in "$@"; do\n'
            f'  case "$arg" in *"{failing_cp_marker}"*)\n'
            '    src="$1"; last="";\n'
            '    for a in "$@"; do last="$a"; done\n'
            '    [ -d "$last" ] && last="$last/${src##*/}"\n'
            '    printf "partial-copy" > "$last" 2>/dev/null || true\n'
            '    echo "cp: simulated failure" >&2\n'
            "    exit 1\n"
            "    ;;\n"
            "  esac\n"
            "done\n"
            f'exec "{real_cp}" "$@"\n'
        )
    else:
        body = f'exec "{real_cp}" "$@"\n'
    _write_stub(bin_dir / "cp", body)

    real_rm = shutil.which("rm")
    assert real_rm is not None, "test host lacks rm"
    if failing_rm_marker:
        _write_stub(bin_dir / "rm", _fail_on_marker_stub(real_rm, failing_rm_marker))
    else:
        (bin_dir / "rm").symlink_to(real_rm)

    if failing_mktemp:
        _write_stub(
            bin_dir / "mktemp", 'echo "mktemp: simulated failure" >&2\nexit 1\n'
        )
    elif mktemp_sequence:
        count = root / "mktemp.count"
        log = root / "mktemp.args"
        cases = "".join(
            f'{index}) path="{path}" ;;\n'
            for index, path in enumerate(mktemp_sequence, start=1)
        )
        _write_stub(
            bin_dir / "mktemp",
            f'count="{count}"\n'
            f'log="{log}"\n'
            "i=0\n"
            '[ -f "$count" ] && read -r i < "$count"\n'
            "i=$((i + 1))\n"
            'echo "$i" > "$count"\n'
            'echo "$*" >> "$log"\n'
            'case "$i" in\n'
            f"{cases}"
            '*) echo "mktemp: unexpected call $i" >&2; exit 1 ;;\n'
            "esac\n"
            'case " $* " in\n'
            '*" -d "*) mkdir -p "$path" ;;\n'
            '*) : > "$path" ;;\n'
            "esac\n"
            'echo "$path"\n',
        )
    else:
        real_mktemp = shutil.which("mktemp")
        assert real_mktemp is not None, "test host lacks mktemp"
        (bin_dir / "mktemp").symlink_to(real_mktemp)
    return str(bin_dir)


def _live_data(root: Path) -> Path:
    """A data directory with a migrated database and one photo."""

    source = root / "live-data"
    source.mkdir()
    (source / "photos" / "originals").mkdir(parents=True)
    (source / "photos" / "originals" / "evidence.jpg").write_bytes(b"photo-bytes")
    conn = db_module.connect(source / "arkham.db")
    db_module.apply_migrations(conn)
    conn.close()
    return source


def _backup_env(
    source: Path,
    root: Path,
    *,
    failing_cp_marker: str = "",
    failing_rm_marker: str = "",
    failing_mktemp: bool = False,
    mktemp_sequence: tuple[str, ...] = (),
    **extra: str,
) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "ARKHAM_DATA_DIR": str(source),
            "PATH": _restricted_path_without_sqlite_cli(
                root,
                failing_cp_marker=failing_cp_marker,
                failing_rm_marker=failing_rm_marker,
                failing_mktemp=failing_mktemp,
                mktemp_sequence=mktemp_sequence,
            ),
        }
    )
    env.update(extra)
    return env


def _run_backup(destination: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["/bin/sh", str(BACKUP_SCRIPT), str(destination)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_backup_archive_restores_live_database_and_photos(tmp_path):
    source = tmp_path / "live-data"
    destination = tmp_path / "backups"
    restored = tmp_path / "restored"
    source.mkdir()
    (source / "photos" / "originals").mkdir(parents=True)
    photo_bytes = b"synthetic-photo-bytes"
    (source / "photos" / "originals" / "evidence.jpg").write_bytes(photo_bytes)

    conn = db_module.connect(source / "arkham.db")
    db_module.apply_migrations(conn)
    conn.execute(
        "INSERT INTO event (id, name, join_code, mod_code, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        ("event-backup", "Restore Party", "JOINBACK", "MODBACK", 123),
    )
    conn.commit()

    env = os.environ.copy()
    env.update(
        {
            "ARKHAM_DATA_DIR": str(source),
            "PATH": _restricted_path_without_sqlite_cli(tmp_path),
        }
    )
    try:
        result = subprocess.run(
            ["/bin/sh", str(BACKUP_SCRIPT), str(destination)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
    finally:
        conn.close()

    archives = list(destination.glob("arkham-backup-*.tar.gz"))
    assert len(archives) == 1
    assert str(archives[0]) in result.stdout
    assert not list(destination.glob(".backup-work-*"))

    restored.mkdir()
    with tarfile.open(archives[0], "r:gz") as archive:
        if hasattr(tarfile, "data_filter"):
            archive.extractall(restored, filter=tarfile.data_filter)
        else:  # Python 3.11 has no extraction filter argument.
            archive.extractall(restored)

    restored_conn = db_module.connect(restored / "arkham.db")
    try:
        assert (
            restored_conn.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()[0]
            == 5
        )
        assert (
            restored_conn.execute(
                "SELECT name FROM event WHERE id = ?", ("event-backup",)
            ).fetchone()[0]
            == "Restore Party"
        )
        assert restored_conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            with restored_conn:
                restored_conn.execute(
                    "INSERT INTO riddle"
                    " (id, event_id, text, sort_order, created_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    ("orphan", "missing-event", "Nope", 1, 123),
                )
    finally:
        restored_conn.close()

    assert (
        restored / "photos" / "originals" / "evidence.jpg"
    ).read_bytes() == photo_bytes


def test_backup_restore_recipe_extracts_one_archive_into_data():
    """The header recipe must match RUNBOOK §1, or the restore is empty.

    Retention leaves several archives, so a wildcard passed to tar would make
    every file but the first a member name and the restore would fail.
    """

    header = BACKUP_SCRIPT.read_text()
    runbook = RUNBOOK.read_text()
    assert "tar -xzf" in header
    assert 'tar -xzf "$ARCHIVE" -C <repo-root>/data' in header
    assert 'tar -xzf "$ARCHIVE" -C ~/arkham/data' in runbook
    for text in (header, runbook):
        # No recipe that extracts into the repo root itself, and none that
        # lets the shell expand the archive argument.
        assert not re.search(r"-C <repo-root>(?!\S)", text)
        assert not re.search(r"tar -xzf [^\n]*\*", text)
        assert re.search(r"ARCHIVE=\$\(ls -1t [^\n]*arkham-backup-\*\.tar\.gz", text)


def test_backups_in_the_same_second_do_not_collide(tmp_path):
    source = _live_data(tmp_path)
    destination = tmp_path / "backups"
    # The stubbed date pins both runs to the same second, so only the archive
    # suffix can keep them apart.
    env = _backup_env(source, tmp_path)

    for _ in range(2):
        result = _run_backup(destination, env)
        assert result.returncode == 0, result.stderr

    archives = sorted(destination.glob("arkham-backup-*.tar.gz"))
    assert len(archives) == 2, [archive.name for archive in archives]
    assert all("20260101-000000" in archive.name for archive in archives)
    assert not list(destination.glob(".backup-work-*"))


def test_backup_mirrors_off_host_and_prunes_both_directories(tmp_path):
    source = _live_data(tmp_path)
    destination = tmp_path / "backups"
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    env = _backup_env(
        source,
        tmp_path,
        ARKHAM_BACKUP_MIRROR=str(mirror),
        ARKHAM_BACKUP_KEEP="2",
    )

    for _ in range(3):
        result = _run_backup(destination, env)
        assert result.returncode == 0, result.stderr

    local = sorted(destination.glob("arkham-backup-*.tar.gz"))
    mirrored = sorted(mirror.glob("arkham-backup-*.tar.gz"))
    assert len(local) == 2, [archive.name for archive in local]
    assert len(mirrored) == 2, [archive.name for archive in mirrored]
    assert {archive.name for archive in local} == {archive.name for archive in mirrored}


def test_backup_warns_when_no_mirror_is_configured(tmp_path):
    source = _live_data(tmp_path)
    env = _backup_env(source, tmp_path)
    env.pop("ARKHAM_BACKUP_MIRROR", None)

    result = _run_backup(tmp_path / "backups", env)

    assert result.returncode == 0, result.stderr
    assert "ARKHAM_BACKUP_MIRROR is unset" in result.stderr


def test_backup_refuses_an_unmounted_mirror(tmp_path):
    source = _live_data(tmp_path)
    env = _backup_env(
        source, tmp_path, ARKHAM_BACKUP_MIRROR=str(tmp_path / "not-mounted")
    )

    result = _run_backup(tmp_path / "backups", env)

    assert result.returncode != 0
    assert "not a directory" in result.stderr


def test_backup_publishes_no_archive_when_the_mirror_copy_fails(tmp_path):
    """A copy cut short must not land under the final name."""

    source = _live_data(tmp_path)
    destination = tmp_path / "backups"
    mirror = tmp_path / "off-host"
    mirror.mkdir()
    env = _backup_env(
        source,
        tmp_path,
        failing_cp_marker="off-host",
        ARKHAM_BACKUP_MIRROR=str(mirror),
    )

    result = _run_backup(destination, env)

    assert result.returncode != 0
    assert not list(mirror.glob("arkham-backup-*.tar.gz"))
    assert not list(mirror.glob(".arkham-backup-copy-*"))
    assert "failed to mirror" in result.stderr


def test_backup_reserves_the_archive_name_apart_from_the_work_directory(tmp_path):
    """The archive name must be reserved by mktemp, not built from the work dir.

    The work directory's suffix is free for reuse once the directory is
    removed, so a later run in the same second could take it and overwrite the
    archive. The stub creates the path it returns and records its arguments, so
    the test fails if the script stops asking mktemp for the archive name. The
    reserved name has no extension: BusyBox mktemp rejects a template whose
    trailing characters follow the `X`s, so the script creates the suffixed
    name itself under noclobber.
    """

    source = _live_data(tmp_path)
    destination = tmp_path / "backups"
    work = destination / ".backup-work-20260101-000000-WORKSU"
    reserved = destination / "arkham-backup-20260101-000000-ARCHSU"
    archive = reserved.with_name(f"{reserved.name}.tar.gz")
    env = _backup_env(source, tmp_path, mktemp_sequence=(str(work), str(reserved)))

    result = _run_backup(destination, env)

    assert result.returncode == 0, result.stderr
    assert [path.name for path in destination.glob("arkham-backup-*.tar.gz")] == [
        archive.name
    ]
    assert not reserved.exists()
    assert (tmp_path / "mktemp.args").read_text().splitlines() == [
        f"-d {destination}/.backup-work-20260101-000000-XXXXXX",
        f"{destination}/arkham-backup-20260101-000000-XXXXXX",
    ]
    # The script created an empty file at the suffixed name under noclobber;
    # publication must have replaced it with the finished tarball.
    with tarfile.open(archive) as tarball:
        names = tarball.getnames()
    assert "arkham.db" in names
    assert any(name.startswith("photos/") for name in names)


def test_backup_keeps_an_archive_whose_suffixed_name_is_already_taken(tmp_path):
    """mktemp reserves only the bare name, so the suffixed name can collide.

    The suffixed name is created under noclobber; when it is already taken the
    script must drop that reservation, ask mktemp again, and leave the earlier
    archive untouched.
    """

    source = _live_data(tmp_path)
    destination = tmp_path / "backups"
    destination.mkdir()
    work = destination / ".backup-work-20260101-000000-WORKSU"
    taken = destination / "arkham-backup-20260101-000000-TAKEN0"
    taken_archive = taken.with_name(f"{taken.name}.tar.gz")
    taken_archive.write_bytes(b"earlier-archive")
    free = destination / "arkham-backup-20260101-000000-FREESU"
    env = _backup_env(
        source, tmp_path, mktemp_sequence=(str(work), str(taken), str(free))
    )

    result = _run_backup(destination, env)

    assert result.returncode == 0, result.stderr
    assert taken_archive.read_bytes() == b"earlier-archive"
    assert not taken.exists()
    assert sorted(
        path.name for path in destination.glob("arkham-backup-*.tar.gz")
    ) == sorted([taken_archive.name, f"{free.name}.tar.gz"])
    assert (tmp_path / "mktemp.args").read_text().splitlines() == [
        f"-d {destination}/.backup-work-20260101-000000-XXXXXX",
        f"{destination}/arkham-backup-20260101-000000-XXXXXX",
        f"{destination}/arkham-backup-20260101-000000-XXXXXX",
    ]
    with tarfile.open(f"{free}.tar.gz") as tarball:
        assert "arkham.db" in tarball.getnames()


def test_backup_aborts_when_the_work_directory_cannot_be_created(tmp_path):
    """An empty WORK would resolve $WORK/arkham.db at the filesystem root."""

    source = _live_data(tmp_path)
    destination = tmp_path / "backups"
    env = _backup_env(source, tmp_path, failing_mktemp=True)

    result = _run_backup(destination, env)

    assert result.returncode != 0
    assert "backup written:" not in result.stdout
    assert not list(destination.glob("arkham-backup-*.tar.gz"))


def test_backup_accepts_a_leading_zero_keep_count(tmp_path):
    """`08` is decimal eight, not an octal arithmetic error."""

    source = _live_data(tmp_path)
    destination = tmp_path / "backups"
    env = _backup_env(source, tmp_path, ARKHAM_BACKUP_KEEP="08")

    for _ in range(3):
        result = _run_backup(destination, env)
        assert result.returncode == 0, result.stderr

    assert len(list(destination.glob("arkham-backup-*.tar.gz"))) == 3


def test_backup_fails_when_retention_cannot_delete_an_archive(tmp_path):
    source = _live_data(tmp_path)
    destination = tmp_path / "backups"
    env = _backup_env(
        source,
        tmp_path,
        failing_rm_marker="arkham-backup-",
        ARKHAM_BACKUP_KEEP="1",
    )

    for _ in range(2):
        result = _run_backup(destination, env)
    assert result.returncode != 0
    assert "simulated failure" in result.stderr
