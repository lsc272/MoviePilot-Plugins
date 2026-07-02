import base64
import json
import re
from dataclasses import dataclass

from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urlencode

from app.utils.http import RequestUtils


@dataclass
class EmbySyncResult:
    collection_id: str
    created: bool
    added: int
    removed: int


class EmbyCollectionClient:
    """Small adapter around MoviePilot's configured Emby service instance."""

    def __init__(self, service_info):
        self._service = service_info
        self._emby = service_info.instance

    def build_library_index(self) -> Tuple[Dict[Tuple[str, int], str], int]:
        """Map (movie|tv, TMDB id) to Emby item id."""

        catalog, _, duplicate_count = self.build_library_catalog()
        return {
            key: str(item["id"])
            for key, item in catalog.items()
        }, duplicate_count

    def build_library_catalog(
        self,
    ) -> Tuple[
        Dict[Tuple[str, int], Dict[str, Any]],
        Dict[Tuple[str, Optional[int]], List[Dict[str, Any]]],
        int,
    ]:
        """Build exact TMDB and conservative title/year indexes for previews."""

        catalog: Dict[Tuple[str, int], Dict[str, Any]] = {}
        title_index: Dict[
            Tuple[str, Optional[int]], List[Dict[str, Any]]
        ] = {}
        duplicate_count = 0
        for item in self._paged_items("Movie,Series"):
            media_type = "movie" if item.get("Type") == "Movie" else "tv"
            year = self._safe_year(item.get("ProductionYear"))
            record = {
                "id": str(item.get("Id")),
                "name": item.get("Name"),
                "original_title": item.get("OriginalTitle"),
                "year": year,
                "media_type": media_type,
                "poster_tag": (item.get("ImageTags") or {}).get("Primary"),
            }
            for title in {item.get("Name"), item.get("OriginalTitle")}:
                normalized = self.normalize_title(title)
                if normalized:
                    title_index.setdefault((normalized, year), []).append(record)

            provider_ids = item.get("ProviderIds") or {}
            tmdb_id = (
                provider_ids.get("Tmdb")
                or provider_ids.get("TMDb")
                or provider_ids.get("TMDB")
            )
            try:
                tmdb_id = int(tmdb_id)
            except (TypeError, ValueError):
                continue
            key = (media_type, tmdb_id)
            if key in catalog:
                duplicate_count += 1
                continue
            record["tmdb_id"] = tmdb_id
            catalog[key] = record
        return catalog, title_index, duplicate_count

    @staticmethod
    def normalize_title(value: Any) -> str:
        return re.sub(
            r"[^0-9a-z\u3400-\u9fff\uac00-\ud7af]+",
            "",
            str(value or "").lower(),
        )

    @staticmethod
    def _safe_year(value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def find_collection(self, name: str) -> Optional[str]:
        for item in self.list_collections():
            if str(item.get("name") or "").strip() == name.strip():
                return str(item.get("id"))
        return None

    def list_collections(self) -> List[Dict[str, Any]]:
        """Return BoxSet metadata used for inventory and portable backups."""

        result: List[Dict[str, Any]] = []
        fields = (
            "ProviderIds,Overview,SortName,Tags,ImageTags,"
            "LockData,LockedFields"
        )
        for item in self._paged_items("BoxSet", fields=fields):
            result.append(
                {
                    "id": str(item.get("Id") or ""),
                    "name": item.get("Name"),
                    "sort_name": item.get("SortName"),
                    "overview": item.get("Overview"),
                    "provider_ids": item.get("ProviderIds") or {},
                    "tags": item.get("Tags") or [],
                    "lock_data": item.get("LockData"),
                    "locked_fields": item.get("LockedFields") or [],
                    "image_tag": (item.get("ImageTags") or {}).get("Primary"),
                }
            )
        return result

    def get_collection_item_ids(self, collection_id: str) -> Set[str]:
        return self._collection_item_ids(collection_id)

    def get_collection_poster(self, collection_id: str) -> Optional[bytes]:
        """Download a bounded primary image suitable for a local backup."""

        params = {
            "MaxWidth": 800,
            "Quality": 88,
            "api_key": "[APIKEY]",
        }
        url = (
            f"[HOST]emby/Items/{collection_id}/Images/Primary?"
            f"{urlencode(params, safe='[]')}"
        )
        response = self._emby.get_data(url=url)
        if not response or response.status_code != 200 or not response.content:
            return None
        return bytes(response.content)

    def restore_collection(
        self,
        record: Dict[str, Any],
        poster: Optional[bytes] = None,
        existing_id: Optional[str] = None,
    ) -> EmbySyncResult:
        """Create or merge one backed-up collection without removing new members."""

        name = str(record.get("name") or "").strip()
        if not name:
            raise ValueError("备份中的合集名称为空")
        desired = {
            str(item_id) for item_id in (record.get("item_ids") or []) if item_id
        }
        collection_id = str(existing_id or "")
        created = False
        added = 0
        if not collection_id:
            collection_id = self._create_collection(name, sorted(desired))
            created = True
            added = len(desired)
        else:
            current = self._collection_item_ids(collection_id)
            to_add = desired - current
            if to_add:
                self._change_items(collection_id, to_add, remove=False)
            added = len(to_add)

        self._update_collection_metadata(collection_id, record)
        if poster:
            self.set_collection_poster(collection_id, poster)
        return EmbySyncResult(
            collection_id=collection_id,
            created=created,
            added=added,
            removed=0,
        )

    def sync_collection(
        self,
        name: str,
        item_ids: Iterable[str],
        mode: str = "sync",
    ) -> EmbySyncResult:
        desired: Set[str] = {str(item_id) for item_id in item_ids if item_id}
        if not desired:
            raise ValueError("没有匹配到任何 Emby 媒体，已跳过以避免创建或清空合集")

        collection_id = self.find_collection(name)
        if not collection_id:
            collection_id = self._create_collection(name, sorted(desired))
            return EmbySyncResult(
                collection_id=collection_id,
                created=True,
                added=len(desired),
                removed=0,
            )

        current = self._collection_item_ids(collection_id)
        to_add = desired - current
        to_remove = current - desired if mode == "sync" else set()
        if to_add:
            self._change_items(collection_id, to_add, remove=False)
        if to_remove:
            self._change_items(collection_id, to_remove, remove=True)
        return EmbySyncResult(
            collection_id=collection_id,
            created=False,
            added=len(to_add),
            removed=len(to_remove),
        )

    def _paged_items(
        self,
        include_types: str,
        fields: str = "ProviderIds,ProductionYear,OriginalTitle,ImageTags",
    ) -> Iterable[dict]:
        start = 0
        limit = 500
        while True:
            params = {
                "Recursive": "true",
                "IncludeItemTypes": include_types,
                "Fields": fields,
                "StartIndex": start,
                "Limit": limit,
                "api_key": "[APIKEY]",
            }
            url = f"[HOST]emby/Users/[USER]/Items?{urlencode(params, safe='[]')}"
            response = self._emby.get_data(url=url)
            if not response or response.status_code != 200:
                code = response.status_code if response is not None else "无响应"
                raise RuntimeError(f"读取 Emby 媒体库失败：{code}")
            payload = response.json() or {}
            items: List[dict] = payload.get("Items") or []
            for item in items:
                yield item
            start += len(items)
            total = int(payload.get("TotalRecordCount") or start)
            if not items or start >= total:
                break

    def _collection_item_ids(self, collection_id: str) -> Set[str]:
        params = {
            "ParentId": collection_id,
            "Recursive": "false",
            "IncludeItemTypes": "Movie,Series",
            "Fields": "ProviderIds",
            "api_key": "[APIKEY]",
        }
        url = f"[HOST]emby/Users/[USER]/Items?{urlencode(params, safe='[]')}"
        response = self._emby.get_data(url=url)
        if not response or response.status_code != 200:
            code = response.status_code if response is not None else "无响应"
            raise RuntimeError(f"读取 Emby 合集成员失败：{code}")
        return {
            str(item.get("Id"))
            for item in (response.json() or {}).get("Items", [])
            if item.get("Id")
        }

    def _create_collection(self, name: str, item_ids: List[str]) -> str:
        params = {
            "Name": name,
            "IsLocked": "false",
            "Ids": ",".join(item_ids),
            "api_key": "[APIKEY]",
        }
        url = f"[HOST]emby/Collections?{urlencode(params, safe='[]')}"
        response = self._emby.post_data(url=url)
        if not response or response.status_code not in {200, 201, 204}:
            code = response.status_code if response is not None else "无响应"
            raise RuntimeError(f"创建 Emby 合集失败：{code}")
        try:
            payload = response.json() if response.content else {}
        except ValueError:
            payload = {}
        collection_id = payload.get("Id")
        if not collection_id:
            collection_id = self.find_collection(name)
        if not collection_id:
            raise RuntimeError("Emby 已接受创建请求，但未返回合集 ID")
        return str(collection_id)

    def _change_items(
        self, collection_id: str, item_ids: Iterable[str], remove: bool
    ) -> None:
        path = "Items/Delete" if remove else "Items"
        params = {
            "Ids": ",".join(sorted(str(item_id) for item_id in item_ids)),
            "api_key": "[APIKEY]",
        }
        url = (
            f"[HOST]emby/Collections/{collection_id}/{path}?"
            f"{urlencode(params, safe='[]')}"
        )
        response = self._emby.post_data(url=url)
        if not response or response.status_code not in {200, 201, 204}:
            action = "移除" if remove else "添加"
            code = response.status_code if response is not None else "无响应"
            raise RuntimeError(f"向 Emby 合集{action}成员失败：{code}")

    def _update_collection_metadata(
        self, collection_id: str, record: Dict[str, Any]
    ) -> None:
        detail_url = (
            f"[HOST]emby/Users/[USER]/Items/{collection_id}?api_key=[APIKEY]"
        )
        response = self._emby.get_data(url=detail_url)
        if not response or response.status_code != 200:
            code = response.status_code if response is not None else "无响应"
            raise RuntimeError(f"读取新建合集信息失败：{code}")
        payload = response.json() or {}
        mapping = {
            "Name": "name",
            "SortName": "sort_name",
            "Overview": "overview",
            "ProviderIds": "provider_ids",
            "Tags": "tags",
            "LockData": "lock_data",
            "LockedFields": "locked_fields",
        }
        for target, source in mapping.items():
            if source in record and record.get(source) is not None:
                payload[target] = record.get(source)
        update_url = f"[HOST]emby/Items/{collection_id}?api_key=[APIKEY]"
        update_response = self._emby.post_data(
            url=update_url,
            data=json.dumps(payload, ensure_ascii=False),
            headers={"Content-Type": "application/json"},
        )
        if not update_response or update_response.status_code not in {200, 204}:
            code = (
                update_response.status_code
                if update_response is not None
                else "无响应"
            )
            raise RuntimeError(f"恢复 Emby 合集元数据失败：{code}")

    def delete_collection(self, collection_id: str) -> None:
        """Delete one Emby BoxSet by id."""

        host = str(getattr(self._emby, "_host", "") or "")
        api_key = str(getattr(self._emby, "_apikey", "") or "")
        if not host or not api_key:
            raise RuntimeError("Emby 连接信息不完整")
        params = {"api_key": api_key}
        url = f"{host}emby/Items/{collection_id}?{urlencode(params)}"
        response = RequestUtils().delete_res(url=url)
        if not response or response.status_code not in {200, 202, 204}:
            code = response.status_code if response is not None else "无响应"
            raise RuntimeError(f"删除 Emby 合集失败：{code}")

    def get_item_url(self, item_id: str) -> Optional[str]:
        """Return the configured Emby web page for one library item."""

        if not item_id or not hasattr(self._emby, "get_play_url"):
            return None
        return self._emby.get_play_url(str(item_id))

    def set_collection_poster(self, collection_id: str, image: bytes) -> None:
        """Upload JPEG bytes as the collection primary image."""

        if not collection_id or not image:
            raise ValueError("合集 ID 或海报内容为空")
        url = f"[HOST]emby/Items/{collection_id}/Images/Primary?api_key=[APIKEY]"
        response = self._emby.post_data(
            url=url,
            data=base64.b64encode(image).decode("ascii"),
            headers={"Content-Type": "image/jpeg"},
        )
        if not response or response.status_code not in {200, 201, 202, 204}:
            code = response.status_code if response is not None else "无响应"
            raise RuntimeError(f"设置 Emby 合集海报失败：{code}")
