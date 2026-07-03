import html
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.log import logger
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
    {"title": "金球奖最佳剧情片", "value": "finly_golden_globes", "list_id": "8648849", "media_type": "movie"},
    {"title": "英国电影学院奖最佳影片", "value": "finly_bafta", "list_id": "8648848", "media_type": "movie"},
    {"title": "戛纳电影节金棕榈奖", "value": "finly_cannes", "list_id": "8648844", "media_type": "movie"},
    {"title": "威尼斯电影节金狮奖", "value": "finly_venice", "list_id": "8648854", "media_type": "movie"},
    {"title": "IMDb Top 250 Movies", "value": "finly_imdb_movies", "list_id": "8647021", "media_type": "movie"},
    {"title": "IMDb Top 250 TV Shows", "value": "finly_imdb_tv", "list_id": "8647022", "media_type": "tv"},
    {"title": "豆瓣电影 Top 250", "value": "finly_douban_top250", "list_id": "8647023", "media_type": "movie"},
    {"title": "Letterboxd's Top 500 Films", "value": "finly_letterboxd_500", "list_id": "8648802", "media_type": "movie"},
    {"title": "Letterboxd's Top 250 Animated Films", "value": "finly_letterboxd_animation_250", "list_id": "8649225", "media_type": "movie"},
    {"title": "Criterion Collection", "value": "finly_criterion", "list_id": "8649108", "media_type": "movie"},
    # Titles, descriptions and item counts for these public lists are refreshed
    # from TMDB at runtime. The local labels are only offline fallbacks.
    {"title": "TSPDT - 1000 Greatest Films", "value": "tmdb_8648821", "list_id": "8648821"},
    {"title": "Letterboxd's Top 250 Films with the Most Fans", "value": "tmdb_8649224", "list_id": "8649224"},
    {"title": "Letterboxd's Top 250 Documentary Films", "value": "tmdb_8649231", "list_id": "8649231"},
    {"title": "S&S Directors - Greatest Films", "value": "tmdb_8649058", "list_id": "8649058"},
    {"title": "S&S Critics - Greatest Films", "value": "tmdb_8649050", "list_id": "8649050"},
    {"title": "独立精神奖最佳长片", "value": "tmdb_8648851", "list_id": "8648851"},
    {"title": "金球奖最佳音乐/喜剧片", "value": "tmdb_8648850", "list_id": "8648850"},
    {"title": "Roger Ebert's Great Movies", "value": "tmdb_8649219", "list_id": "8649219"},
    {"title": "Every MUBI Film", "value": "tmdb_8649220", "list_id": "8649220"},
    {"title": "Every NEON Film", "value": "tmdb_8649218", "list_id": "8649218"},
    {"title": "Every A24 Film", "value": "tmdb_8649217", "list_id": "8649217"},
    {"title": "AFI Top 100 (2007 Edition)", "value": "tmdb_8649041", "list_id": "8649041"},
]


for _definition in POPULAR_TMDB_LISTS:
    if _definition.get("list_id") and not _definition.get("url"):
        _definition["url"] = (
            f"https://www.themoviedb.org/list/{_definition['list_id']}"
        )


