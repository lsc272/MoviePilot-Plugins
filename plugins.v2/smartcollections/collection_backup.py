import datetime
import json
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set


ProgressCallback = Callable[[int, int, str], None]


class EmbyCollectionBackupManager:
    """Backup, restore and safely remove Emby collections not managed here."""

    MANIFEST_NAME = "manifest.json"
    MAX_BACKUPS = 5

    def __init__(self, backup_root: Path, client):
        self._root = Path(backup_root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._client = client

    def inventory(self, protected_ids: Iterable[str]) -> Dict[str, Any]:
        protected = {str(value) for value in protected_ids if value}
        collections = self._client.list_collections()
        managed = [item for item in collections if str(item.get("id")) in protected]
        others = [item for item in collections if str(item.get("id")) not in protected]
        return {
            "total": len(collections),
            "managed": len(managed),
            "other": len(others),
        }

    def list_backups(self) -> List[dict]:
        backups: List[dict] = []
        for path in self._root.glob("emby-collections-*.zip"):
            try:
                manifest = self._read_manifest(path.name)
                backups.append(
                    {
                        "id": path.name,
                        "created_at": manifest.get("created_at"),
                        "server_name": manifest.get("server_name"),
                        "collection_count": len(manifest.get("collections") or []),
                        "size": path.stat().st_size,
                    }
                )
            except Exception:
                continue
        return sorted(
            backups,
            key=lambda item: str(item.get("created_at") or ""),
            reverse=True,
        )

    def create_backup(
        self,
        protected_ids: Iterable[str],
        server_name: str,
        progress: Optional[ProgressCallback] = None,
    ) -> dict:
        protected = {str(value) for value in protected_ids if value}
        collections = [
            item
            for item in self._client.list_collections()
            if str(item.get("id")) not in protected
        ]
        now = datetime.datetime.now()
        backup_id = f"emby-collections-{now.strftime('%Y%m%d-%H%M%S-%f')}.zip"
        final_path = self._root / backup_id
        temp_path = self._root / f"{backup_id}.tmp"
        records: List[dict] = []
        total = len(collections)

        try:
            with zipfile.ZipFile(
                temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
            ) as archive:
                for index, item in enumerate(collections, start=1):
                    collection_id = str(item.get("id") or "")
                    record = dict(item)
                    record["item_ids"] = sorted(
                        self._client.get_collection_item_ids(collection_id)
                    )
                    poster = (
                        self._client.get_collection_poster(collection_id)
                        if item.get("image_tag")
                        else None
                    )
                    if poster:
                        poster_path = f"posters/{collection_id}.jpg"
                        archive.writestr(poster_path, poster)
                        record["poster_path"] = poster_path
                    records.append(record)
                    if progress:
                        progress(index, total, f"正在备份：{record.get('name') or collection_id}")

                manifest = {
                    "version": 1,
                    "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "server_name": server_name,
                    "collection_count": len(records),
                    "collections": records,
                }
                archive.writestr(
                    self.MANIFEST_NAME,
                    json.dumps(manifest, ensure_ascii=False, indent=2),
                )
            temp_path.replace(final_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

        self._prune_backups()
        return {
            "backup_id": backup_id,
            "created_at": manifest["created_at"],
            "collection_count": len(records),
            "size": final_path.stat().st_size,
        }

    def restore_backup(
        self,
        backup_id: str,
        protected_ids: Iterable[str],
        progress: Optional[ProgressCallback] = None,
    ) -> dict:
        protected: Set[str] = {str(value) for value in protected_ids if value}
        path = self._backup_path(backup_id)
        manifest = self._read_manifest(path.name)
        records = manifest.get("collections") or []
        current = self._client.list_collections()
        by_name = {
            self._name_key(item.get("name")): item
            for item in current
            if self._name_key(item.get("name"))
        }
        created = 0
        merged = 0
        added = 0
        skipped = 0
        failures: List[str] = []
        warnings: List[str] = []

        with zipfile.ZipFile(path, "r") as archive:
            total = len(records)
            names = set(archive.namelist())
            for index, record in enumerate(records, start=1):
                name = str(record.get("name") or "").strip()
                existing = by_name.get(self._name_key(name))
                if existing and str(existing.get("id")) in protected:
                    skipped += 1
                    warnings.append(f"{name}：与智能合集同名，已跳过")
                    if progress:
                        progress(index, total, f"已跳过同名智能合集：{name}")
                    continue
                poster = None
                poster_path = str(record.get("poster_path") or "")
                if poster_path and poster_path in names:
                    poster = archive.read(poster_path)
                try:
                    result = self._client.restore_collection(
                        record=record,
                        poster=poster,
                        existing_id=str(existing.get("id")) if existing else None,
                    )
                    created += int(bool(result.created))
                    merged += int(not result.created)
                    added += int(result.added)
                    by_name[self._name_key(name)] = {
                        "id": result.collection_id,
                        "name": name,
                    }
                except Exception as exc:
                    failures.append(f"{name or record.get('id')}：{exc}")
                if progress:
                    progress(index, total, f"正在恢复：{name or record.get('id')}")

        return {
            "backup_id": path.name,
            "created": created,
            "merged": merged,
            "added": added,
            "skipped": skipped,
            "failed": len(failures),
            "errors": failures[:20],
            "warnings": warnings[:20],
        }

    def backup_and_cleanup(
        self,
        protected_ids: Iterable[str],
        server_name: str,
        progress: Optional[ProgressCallback] = None,
    ) -> dict:
        protected = {str(value) for value in protected_ids if value}

        def backup_progress(done: int, total: int, message: str) -> None:
            if progress:
                progress(done, max(1, total * 2), message)

        backup = self.create_backup(
            protected_ids=protected,
            server_name=server_name,
            progress=backup_progress,
        )
        manifest = self._read_manifest(str(backup["backup_id"]))
        records = manifest.get("collections") or []
        deleted = 0
        failures: List[str] = []
        total = len(records)
        for index, record in enumerate(records, start=1):
            collection_id = str(record.get("id") or "")
            name = str(record.get("name") or collection_id)
            if not collection_id or collection_id in protected:
                continue
            try:
                self._client.delete_collection(collection_id)
                deleted += 1
            except Exception as exc:
                failures.append(f"{name}：{exc}")
            if progress:
                progress(
                    total + index,
                    max(1, total * 2),
                    f"正在清理：{name}",
                )
        return {
            "backup": backup,
            "deleted": deleted,
            "failed": len(failures),
            "errors": failures[:20],
        }

    def _read_manifest(self, backup_id: str) -> dict:
        path = self._backup_path(backup_id)
        with zipfile.ZipFile(path, "r") as archive:
            payload = json.loads(archive.read(self.MANIFEST_NAME).decode("utf-8"))
        if int(payload.get("version") or 0) != 1:
            raise ValueError("不支持的合集备份版本")
        if not isinstance(payload.get("collections"), list):
            raise ValueError("合集备份内容无效")
        return payload

    def _backup_path(self, backup_id: str) -> Path:
        name = Path(str(backup_id or "")).name
        if not name.endswith(".zip") or not name.startswith("emby-collections-"):
            raise ValueError("合集备份编号无效")
        path = self._root / name
        if not path.is_file():
            raise FileNotFoundError("合集备份不存在")
        return path

    def _prune_backups(self) -> None:
        backups = sorted(
            self._root.glob("emby-collections-*.zip"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in backups[self.MAX_BACKUPS :]:
            path.unlink()

    @staticmethod
    def _name_key(value: Any) -> str:
        return str(value or "").strip().casefold()
