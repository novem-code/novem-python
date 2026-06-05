from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import requests


class NovemTreeSync:
    """
    Shared `--dump` / `--load` tree-sync logic for the resource APIs.

    A resource exposes its state as a tree of files under an HTTP path. Dump
    walks that tree to disk; load treats a dumped folder as the desired state
    and syncs the remote tree to match it (create / overwrite / delete).

    Concrete classes mix this in and provide two hooks plus the usual
    ``self._session`` / ``self.user`` attributes:

      * ``_sync_base(user_aware)`` - the resource's base URL WITHOUT a trailing
        slash (e.g. ``.../vis/plots/myplot``). When ``user_aware`` is true and
        the resource belongs to another user, return that user-scoped path so
        dump can read it.
      * ``_sync_label()`` - a noun for the "cannot modify another user's X"
        message (e.g. ``"plots"`` / ``"job"``).

    Only real, round-trippable files are synced. The directory listing reports
    every leaf as ``type="file"``, so selection keys on the DELETE verb in each
    node's ``actions``: read-only files (no DELETE) and virtual/computed files
    like ``notifications`` (POST but no DELETE) are excluded. Shares
    (``/shared/``) round-trip as links created via PUT; tags (``/tags/``) are
    excluded entirely (managed via the -t CLI flag).
    """

    # supplied by the concrete NovemAPI subclass
    _session: requests.Session
    user: Optional[str]

    def _sync_base(self, user_aware: bool) -> str:  # pragma: no cover - hook
        raise NotImplementedError

    def _sync_label(self) -> str:  # pragma: no cover - hook
        raise NotImplementedError

    def api_dump(self, outpath: str) -> None:
        """
        Walk the remote tree and write every round-trippable file to disk.
        """
        read_root = f"{self._sync_base(user_aware=True)}/"
        out = Path(outpath)

        def write_file(api_path: str, content: str) -> None:
            fp = out / api_path.lstrip("/")
            if not fp.parent.exists():
                fp.parent.mkdir(parents=True, exist_ok=True)
                print(f"Creating folder: {fp.parent}")
            fp.write_text(content, encoding="utf-8")
            print(f"Writing file:    {fp}")

        def rec_tree(path: str) -> None:
            req = self._session.get(f"{read_root}{path}")
            if not req.ok:
                return

            headers = req.headers
            tp = headers.get("X-NVM-Type", headers.get("X-NS-Type", "file"))

            if tp == "file":
                # skip files with default values
                if headers.get("x-nvm-default", "").lower() == "true":
                    print(f"Skipping default: {out / path.lstrip('/')}")
                    return
                write_file(path, req.text)
                return

            nodes: List[Dict[str, str]] = req.json()
            for r in nodes:
                if r["type"] in ["system_file", "system_dir"]:
                    continue
                child_path = f'{path}/{r["name"]}'

                # tags are managed via the -t CLI flag, not the load/dump sync
                if child_path == "/tags" or child_path.startswith("/tags/"):
                    continue

                # /shared/ markers are links dumped as empty files
                if r["type"] in ["file", "link"] and child_path.startswith("/shared/"):
                    write_file(child_path, "")
                    continue

                # Only round-trip real file_content-backed files (those with a
                # DELETE verb); skip read-only and virtual/computed files.
                if r["type"] in ["file", "link"] and "DELETE" not in r.get("actions", []):
                    continue
                rec_tree(child_path)

        rec_tree("")

    def _collect_local_files(self, inpath: str) -> Dict[str, str]:
        """
        Walk a dumped folder and return {api_path: content} for every file,
        keyed by the api path it maps to (e.g. "/config/type").
        """
        files: Dict[str, str] = {}

        def walk(full: Path, api_path: str) -> None:
            # tags are managed via the -t CLI flag, not the load/dump sync
            if api_path == "/tags" or api_path.startswith("/tags/"):
                return

            if full.is_file():
                files[api_path] = full.read_text(encoding="utf-8")
            elif full.is_dir():
                for name in sorted(p.name for p in full.iterdir()):
                    walk(full / name, f"{api_path}/{name}")

        walk(Path(inpath), "")
        return files

    def _collect_remote_files(self, read_root: str) -> Tuple[Dict[str, str], Set[str]]:
        """
        Walk the current remote tree and return (files, skipped):
          * files   - {api_path: content} for every real, round-trippable file
          * skipped - api paths that exist remotely but the sync does not manage
                      (virtual/computed or read-only files, e.g. `notifications`)

        `skipped` lets api_load ignore local copies of those paths rather than
        trying to (re)create them on every run. Mirrors api_dump's filtering.
        """
        files: Dict[str, str] = {}
        skipped: Set[str] = set()

        def rec_tree(path: str) -> None:
            req = self._session.get(f"{read_root}{path}")
            if not req.ok:
                return

            headers = req.headers
            tp = headers.get("X-NVM-Type", headers.get("X-NS-Type", "file"))

            if tp == "file":
                # skip files with default values
                if headers.get("x-nvm-default", "").lower() == "true":
                    return
                files[path] = req.text
                return

            nodes: List[Dict[str, str]] = req.json()
            for r in nodes:
                if r["type"] in ["system_file", "system_dir"]:
                    continue
                child_path = f'{path}/{r["name"]}'

                # tags are managed via the -t CLI flag, not the sync
                if child_path == "/tags" or child_path.startswith("/tags/"):
                    continue

                # /shared/ markers are links round-tripped as empty files
                if r["type"] in ["file", "link"] and child_path.startswith("/shared/"):
                    files[child_path] = ""
                    continue

                # Only round-trip real file_content-backed files. Read-only
                # files expose no DELETE verb, and virtual/computed files like
                # `notifications` accept POST but no DELETE. Record them as
                # skipped so api_load ignores any stale local copy.
                if r["type"] in ["file", "link"] and "DELETE" not in r.get("actions", []):
                    skipped.add(child_path)
                    continue
                rec_tree(child_path)

        rec_tree("")
        return files, skipped

    def api_load(self, inpath: str, dry_run: bool = False) -> None:
        """
        Sync a dumped folder into the API, treating the local folder as the
        desired state of the resource:

          * files that don't exist remotely are created
          * files whose content differs are overwritten
          * remote files no longer present locally are deleted
          * unchanged files are left untouched

        With dry_run=True no state-changing requests are sent; the actions that
        would be taken are printed instead.
        """
        if self.user:
            print(f"You cannot modify another user's {self._sync_label()}")
            return

        base = self._sync_base(user_aware=False)
        read_root = f"{base}/"
        prefix = "[dry-run] " if dry_run else ""

        local = self._collect_local_files(inpath)
        remote, skipped = self._collect_remote_files(read_root)

        # don't (re)create local copies of paths the sync doesn't manage
        # (virtual/read-only files like `notifications`)
        to_create = sorted(p for p in local if p not in remote and p not in skipped)
        to_overwrite = sorted(p for p in local if p in remote and local[p] != remote[p])
        # delete deepest paths first so we don't strand children
        to_delete = sorted((p for p in remote if p not in local), reverse=True)
        unchanged = sum(1 for p in local if p in remote and local[p] == remote[p])

        created = overwritten = deleted = failed = 0

        for api_path in to_create:
            content = local[api_path]
            if dry_run:
                print(f"{prefix}create:    {api_path} ({len(content)} bytes)")
                created += 1
                continue
            full_api = f"{base}{api_path}"
            if api_path.startswith("/shared/"):
                # shares are links created via PUT with no body
                r = self._session.put(full_api)
            else:
                # PUT is best-effort (file leaves have no PUT route); the POST
                # is what actually creates and writes, so gate success on it.
                self._session.put(full_api)
                r = self._session.post(
                    full_api,
                    headers={"Content-type": "text/plain"},
                    data=content.encode("utf-8"),
                )
            if r.ok:
                print(f"create:    {api_path} ({len(content)} bytes)")
                created += 1
            else:
                print(f"FAILED create:    {api_path} (HTTP {r.status_code})")
                failed += 1

        for api_path in to_overwrite:
            content = local[api_path]
            old = remote[api_path]
            # for single-line values show the actual change, not just a size
            if "\n" not in content.strip() and "\n" not in old.strip():
                detail = f'"{old.strip()}" -> "{content.strip()}"'
            else:
                detail = f"{len(content)} bytes"
            if dry_run:
                print(f"{prefix}overwrite: {api_path} ({detail})")
                overwritten += 1
                continue
            full_api = f"{base}{api_path}"
            r = self._session.post(
                full_api,
                headers={"Content-type": "text/plain"},
                data=content.encode("utf-8"),
            )
            if r.ok:
                print(f"overwrite: {api_path} ({detail})")
                overwritten += 1
            else:
                print(f"FAILED overwrite: {api_path} (HTTP {r.status_code})")
                failed += 1

        for api_path in to_delete:
            if dry_run:
                print(f"{prefix}delete:    {api_path}")
                deleted += 1
                continue
            r = self._session.delete(f"{base}{api_path}")
            if r.ok:
                print(f"delete:    {api_path}")
                deleted += 1
            else:
                print(f"FAILED delete:    {api_path} (HTTP {r.status_code})")
                failed += 1

        summary = f"{prefix}{created} created, {overwritten} overwritten, " f"{deleted} deleted, {unchanged} unchanged"
        if failed:
            summary += f", {failed} failed"
        print(summary)
