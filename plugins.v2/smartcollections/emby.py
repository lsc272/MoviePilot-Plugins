from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urlencode


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

        index: Dict[Tuple[str, int], str] = {}
        duplicate_count = 0
        for item in self._paged_items("Movie,Series"):
            media_type = "movie" if item.get("Type") == "Movie" else "tv"
            tmdb_id = (item.get("ProviderIds") or {}).get("Tmdb")
            try:
                tmdb_id = int(tmdb_id)
            except (TypeError, ValueError):
                continue
            key = (media_type, tmdb_id)
            if key in index:
                duplicate_count += 1
                continue
            index[key] = str(item.get("Id"))
        return index, duplicate_count

    def find_collection(self, name: str) -> Optional[str]:
        for item in self._paged_items("BoxSet"):
            if str(item.get("Name") or "").strip() == name.strip():
                return str(item.get("Id"))
        return None

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

    def _paged_items(self, include_types: str) -> Iterable[dict]:
        start = 0
        limit = 500
        while True:
            params = {
                "Recursive": "true",
                "IncludeItemTypes": include_types,
                "Fields": "ProviderIds,ProductionYear",
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