POPULAR_DOUBAN_LISTS = [
    {"title": "★豆瓣高分电影榜★ （上）9.7-8.6分", "value": "240962"},
    {"title": "★豆瓣高分电影榜★ （中）8.5-8.3分", "value": "243559"},
    {"title": "★豆瓣高分电影榜★ （下）8.2-8.0分", "value": "248893"},
    {"title": "【豆瓣冷门佳片】10-8.5分｜评分人数<5000", "value": "13922"},
    {"title": "【豆瓣冷门佳片】8.4-8分｜评分人数<5000", "value": "249029"},
    {"title": "【豆瓣高分动画长片】", "value": "223781"},
    {"title": "豆瓣电影【口碑榜】2023-09-11 更新", "value": "30299"},
    {"title": "历届奥斯卡最佳动画长片及提名", "value": "515203"},
    {"title": "值得一看的电影和美剧", "value": "40435"},
    {"title": "有生之年一定要看的1001部电影", "value": "110522"},
    {"title": "IMDb TV Shows Top 250", "value": "213727", "media_type": "tv"},
    {"title": "【豆瓣五星电视剧】(1/2)", "value": "172901", "media_type": "tv"},
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
    aliases: Tuple[str, ...] = ()


@dataclass
class CollectionSpec:
    """One configured Emby collection and the source that feeds it."""

    source_type: str
    name: Optional[str] = None
    url: Optional[str] = None
    list_id: Optional[str] = None
    items: List[Any] = field(default_factory=list)
    mode: Optional[str] = None
    media_type: Optional[str] = None
    use_source_title: bool = False
    description: Optional[str] = None


@dataclass
class ResolvedSource:
    """A source after its public list has been downloaded and parsed."""

    title: Optional[str]
    items: List[MediaRef]
    description: Optional[str] = None
    reported_total: Optional[int] = None


class SourceResolver:
    """Fetch TMDB lists, public Douban doulists and inline templates."""

    _TMDB_LIST_RE = re.compile(r"(?:themoviedb\.org/(?:[^/]+/)?list/)?(\d+)", re.I)
    _DOUBAN_LIST_RE = re.compile(r"(?:douban\.com/doulist/)?(\d+)", re.I)
    _DOUBAN_SUBJECT_RE = re.compile(
        r"https?://movie\.douban\.com/subject/(\d+)/?", re.I
    )
    _SEASON_RE = re.compile(
        r"(?:第\s*[0-9一二三四五六七八九十百]+\s*季|season\s*\d+)", re.I
    )

    def __init__(
        self,
        tmdb_token: str = "",
        language: str = "zh-CN",
        max_items: int = 2000,
        use_proxy: bool = False,
    ):
        self._tmdb_token = (tmdb_token or "").strip()
        self._language = language or "zh-CN"
        self._max_items = max(1, min(int(max_items or 2000), 5000))
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
                    media_type=str(item.get("media_type") or "").lower().strip()
                    or None,
                    use_source_title=bool(item.get("use_source_title")),
                    description=str(item.get("description") or "").strip() or None,
                )
            )
        return specs

    def fetch(self, spec: CollectionSpec) -> ResolvedSource:
        if spec.source_type == "tmdb":
            return self._fetch_tmdb_list(spec.url or spec.list_id or "")
        if spec.source_type == "tmdb_builtin":
            return self._fetch_tmdb_builtin(spec.list_id or "")
        if spec.source_type == "douban":
            return self._fetch_douban_list(
                spec.url or spec.list_id or "", default_media_type=spec.media_type
            )
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
            return self._fetch_tmdb_list(str(definition["list_id"]))

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
        reported_total: Optional[int] = None
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
            if reported_total is None:
                reported_total = self._safe_total(payload.get("total_results"))
            results = payload.get("results") or []
            media_items.extend(
                self._tmdb_items(results, default_media_type=definition["media_type"])
            )
            total_pages = int(payload.get("total_pages") or 1)
            if not results or page >= total_pages:
                break
            page += 1

        return ResolvedSource(
            title=definition["title"],
            items=media_items[: self._max_items],
            description=str(definition.get("description") or "").strip() or None,
            reported_total=reported_total,
        )

    def _fetch_tmdb_list(self, value: str) -> ResolvedSource:
        match = self._TMDB_LIST_RE.search(value)
        if not match:
            raise ValueError(f"无法从 {value!r} 提取 TMDB List ID")
        list_id = match.group(1)

        if self._tmdb_token:
            try:
                return self._fetch_tmdb_v4(list_id)
            except Exception as exc:
                # Public legacy lists can still be available through v3. The caller
                # receives the v3 error if both paths fail.
                logger.warning(
                    f"TMDB v4 List {list_id} 请求失败，回退 v3 分页读取：{exc}"
                )
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
        description: Optional[str] = None
        reported_total: Optional[int] = None
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
            description = description or payload.get("description")
            if reported_total is None:
                reported_total = self._safe_total(
                    payload.get("total_results") or payload.get("total_items")
                )
            results = payload.get("results") or []
            media_items.extend(self._tmdb_items(results))
            total_pages = int(payload.get("total_pages") or 1)
            if not results or page >= total_pages:
                break
            page += 1

        return ResolvedSource(
            title=title,
            items=media_items[: self._max_items],
            description=str(description or "").strip() or None,
            reported_total=reported_total,
        )

    def _fetch_tmdb_v3(self, list_id: str) -> ResolvedSource:
        domain = settings.TMDB_API_DOMAIN or "api.themoviedb.org"
        url = f"https://{domain}/3/list/{list_id}"
        title: Optional[str] = None
        description: Optional[str] = None
        reported_total: Optional[int] = None
        raw_items: List[Dict[str, Any]] = []
        page = 1
        while len(raw_items) < self._max_items:
            response = RequestUtils(
                ua=settings.USER_AGENT, proxies=self._proxies, timeout=30
            ).get_res(
                url,
                params={
                    "api_key": settings.TMDB_API_KEY,
                    "language": self._language,
                    "page": page,
                },
            )
            if not response or response.status_code != 200:
                code = response.status_code if response is not None else "无响应"
                raise RuntimeError(
                    f"TMDB List 第 {page} 页请求失败：{code}；"
                    "新版混合片单请配置 TMDB v4 Read Access Token"
                )
            payload = response.json() or {}
            title = title or payload.get("name")
            description = description or payload.get("description")
            if reported_total is None:
                reported_total = self._safe_total(
                    payload.get("item_count") or payload.get("total_results")
                )
            page_items = payload.get("items") or []
            raw_items.extend(page_items)
            total_pages = self._safe_total(payload.get("total_pages"))
            if not total_pages and reported_total and page_items:
                total_pages = max(
                    1,
                    (reported_total + len(page_items) - 1) // len(page_items),
                )
            if (
                not page_items
                or (reported_total is not None and len(raw_items) >= reported_total)
                or page >= int(total_pages or 1)
            ):
                break
            page += 1

        items = self._tmdb_items(raw_items)
        return ResolvedSource(
            title=title,
            items=items[: self._max_items],
            description=str(description or "").strip() or None,
            reported_total=reported_total or len(items),
        )

    @staticmethod
    def _safe_total(value: Any) -> Optional[int]:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return None

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

    @classmethod
    def title_candidates(cls, value: Any) -> List[str]:
        """Extract localized/original aliases from one mixed-language title."""

        text = re.sub(r"\s+", " ", cls._clean_html(str(value or ""))).strip()
        if not text:
            return []

        script_count = sum(
            bool(re.search(pattern, text))
            for pattern in (r"[\u3400-\u9fff]", r"[A-Za-z]", r"[\uac00-\ud7af]")
        )
        if script_count > 1:
            segments = [
                match.strip()
                for match in re.findall(
                    r"[\u3400-\u9fff][\u3400-\u9fff0-9第季部篇：:·・—\-（）()《》！？!?、\s]*"
                    r"|[A-Za-z][A-Za-z0-9 .:'’&!?()\-]+"
                    r"|[\uac00-\ud7af][\uac00-\ud7af0-9\s:·・\-]+",
                    text,
                )
                if match.strip()
            ]
        else:
            segments = [text]

        candidates: List[str] = []

        def add(candidate: str) -> None:
            candidate = re.sub(r"\s+", " ", str(candidate or "")).strip(" -:：·")
            normalized = cls._normalize_lookup_title(candidate)
            if len(normalized) < 2:
                return
            if all(
                cls._normalize_lookup_title(item) != normalized
                for item in candidates
            ):
                candidates.append(candidate)

        for segment in segments:
            add(segment)
        for segment in segments:
            add(cls._SEASON_RE.sub("", segment))
        for segment in segments:
            if re.search(r"[\u3400-\u9fff]", segment):
                for part in re.split(r"\s+", segment):
                    if not cls._SEASON_RE.fullmatch(part):
                        add(part)
        return candidates

    @classmethod
    def has_season_marker(cls, media_ref: MediaRef) -> bool:
        return any(
            cls._SEASON_RE.search(value or "")
            for value in (media_ref.title, *media_ref.aliases)
        )

    def resolve_tmdb_by_title(self, media_ref: MediaRef) -> Optional[MediaRef]:
        """Use TMDB search when MoviePilot's Douban-ID lookup is rate limited."""

        queries: List[str] = []
        for value in (media_ref.title, *media_ref.aliases):
            for candidate in self.title_candidates(value):
                if candidate not in queries:
                    queries.append(candidate)
        if not queries:
            return None

        api_key = str(getattr(settings, "TMDB_API_KEY", "") or "").strip()
        if not self._tmdb_token and not api_key:
            return None

        domain = getattr(settings, "TMDB_API_DOMAIN", None) or "api.themoviedb.org"
        url = f"https://{domain}/3/search/multi"
        headers = {
            "Accept": "application/json",
            "User-Agent": settings.USER_AGENT,
        }
        if self._tmdb_token:
            headers["Authorization"] = f"Bearer {self._tmdb_token}"

        best: Optional[Dict[str, Any]] = None
        best_score = -10_000.0
        season_hint = self.has_season_marker(media_ref)
        query_norms = {
            self._normalize_lookup_title(value)
            for value in queries
            if self._normalize_lookup_title(value)
        }

        for query in queries[:6]:
            params: Dict[str, Any] = {
                "query": query,
                "language": self._language,
                "include_adult": "false",
            }
            if not self._tmdb_token:
                params["api_key"] = api_key
            try:
                response = RequestUtils(
                    headers=headers, proxies=self._proxies, timeout=20
                ).get_res(url, params=params)
                if not response or response.status_code != 200:
                    continue
                results = (response.json() or {}).get("results") or []
            except Exception:
                continue

            for result in results:
                media_type = str(result.get("media_type") or "").lower()
                if media_type not in {"movie", "tv"}:
                    continue
                score = self._score_tmdb_search_result(
                    media_ref=media_ref,
                    result=result,
                    query_norms=query_norms,
                    season_hint=season_hint,
                )
                if score > best_score:
                    best = result
                    best_score = score
            if best_score >= 160:
                break

        if not best or best_score < 90:
            return None
        try:
            tmdb_id = int(best.get("id"))
        except (TypeError, ValueError):
            return None
        return MediaRef(
            media_type=str(best.get("media_type")),
            tmdb_id=tmdb_id,
            douban_id=media_ref.douban_id,
            title=best.get("title") or best.get("name") or media_ref.title,
            year=self._extract_year(
                best.get("release_date") or best.get("first_air_date")
            )
            or media_ref.year,
            poster_url=self._tmdb_poster(best.get("poster_path"))
            or media_ref.poster_url,
            aliases=media_ref.aliases,
        )

    def resolve_tmdb_by_id(
        self,
        media_ref: MediaRef,
        media_type: str,
        tmdb_id: int,
    ) -> Optional[MediaRef]:
        """Load canonical TMDB metadata for an Emby title match."""

        if media_type not in {"movie", "tv"} or not tmdb_id:
            return None
        api_key = str(getattr(settings, "TMDB_API_KEY", "") or "").strip()
        if not self._tmdb_token and not api_key:
            return None
        domain = getattr(settings, "TMDB_API_DOMAIN", None) or "api.themoviedb.org"
        headers = {
            "Accept": "application/json",
            "User-Agent": settings.USER_AGENT,
        }
        params: Dict[str, Any] = {"language": self._language}
        if self._tmdb_token:
            headers["Authorization"] = f"Bearer {self._tmdb_token}"
        else:
            params["api_key"] = api_key
        try:
            response = RequestUtils(
                headers=headers, proxies=self._proxies, timeout=20
            ).get_res(
                f"https://{domain}/3/{media_type}/{int(tmdb_id)}",
                params=params,
            )
            if not response or response.status_code != 200:
                return None
            payload = response.json() or {}
        except Exception:
            return None
        return MediaRef(
            media_type=media_type,
            tmdb_id=int(tmdb_id),
            douban_id=media_ref.douban_id,
            title=payload.get("title") or payload.get("name") or media_ref.title,
            year=self._extract_year(
                payload.get("release_date") or payload.get("first_air_date")
            )
            or media_ref.year,
            poster_url=self._tmdb_poster(payload.get("poster_path"))
            or media_ref.poster_url,
            aliases=media_ref.aliases,
        )

    @classmethod
    def _score_tmdb_search_result(
        cls,
        media_ref: MediaRef,
        result: Dict[str, Any],
        query_norms: set,
        season_hint: bool,
    ) -> float:
        media_type = str(result.get("media_type") or "").lower()
        names = {
            cls._normalize_lookup_title(value)
            for value in (
                result.get("title"),
                result.get("name"),
                result.get("original_title"),
                result.get("original_name"),
            )
            if value
        }
        names.discard("")
        score = 0.0
        if names & query_norms:
            score += 120
        elif any(
            query in name or name in query
            for query in query_norms
            for name in names
            if min(len(query), len(name)) >= 3
        ):
            score += 60

        if media_ref.media_type in {"movie", "tv"}:
            score += 25 if media_ref.media_type == media_type else -30
        if season_hint:
            score += 65 if media_type == "tv" else -80

        result_year = cls._extract_year(
            result.get("release_date") or result.get("first_air_date")
        )
        if media_ref.year and result_year and not (season_hint and media_type == "tv"):
            difference = abs(int(media_ref.year) - int(result_year))
            score += 50 if difference == 0 else 25 if difference == 1 else -80
        try:
            score += min(10.0, float(result.get("popularity") or 0) / 10)
        except (TypeError, ValueError):
            pass
        return score

    @staticmethod
    def _normalize_lookup_title(value: Any) -> str:
        return re.sub(
            r"[^0-9a-z\u3400-\u9fff\uac00-\ud7af]+",
            "",
            str(value or "").lower(),
        )

    def _fetch_douban_list(
        self, value: str, default_media_type: Optional[str] = None
    ) -> ResolvedSource:
        match = self._DOUBAN_LIST_RE.search(value)
        if not match:
            raise ValueError(f"无法从 {value!r} 提取豆瓣豆列 ID")
        list_id = match.group(1)
        url = f"https://www.douban.com/doulist/{list_id}/"
        title: Optional[str] = None
        description: Optional[str] = None
        reported_total: Optional[int] = None
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
                description_match = re.search(
                    r'<div\s+class="doulist-about"[^>]*>([\s\S]*?)</div>',
                    page_html,
                    flags=re.I,
                )
                if description_match:
                    description = re.sub(
                        r"\s+", " ", self._clean_html(description_match.group(1))
                    ).strip()
                total_match = re.search(
                    r'<div\s+class="doulist-filter">[\s\S]*?全部\s*<span>\((\d+)\)</span>',
                    page_html,
                    flags=re.I,
                )
                if total_match:
                    reported_total = int(total_match.group(1))

            page_items = self._parse_douban_page(
                page_html, media_type=default_media_type
            )
            if not page_items:
                page_items = [
                    MediaRef(
                        media_type=default_media_type
                        if default_media_type in {"movie", "tv"}
                        else None,
                        douban_id=subject_id,
                    )
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
            description=description,
            reported_total=reported_total,
        )

    @classmethod
    def _parse_douban_page(
        cls, page_html: str, media_type: Optional[str] = None
    ) -> List[MediaRef]:
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
            raw_title = cls._clean_html(title_match.group(1)) if title_match else None
            aliases: Tuple[str, ...] = ()
            title = raw_title
            if title:
                title = re.sub(r"^播放全片\s*", "", title).strip()
                raw_candidates = cls.title_candidates(title)
                if re.search(r"[\u4e00-\u9fff]", title):
                    title = re.sub(
                        r"\s+(?:[A-Za-z]|[\uac00-\ud7af]).*$",
                        "",
                        title,
                    ).strip()
                title_key = cls._normalize_lookup_title(title)
                aliases = tuple(
                    candidate
                    for candidate in raw_candidates
                    if cls._normalize_lookup_title(candidate) != title_key
                )
            year_match = re.search(r"年份:\s*((?:19|20)\d{2})", block, flags=re.I)
            poster_match = re.search(
                r'<div\s+class="post">[\s\S]*?<img[^>]+src="([^"]+)"',
                block,
                flags=re.I,
            )
            result.append(
                MediaRef(
                    media_type=media_type if media_type in {"movie", "tv"} else None,
                    douban_id=subject_match.group(1),
                    title=title,
                    year=int(year_match.group(1)) if year_match else None,
                    poster_url=html.unescape(poster_match.group(1))
                    if poster_match
                    else None,
                    aliases=aliases,
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

        return ResolvedSource(
            title=spec.name,
            items=items,
            description=spec.description,
            reported_total=len(items),
        )
