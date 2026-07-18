"""Small TMDB v4 client used by the optional list export workflow.

The plugin already uses the application's TMDB *read* token for public list
lookups.  Writing a list is different: TMDB requires a user access token, so
this module deliberately keeps the two credentials separate.
"""

from typing import Any, Dict, Iterable, List, Optional

from app.core.config import settings
from app.utils.http import RequestUtils


class TmdbListClient:
    """TMDB v4 user-auth and mixed movie/TV list operations."""

    def __init__(
        self,
        application_token: str,
        user_token: Optional[str] = None,
        proxies: Optional[dict] = None,
    ) -> None:
        self._application_token = str(application_token or "").strip()
        self._user_token = str(user_token or "").strip()
        self._proxies = proxies
        domain = str(getattr(settings, "TMDB_API_DOMAIN", "") or "api.themoviedb.org")
        self._base_url = f"https://{domain}/4"

    @staticmethod
    def list_url(list_id: Any) -> str:
        return f"https://www.themoviedb.org/list/{int(list_id)}"

    def create_request_token(self) -> Dict[str, Any]:
        self._require_application_token()
        payload = self._post(
            "/auth/request_token",
            {},
            token=self._application_token,
        )
        request_token = str(payload.get("request_token") or "").strip()
        if not request_token:
            raise RuntimeError("TMDB 未返回授权请求令牌")
        return {
            "request_token": request_token,
            "expires_at": payload.get("expires_at"),
        }

    def create_access_token(self, request_token: str) -> Dict[str, Any]:
        self._require_application_token()
        payload = self._post(
            "/auth/access_token",
            {"request_token": str(request_token or "").strip()},
            token=self._application_token,
        )
        access_token = str(payload.get("access_token") or "").strip()
        if not access_token:
            raise RuntimeError("TMDB 未返回用户访问令牌；请重新授权")
        return {
            "access_token": access_token,
            "account_id": payload.get("account_id"),
        }

    def create_list(self, name: str, description: str, language: str) -> int:
        self._require_user_token()
        iso_language = str(language or "zh").strip().replace("_", "-").split("-", 1)[0]
        payload = self._post(
            "/list",
            {
                "name": str(name or "").strip(),
                "description": str(description or "").strip(),
                "iso_639_1": iso_language or "zh",
                # TMDB v4 validates list metadata as a complete object.  Some
                # accounts reject a create request when region/public are omitted.
                "iso_3166_1": "CN",
                "public": True,
            },
        )
        try:
            return int(payload.get("id") or payload.get("list_id"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("TMDB 未返回新片单 ID") from exc

    def add_items(self, list_id: Any, items: Iterable[Dict[str, Any]]) -> int:
        """Add mixed movie/TV entries in small resilient batches."""

        self._require_user_token()
        normalized: List[Dict[str, Any]] = []
        seen = set()
        for item in items:
            media_type = str((item or {}).get("media_type") or "").strip()
            try:
                media_id = int((item or {}).get("tmdb_id"))
            except (TypeError, ValueError):
                continue
            if media_type not in {"movie", "tv"}:
                continue
            key = (media_type, media_id)
            if key in seen:
                continue
            seen.add(key)
            normalized.append({"media_type": media_type, "media_id": media_id})

        for offset in range(0, len(normalized), 100):
            self._post(
                f"/list/{int(list_id)}/items",
                {"items": normalized[offset : offset + 100]},
            )
        return len(normalized)

    def _headers(self, token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json;charset=utf-8",
            "User-Agent": str(getattr(settings, "USER_AGENT", "MoviePilot")),
        }

    def _post(
        self, path: str, body: Dict[str, Any], token: Optional[str] = None
    ) -> Dict[str, Any]:
        credential = str(token or self._user_token or "").strip()
        response = RequestUtils(
            headers=self._headers(credential), proxies=self._proxies, timeout=30
        ).post_res(f"{self._base_url}{path}", json=body)
        if not response or response.status_code not in {200, 201}:
            status = response.status_code if response is not None else "无响应"
            detail = ""
            if response is not None:
                try:
                    payload = response.json() or {}
                    detail = str(payload.get("status_message") or payload.get("message") or "")
                except Exception:
                    detail = ""
            suffix = f"：{detail}" if detail else ""
            raise RuntimeError(f"TMDB 请求失败（{status}）{suffix}（{path}）")
        try:
            return response.json() or {}
        except Exception as exc:
            raise RuntimeError("TMDB 返回了无法识别的数据") from exc

    def _require_application_token(self) -> None:
        if not self._application_token:
            raise ValueError("请先在插件设置中填写 TMDB v4 Read Access Token")

    def _require_user_token(self) -> None:
        if not self._user_token:
            raise ValueError("请先连接你的 TMDB 账号")
