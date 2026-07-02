import html
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.utils.http import RequestUtils


POPULAR_TMDB_LISTS = [
    {
        "title": "TMDB 本周热门电影",
        "value": "trending_movies_week",
        "path": "/3/trending/movie/week",
        "url": "https://www.themoviedb.org/trending/movie/week",
        "media_type": "movie",
    },
    {
        "title": "TMDB 本周热门剧集",
        "value": "trending_tv_week",
        "path": "/3/trending/tv/week",
        "url": "https://www.themoviedb.org/trending/tv/week",
        "media_type": "tv",
    },
    {
        "title": "TMDB 热门电影",
        "value": "popular_movies",
        "path": "/3/movie/popular",
        "url": "https://www.themoviedb.org/movie",
        "media_type": "movie",
    },
    {
        "title": "TMDB 高分电影",
        "value": "top_rated_movies",
        "path": "/3/movie/top_rated",
        "url": "https://www.themoviedb.org/movie/top-rated",
        "media_type": "movie",
    },
    {
        "title": "TMDB 热门剧集",
        "value": "popular_tv",
        "path": "/3/tv/popular",
        "url": "https://www.themoviedb.org/tv",
        "media_type": "tv",
    },
    {
        "title": "TMDB 高分剧集",
        "value": "top_rated_tv",
        "path": "/3/tv/top_rated",
        "url": "https://www.themoviedb.org/tv/top-rated",
        "media_type": "tv",
    },
    # Keep the historical value for saved configurations; the old display title
    # incorrectly described TMDB List 8648843 as an animated-feature list.
    {"title": "奥斯卡历届最佳影片", "value": "finly_oscars_animation", "list_id": "8648843", "media_type": "movie"},
    {"title": "历届金球奖电影精选", "value": "finly_golden_globes", "list_id": "8648849", "media_type": "movie"},
    {"title": "历届英国电影学院奖精选", "value": "finly_bafta", "list_id": "8648848", "media_type": "movie"},
    {"title": "戛纳电影节精选", "value": "finly_cannes", "list_id": "8648844", "media_type": "movie"},
    {"title": "威尼斯电影节精选", "value": "finly_venice", "list_id": "8648854", "media_type": "movie"},
    {"title": "IMDb Top 250 电影", "value": "finly_imdb_movies", "list_id": "8647021", "media_type": "movie"},
    {"title": "IMDb Top 250 剧集", "value": "finly_imdb_tv", "list_id": "8647022", "media_type": "tv"},
    {"title": "豆瓣电影 Top 250", "value": "finly_douban_top250", "list_id": "8647023", "media_type": "movie"},
    {"title": "Letterboxd Top 500", "value": "finly_letterboxd_500", "list_id": "8648802", "media_type": "movie"},
    {"title": "Letterboxd Top 250 动画长片", "value": "finly_letterboxd_animation_250", "list_id": "8649225", "media_type": "movie"},
    {"title": "Criterion Collection 精选", "value": "finly_criterion", "list_id": "8649108", "media_type": "movie"},
]


for _definition in POPULAR_TMDB_LISTS:
    if _definition.get("list_id") and not _definition.get("url"):
        _definition["url"] = (
            f"https://www.themoviedb.org/list/{_definition['list_id']}"
        )


POPULAR_DOUBAN_LISTS = [
    {"title": "豆瓣高分电影榜（上）9.7–8.6", "value": "240962"},
    {"title": "豆瓣高分电影榜（中）8.5–8.3", "value": "243559"},
    {"title": "豆瓣高分电影榜（下）8.2–8.0", "value": "248893"},
    {"title": "豆瓣冷门佳片（上）", "value": "13922"},
    {"title": "豆瓣冷门佳片（下）", "value": "249029"},
    {"title": "豆瓣高分动画长片", "value": "223781"},
    {"title": "豆瓣电影 Top 250", "value": "30299"},
    {"title": "豆瓣五星电影", "value": "515203"},
    {"title": "豆瓣高分科幻片", "value": "40435"},
    {"title": "豆瓣高分喜剧片", "value": "110522"},
    {"title": "豆瓣高分爱情片", "value": "213727"},
    {"title": "豆瓣高分悬疑片", "value": "172901"},
]


@dataclass(frozen=True)
class MediaRef:
    """A source item before it is matched to an Emby library item."""

    media_type: Optional[str] = None
    tmdb_id: Optional[int] = None
    douban_id: Optional[str] = None
    title: Optional[str] = None
    year: Optional[int] = None
    poster_url: Optional[str] = None


@dataclass
class CollectionSpec:
    """One configured Emby collection and the source that feeds it."""

    source_type: str
    name: Optional[str] = None
    url: Optional[str] = None
    list_id: Optional[str] = None
    items: List[Any] = field(default_factory=list)
    mode: Optional[str] = None


@dataclass
class ResolvedSource:
    """A source after its public list has been downloaded and parsed."""

    title: Optional[str]
    items: List[MediaRef]


class SourceResolver:
    """Fetch TMDB lists, public Douban doulists and inline templates."""

    _TMDB_LIST_RE = re.compile(r"(?:themoviedb\.org/(?:[^/]+/)?list/)?(\d+)", re.I)
    _DOUBAN_LIST_RE = re.compile(r"(?:douban\.com/doulist/)?(\d+)", re.I)
    _DOUBAN_SUBJECT_RE = re.compile(
        r"https?://movie\.douban\.com/subject/(\d+)/?", re.I
    )

    def __init__(
        self,
        tmdb_token: str = "",
        language: str = "zh-CN",
        max_items: int = 500,
        use_proxy: bool = False,
    ):
        self._tmdb_token = (tmdb_token or "").strip()
        self._language = language or "zh-CN"
        self._max_items = max(1, min(int(max_items or 500), 5000))
        self._proxies = settings.PROXY if use_proxy else None

    @staticmethod
    def parse_specs(raw: Any) -> List[CollectionSpec]:
        """Parse and validate the JSON stored in the plugin configuration."""

        if raw is None or raw == "":
            return []
        if isinstance(raw, str):
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"合集定义不是有效的 JSON：第 {exc.lineno} 行第 {exc.colno} 列"
                ) from exc
        else:
            payload = raw

        if isinstance(payload, dict):
            payload = payload.get("collections")
        if not isinstance(payload, list):
            raise ValueError("合集定义必须是 JSON 数组")

        specs: List[CollectionSpec] = []
        for index, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"第 {index} 个合集定义必须是对象")
            if item.get("enabled") is False:
                continue

            source_type = str(item.get("type") or item.get("source") or "").lower().strip()
            aliases = {
                "tmdb_list": "tmdb",
                "tmdb-list": "tmdb",
                "doulist": "douban",
                "豆瓣": "douban",
                "模板": "template",
            }
            source_type = aliases.get(source_type, source_type)
            if source_type not in {"tmdb", "tmdb_builtin", "douban", "template"}:
                raise ValueError(
                    f"第 {index} 个合集的 type 必须是 tmdb、douban 或 template"
                )

            name = str(item.get("name") or "").strip() or None
            url = str(item.get("url") or "").strip() or None
            list_id = str(item.get("list_id") or item.get("id") or "").strip() or None
            template_items = item.get("items") or []
            mode = str(item.get("mode") or "").lower().strip() or None
            if mode and mode not in {"sync", "append"}:
                raise ValueError(f"第 {index} 个合集的 mode 必须是 sync 或 append")

            if source_type in {"tmdb", "tmdb_builtin", "douban"} and not (
                url or list_id
            ):
                raise ValueError(f"第 {index} 个合集缺少 url 或 list_id")
            if source_type == "template":
                if not name:
                    raise ValueError(f"第 {index} 个模板合集缺少 name")
                if not isinstance(template_items, list) or not template_items:
                    raise ValueError(f"第 {index} 个模板合集缺少 items")

            specs.append(
                CollectionSpec(
                    source_type=source_type,
                    name=name,
                    url=url,
                    list_id=list_id,
                    items=template_items,
                    mode=mode,
                )
            )
        return specs

    def fetch(self, spec: CollectionSpec) -> ResolvedSource:
        if spec.source_type == "tmdb":
            return self._fetch_tmdb_list(spec.url or spec.list_id or "")
        if spec.source_type == "tmdb_builtin":
            return self._fetch_tmdb_builtin(spec.list_id or "")
        if spec.source_type == "douban":
            return self._fetch_douban_list(spec.url or spec.list_id or "")
        return self._parse_template(spec)

    @classmethod
    def source_url(cls, spec: CollectionSpec) -> Optional[str]:
        """Return a browser-friendly canonical URL for a collection source."""

        if spec.url:
            return spec.url
        if spec.source_type == "tmdb_builtin":
            definition = next(
                (
                    item
                    for item in POPULAR_TMDB_LISTS
                    if item["value"] == str(spec.list_id or "")
                ),
                None,
            )
            if not definition:
                return None
            return str(definition.get("url") or "") or None
        if spec.source_type == "tmdb":
            match = cls._TMDB_LIST_RE.search(str(spec.list_id or ""))
            return (
                f"https://www.themoviedb.org/list/{match.group(1)}"
                if match
                else None
            )
        if spec.source_type == "douban":
            match = cls._DOUBAN_LIST_RE.search(str(spec.list_id or ""))
            return (
                f"https://www.douban.com/doulist/{match.group(1)}/"
                if match
                else None
            )
        return None

    @classmethod
    def spec_from_url(cls, url: str) -> CollectionSpec:
        """Build a source definition from a public TMDB List or Douban doulist URL."""

        value = str(url or "").strip()
        lowered = value.lower()
        if "themoviedb.org" in lowered and "/list/" in lowered:
            match = cls._TMDB_LIST_RE.search(value)
            if match:
                return CollectionSpec(source_type="tmdb", list_id=match.group(1))
        if "douban.com" in lowered and "/doulist/" in lowered:
            match = cls._DOUBAN_LIST_RE.search(value)
            if match:
                return CollectionSpec(source_type="douban", list_id=match.group(1))
        raise ValueError(f"不支持的片单链接：{value}")

    def _fetch_tmdb_builtin(self, list_key: str) -> ResolvedSource:
        definition = next(
            (item for item in POPULAR_TMDB_LISTS if item["value"] == list_key),
            None,
        )
        if not definition:
            raise ValueError(f"未知的热门 TMDB 片单：{list_key}")

        if definition.get("list_id"):
            resolved = self._fetch_tmdb_list(str(definition["list_id"]))
            resolved.title = definition["title"]
            return resolved

        domain = settings.TMDB_API_DOMAIN or "api.themoviedb.org"
        url = f"https://{domain}{definition['path']}"
        headers = {
            "Accept": "application/json",
            "User-Agent": settings.USER_AGENT,
        }
        params: Dict[str, Any] = {"language": self._language}
        if self._tmdb_token:
            headers["Authorization"] = f"Bearer {self._tmdb_token}"
        else:
            params["api_key"] = settings.TMDB_API_KEY

        media_items: List[MediaRef] = []
        page = 1
        while len(media_items) < self._max_items:
            params["page"] = page
            response = RequestUtils(
                headers=headers, proxies=self._proxies, timeout=30
            ).get_res(url, params=params)
            if not response or response.status_code != 200:
                code = response.status_code if response is not None else "无响应"
                raise RuntimeError(f"热门 TMDB 片单请求失败：{code}")
            payload = response.json() or {}
            results = payload.get("results") or []
            media_items.extend(
                self._tmdb_items(results, default_media_type=definition["media_type"])
            )
            total_pages = int(payload.get("total_pages") or 1)
            if not results or page >= total_pages:
                break
            page += 1

        return ResolvedSource(
            title=definition["title"], items=media_items[: self._max_items]
        )

    def _fetch_tmdb_list(self, value: str) -> ResolvedSource:
        match = self._TMDB_LIST_RE.search(value)
        if not match:
            raise ValueError(f"无法从 {value!r} 提取 TMDB List ID")
        list_id = match.group(1)

        if self._tmdb_token:
            try:
                return self._fetch_tmdb_v4(list_id)
            except Exception:
                # Public legacy lists can still be available through v3. The caller
                # receives the v3 error if both paths fail.
                pass
        return self._fetch_tmdb_v3(list_id)

    def _fetch_tmdb_v4(self, list_id: str) -> ResolvedSource:
        domain = settings.TMDB_API_DOMAIN or "api.themoviedb.org"
        url = f"https://{domain}/4/list/{list_id}"
        headers = {
            "Authorization": f"Bearer {self._tmdb_token}",
            "Accept": "application/json",
            "User-Agent": settings.USER_AGENT,
        }
        title: Optional[str] = None
        media_items: List[MediaRef] = []
        page = 1

        while len(media_items) < self._max_items:
            response = RequestUtils(
                headers=headers, proxies=self._proxies, timeout=30
            ).get_res(url, params={"language": self._language, "page": page})
            if not response or response.status_code != 200:
                code = response.status_code if response is not None else "无响应"
                raise RuntimeError(f"TMDB v4 List 请求失败：{code}")
            payload = response.json() or {}
            title = title or payload.get("name")
            results = payload.get("results") or []
            media_items.extend(self._tmdb_items(results))
            total_pages = int(payload.get("total_pages") or 1)
            if not results or page >= total_pages:
                break
            page += 1

        return ResolvedSource(title=title, items=media_items[: self._max_items])

    def _fetch_tmdb_v3(self, list_id: str) -> ResolvedSource:
        domain = settings.TMDB_API_DOMAIN or "api.themoviedb.org"
        url = f"https://{domain}/3/list/{list_id}"
        response = RequestUtils(
            ua=settings.USER_AGENT, proxies=self._proxies, timeout=30
        ).get_res(
            url,
            params={
                "api_key": settings.TMDB_API_KEY,
                "language": self._language,
            },
        )
        if not response or response.status_code != 200:
            code = response.status_code if response is not None else "无响应"
            raise RuntimeError(
                f"TMDB List 请求失败：{code}；新版混合片单请配置 TMDB v4 Read Access Token"
            )
        payload = response.json() or {}
        items = self._tmdb_items(payload.get("items") or [])
        return ResolvedSource(
            title=payload.get("name"), items=items[: self._max_items]
        )

    @staticmethod
    def _tmdb_items(
        items: List[Dict[str, Any]], default_media_type: Optional[str] = None
    ) -> List[MediaRef]:
        result: List[MediaRef] = []
        seen = set()
        for item in items:
            media_type = str(item.get("media_type") or default_media_type or "").lower()
            if media_type not in {"movie", "tv"}:
                media_type = "movie" if item.get("title") is not None else "tv"
            tmdb_id = item.get("id")
            try:
                tmdb_id = int(tmdb_id)
            except (TypeError, ValueError):
                continue
            key = (media_type, tmdb_id)
            if key in seen:
                continue
            seen.add(key)
            result.append(
                MediaRef(
                    media_type=media_type,
                    tmdb_id=tmdb_id,
                    title=item.get("title") or item.get("name"),
                    year=SourceResolver._extract_year(
                        item.get("release_date") or item.get("first_air_date")
                    ),
                    poster_url=SourceResolver._tmdb_poster(item.get("poster_path")),
                )
            )
        return result

    @staticmethod
    def _extract_year(value: Any) -> Optional[int]:
        match = re.search(r"(?:19|20)\d{2}", str(value or ""))
        return int(match.group(0)) if match else None

    @staticmethod
    def _tmdb_poster(value: Any) -> Optional[str]:
        path = str(value or "").strip()
        if not path:
            return None
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"https://image.tmdb.org/t/p/w342/{path.lstrip('/')}"

    def _fetch_douban_list(self, value: str) -> ResolvedSource:
        match = self._DOUBAN_LIST_RE.search(value)
        if not match:
            raise ValueError(f"无法从 {value!r} 提取豆瓣豆列 ID")
        list_id = match.group(1)
        url = f"https://www.douban.com/doulist/{list_id}/"
        title: Optional[str] = None
        subject_items: List[MediaRef] = []
        seen = set()
        start = 0

        while len(subject_items) < self._max_items:
            response = RequestUtils(
                ua=settings.USER_AGENT,
                proxies=self._proxies,
                timeout=30,
                referer="https://www.douban.com/",
                accept_type="text/html,application/xhtml+xml",
            ).get_res(
                url,
                params={
                    "start": start,
                    "sort": "seq",
                    "playable": 0,
                    "sub_type": "",
                },
            )
            if not response or response.status_code != 200:
                code = response.status_code if response is not None else "无响应"
                raise RuntimeError(f"豆瓣豆列请求失败：{code}")

            page_html = response.text or ""
            if title is None:
                title_match = re.search(
                    r"<h1[^>]*>\s*<span[^>]*>(.*?)</span>",
                    page_html,
                    flags=re.I | re.S,
                )
                if title_match:
                    title = self._clean_html(title_match.group(1))

            page_items = self._parse_douban_page(page_html)
            if not page_items:
                page_items = [
                    MediaRef(media_type="movie", douban_id=subject_id)
                    for subject_id in self._DOUBAN_SUBJECT_RE.findall(page_html)
                ]
            new_count = 0
            for item in page_items:
                if not item.douban_id or item.douban_id in seen:
                    continue
                seen.add(item.douban_id)
                subject_items.append(item)
                new_count += 1
                if len(subject_items) >= self._max_items:
                    break

            if new_count == 0:
                break
            start += 25

        return ResolvedSource(
            title=title,
            items=subject_items,
        )

    @classmethod
    def _parse_douban_page(cls, page_html: str) -> List[MediaRef]:
        """Parse public doulist cards while retaining data useful for preview/fallback."""

        blocks = re.findall(
            r'<div\s+id="[^"]+"\s+class="doulist-item"[^>]*>'
            r"([\s\S]*?)(?=<div\s+id=\"[^\"]+\"\s+class=\"doulist-item\"|"
            r'<div\s+class="paginator"|$)',
            page_html or "",
            flags=re.I,
        )
        result: List[MediaRef] = []
        for block in blocks:
            subject_match = cls._DOUBAN_SUBJECT_RE.search(block)
            if not subject_match:
                continue
            title_match = re.search(
                r'<div\s+class="title">\s*<a[^>]*>([\s\S]*?)</a>',
                block,
                flags=re.I,
            )
            title = cls._clean_html(title_match.group(1)) if title_match else None
            if title:
                title = re.sub(r"^播放全片\s*", "", title).strip()
                if re.search(r"[\u4e00-\u9fff]", title):
                    title = re.sub(
                        r"\s+[A-Za-z][A-Za-z0-9\s:'’.,!?&()\-]+$",
                        "",
                        title,
                    ).strip()
            year_match = re.search(r"年份:\s*((?:19|20)\d{2})", block, flags=re.I)
            poster_match = re.search(
                r'<div\s+class="post">[\s\S]*?<img[^>]+src="([^"]+)"',
                block,
                flags=re.I,
            )
            result.append(
                MediaRef(
                    media_type="movie",
                    douban_id=subject_match.group(1),
                    title=title,
                    year=int(year_match.group(1)) if year_match else None,
                    poster_url=html.unescape(poster_match.group(1))
                    if poster_match
                    else None,
                )
            )
        return result

    @staticmethod
    def _clean_html(value: str) -> str:
        return html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()

    @staticmethod
    def _parse_template(spec: CollectionSpec) -> ResolvedSource:
        items: List[MediaRef] = []
        seen = set()
        for value in spec.items:
            if isinstance(value, str):
                match = re.fullmatch(r"\s*(movie|tv)\s*:\s*(\d+)\s*", value, re.I)
                if not match:
                    raise ValueError(
                        f"模板条目 {value!r} 格式错误，应为 movie:TMDBID 或 tv:TMDBID"
                    )
                media_type, tmdb_id = match.group(1).lower(), int(match.group(2))
                title = None
                year = None
                poster_url = None
            elif isinstance(value, dict):
                media_type = str(
                    value.get("type") or value.get("media_type") or ""
                ).lower().strip()
                try:
                    tmdb_id = int(value.get("tmdb_id") or value.get("tmdbid"))
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"模板条目缺少有效的 tmdb_id：{value!r}") from exc
                title = value.get("title")
                year = SourceResolver._extract_year(value.get("year"))
                poster_url = value.get("poster_url") or value.get("poster")
            else:
                raise ValueError(f"不支持的模板条目：{value!r}")

            if media_type not in {"movie", "tv"}:
                raise ValueError(f"模板条目类型必须是 movie 或 tv：{value!r}")
            key = (media_type, tmdb_id)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                MediaRef(
                    media_type=media_type,
                    tmdb_id=tmdb_id,
                    title=title,
                    year=year,
                    poster_url=poster_url,
                )
            )

        return ResolvedSource(title=spec.name, items=items)
