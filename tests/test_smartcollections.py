import ast
import importlib.util
import io
import json
import sys
import tempfile
import threading
import types
import unittest
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from unittest.mock import patch

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins.v2" / "smartcollections"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


settings = types.SimpleNamespace(
    PROXY=None,
    USER_AGENT="SmartCollections-Test",
    TMDB_API_DOMAIN="api.themoviedb.org",
    TMDB_API_KEY="test",
)
app = types.ModuleType("app")
core = types.ModuleType("app.core")
config = types.ModuleType("app.core.config")
config.settings = settings
utils = types.ModuleType("app.utils")
http = types.ModuleType("app.utils.http")
log = types.ModuleType("app.log")


class TestLogger:
    def warning(self, *_args, **_kwargs):
        pass


log.logger = TestLogger()
class FakeRequestUtils:
    deleted_urls = []
    post_calls = []
    post_responses = []

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    def delete_res(self, url):
        self.deleted_urls.append(url)
        return FakeResponse({}, 204)

    def post_res(self, url, data=None, params=None, json=None, **kwargs):
        self.post_calls.append(
            {"url": url, "data": data, "params": params, "json": json, "headers": self.kwargs.get("headers")}
        )
        if self.post_responses:
            return self.post_responses.pop(0)
        return FakeResponse({}, 200)


http.RequestUtils = FakeRequestUtils
sys.modules.update(
    {
        "app": app,
        "app.core": core,
        "app.core.config": config,
        "app.utils": utils,
        "app.utils.http": http,
        "app.log": log,
    }
)

sources = load_module("smartcollections_sources_test", PLUGIN / "sources.py")
emby = load_module("smartcollections_emby_test", PLUGIN / "emby.py")
poster = load_module("smartcollections_poster_test", PLUGIN / "poster.py")
collection_backup = load_module(
    "smartcollections_collection_backup_test", PLUGIN / "collection_backup.py"
)
tmdb_lists = load_module("smartcollections_tmdb_lists_test", PLUGIN / "tmdb_lists.py")


class FakeResponse:
    def __init__(self, payload, status_code=200, content=b"{}", text=""):
        self._payload = payload
        self.status_code = status_code
        self.content = content
        self.text = text

    def json(self):
        return self._payload


class FakeEmby:
    def __init__(self):
        self.deleted = []
        self.uploaded = []
        self._host = "http://emby/"
        self._apikey = "test-key"

    def get_data(self, url):
        if "IncludeItemTypes=BoxSet" in url:
            return FakeResponse(
                {
                    "TotalRecordCount": 2,
                    "Items": [
                        {
                            "Id": "box1",
                            "Type": "BoxSet",
                            "Name": "测试合集",
                            "SortName": "CSHJ",
                            "Overview": "合集简介",
                            "ProviderIds": {"Tmdb": "10"},
                            "Tags": ["测试"],
                            "ImageTags": {"Primary": "cover1"},
                        },
                        {
                            "Id": "box2",
                            "Type": "BoxSet",
                            "Name": "智能合集",
                            "ProviderIds": {},
                            "ImageTags": {},
                        },
                    ],
                }
            )
        if "ParentId=box1" in url:
            return FakeResponse({"Items": [{"Id": "m1"}]})
        if "/Images/Primary" in url:
            return FakeResponse({}, content=b"poster-bytes")
        if "/Items/box1?" in url:
            return FakeResponse({"Id": "box1", "Name": "测试合集", "Type": "BoxSet"})
        return FakeResponse(
            {
                "TotalRecordCount": 2,
                "Items": [
                    {
                        "Id": "m1",
                        "Type": "Movie",
                        "Name": "测试电影",
                        "OriginalTitle": "Test Movie",
                        "ProductionYear": 2024,
                        "ProviderIds": {"Tmdb": "101"},
                        "ImageTags": {"Primary": "poster1"},
                    },
                    {
                        "Id": "s1",
                        "Type": "Series",
                        "Name": "测试剧集",
                        "ProductionYear": 2023,
                        "ProviderIds": {"Tmdb": "202"},
                        "ImageTags": {},
                    },
                ],
            }
        )

    def post_data(self, url, data=None, headers=None):
        self.uploaded.append((url, data, headers))
        return FakeResponse({}, 204)

    def get_play_url(self, item_id):
        return f"http://emby/web/index.html#!/item?id={item_id}"


class SmartCollectionsTests(unittest.TestCase):
    def test_tmdb_v4_list_export_uses_separate_user_token_and_mixed_items(self):
        FakeRequestUtils.post_calls = []
        FakeRequestUtils.post_responses = [
            FakeResponse({"id": 987}),
            FakeResponse({"status_code": 1}),
        ]
        client = tmdb_lists.TmdbListClient(
            application_token="application-read-token",
            user_token="user-write-token",
        )
        list_id = client.create_list("豆瓣测试", "来自豆列", "zh-CN")
        count = client.add_items(
            list_id,
            [
                {"media_type": "movie", "tmdb_id": 101},
                {"media_type": "tv", "tmdb_id": 202},
                {"media_type": "movie", "tmdb_id": 101},
                {"media_type": "unknown", "tmdb_id": 303},
            ],
        )
        self.assertEqual(list_id, 987)
        self.assertEqual(count, 2)
        self.assertEqual(FakeRequestUtils.post_calls[0]["url"], "https://api.themoviedb.org/4/list")
        self.assertEqual(FakeRequestUtils.post_calls[0]["json"]["name"], "豆瓣测试")
        self.assertEqual(FakeRequestUtils.post_calls[0]["json"]["iso_639_1"], "zh")
        self.assertEqual(
            FakeRequestUtils.post_calls[1]["json"],
            {"items": [{"media_type": "movie", "media_id": 101}, {"media_type": "tv", "media_id": 202}]},
        )
        for call in FakeRequestUtils.post_calls:
            self.assertEqual(call["headers"]["Authorization"], "Bearer user-write-token")
            self.assertNotIn("application-read-token", str(call))

    def test_tmdb_v4_auth_exchange_uses_application_token(self):
        FakeRequestUtils.post_calls = []
        FakeRequestUtils.post_responses = [
            FakeResponse({"request_token": "short-lived", "expires_at": "2026-01-01T00:00:00.000Z"}),
            FakeResponse({"access_token": "user-secret", "account_id": "88"}),
        ]
        client = tmdb_lists.TmdbListClient(application_token="application-read-token")
        pending = client.create_request_token()
        granted = client.create_access_token(pending["request_token"])
        self.assertEqual(granted["account_id"], "88")
        self.assertEqual(
            [call["headers"]["Authorization"] for call in FakeRequestUtils.post_calls],
            ["Bearer application-read-token", "Bearer application-read-token"],
        )

    def test_missing_item_subscription_uses_moviepilot_chain(self):
        source = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        methods = [
            node
            for item in tree.body
            if isinstance(item, ast.ClassDef) and item.name == "SmartCollections"
            for node in item.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"api_subscribe", "_subscribe_item"}
        ]

        class MediaType(Enum):
            MOVIE = "电影"
            TV = "电视剧"

        class FakeSubscribeChain:
            kwargs = None

            def add(self, **kwargs):
                type(self).kwargs = kwargs
                return 42, ""

        class FakeLogger:
            def exception(self, *_args, **_kwargs):
                pass

        class SystemConfigKey(Enum):
            SubscribeFilterRuleGroups = "SubscribeFilterRuleGroups"

        class FakeSystemConfigOper:
            def get(self, key):
                self.assert_key = key
                return ["只要x265"]

        class FakeScheduler:
            calls = []

            def start(self, **kwargs):
                type(self).calls.append(kwargs)

        class FakeThread:
            def __init__(self, target, kwargs, **_options):
                self.target = target
                self.kwargs = kwargs

            def start(self):
                self.target(**self.kwargs)

        namespace = {
            "Any": Any,
            "Dict": Dict,
            "MediaType": MediaType,
            "SubscribeChain": FakeSubscribeChain,
            "Scheduler": FakeScheduler,
            "SystemConfigOper": FakeSystemConfigOper,
            "SystemConfigKey": SystemConfigKey,
            "threading": types.SimpleNamespace(Thread=FakeThread),
            "logger": FakeLogger(),
            "Body": lambda *args, **kwargs: None,
        }
        method_source = "\n".join(ast.unparse(method) for method in methods)
        exec(
            "class Subject:\n"
            + "\n".join(f"    {line}" for line in method_source.splitlines()),
            namespace,
        )
        result = namespace["Subject"]().api_subscribe(
            {"tmdb_id": 101, "media_type": "movie", "title": "测试电影", "year": 2024}
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["subscription_id"], 42)
        self.assertEqual(FakeSubscribeChain.kwargs["tmdbid"], 101)
        self.assertFalse(FakeSubscribeChain.kwargs["message"])
        self.assertEqual(FakeSubscribeChain.kwargs["filter_groups"], ["只要x265"])
        self.assertTrue(result["data"]["search_started"])
        self.assertEqual(
            FakeScheduler.calls[-1],
            {
                "job_id": "subscribe_search",
                "sid": 42,
                "state": None,
                "manual": True,
            },
        )

    def test_douban_conversion_uses_official_media_chain(self):
        source = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("recognize_media(doubanid=", source)
        tree = ast.parse(source)
        method = next(
            node
            for item in tree.body
            if isinstance(item, ast.ClassDef) and item.name == "SmartCollections"
            for node in item.body
            if isinstance(node, ast.FunctionDef) and node.name == "_resolve_media_ref"
        )

        class MediaType(Enum):
            MOVIE = "电影"
            TV = "电视剧"

        @dataclass(frozen=True)
        class MediaRef:
            media_type: Optional[str] = None
            tmdb_id: Optional[int] = None
            douban_id: Optional[str] = None
            title: Optional[str] = None
            year: Optional[int] = None
            poster_url: Optional[str] = None
            aliases: tuple = ()

        class FakeLogger:
            def warning(self, *_args, **_kwargs):
                pass

        class FakeResolver:
            @staticmethod
            def _extract_year(value):
                return 2024 if value else None

            @staticmethod
            def _tmdb_poster(value):
                return f"https://image.tmdb.org/t/p/w342{value}" if value else None

            def resolve_tmdb_by_title(self, _media_ref):
                return None

        class FakeMediaChain:
            result = None

            def get_tmdbinfo_by_doubanid(self, doubanid, mtype=None):
                return self.result

        namespace = {
            "Dict": Dict,
            "Optional": Optional,
            "MediaRef": MediaRef,
            "MediaType": MediaType,
            "MediaChain": FakeMediaChain,
            "SourceResolver": FakeResolver,
            "time": types.SimpleNamespace(monotonic=lambda: 100.0, time=lambda: 1000.0),
            "logger": FakeLogger(),
        }
        method_source = ast.unparse(method)
        exec(
            "class Subject:\n"
            + "\n".join(f"    {line}" for line in method_source.splitlines()),
            namespace,
        )
        subject = namespace["Subject"]()
        subject._douban_chain_cooldown_until = 0
        subject._DOUBAN_FAILURE_CACHE_TTL = 6 * 3600

        FakeMediaChain.result = {
            "id": "303",
            "name": "测试剧集",
            "media_type": "tv",
            "first_air_date": "2024-01-01",
            "poster_path": "/poster.jpg",
        }
        cache = {}
        result = subject._resolve_media_ref(
            MediaRef(douban_id="1001"), cache, FakeResolver()
        )
        self.assertEqual((result.media_type, result.tmdb_id, result.year), ("tv", 303, 2024))
        self.assertEqual(cache["1001"]["title"], "测试剧集")

    def test_douban_rate_limit_falls_back_to_tmdb_title_search(self):
        source = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        method = next(
            node
            for item in tree.body
            if isinstance(item, ast.ClassDef) and item.name == "SmartCollections"
            for node in item.body
            if isinstance(node, ast.FunctionDef) and node.name == "_resolve_media_ref"
        )

        @dataclass(frozen=True)
        class MediaRef:
            media_type: Optional[str] = None
            tmdb_id: Optional[int] = None
            douban_id: Optional[str] = None
            title: Optional[str] = None
            year: Optional[int] = None
            poster_url: Optional[str] = None
            aliases: tuple = ()

        class FakeMediaChain:
            def get_tmdbinfo_by_doubanid(self, **_kwargs):
                return None

        class FakeResolver:
            def resolve_tmdb_by_title(self, media_ref):
                return MediaRef(
                    media_type="movie",
                    tmdb_id=513692,
                    douban_id=media_ref.douban_id,
                    title="怒火·重案",
                    year=2021,
                    aliases=media_ref.aliases,
                )

        class FakeLogger:
            def info(self, *_args, **_kwargs):
                pass

            def warning(self, *_args, **_kwargs):
                pass

        namespace = {
            "Dict": Dict,
            "Optional": Optional,
            "MediaRef": MediaRef,
            "MediaChain": FakeMediaChain,
            "MediaType": types.SimpleNamespace(MOVIE="movie", TV="tv"),
            "SourceResolver": types.SimpleNamespace(),
            "time": types.SimpleNamespace(monotonic=lambda: 100.0, time=lambda: 1000.0),
            "logger": FakeLogger(),
        }
        exec(
            "class Subject:\n"
            + "\n".join(
                f"    {line}" for line in ast.unparse(method).splitlines()
            ),
            namespace,
        )
        subject = namespace["Subject"]()
        subject._douban_chain_cooldown_until = 0
        subject._DOUBAN_FAILURE_CACHE_TTL = 6 * 3600
        cache = {}
        result = subject._resolve_media_ref(
            MediaRef(
                douban_id="30174085",
                title="怒火·重案 怒火",
                year=2021,
            ),
            cache,
            FakeResolver(),
        )
        self.assertEqual(result.tmdb_id, 513692)
        self.assertEqual(cache["30174085"]["type"], "movie")
        self.assertEqual(subject._douban_chain_cooldown_until, 160.0)

        class FailingResolver:
            calls = 0

            def resolve_tmdb_by_title(self, _media_ref):
                type(self).calls += 1
                return None

        failed_cache = {}
        missing = MediaRef(douban_id="999", title="无法识别条目", year=2024)
        self.assertIsNone(
            subject._resolve_media_ref(missing, failed_cache, FailingResolver())
        )
        self.assertTrue(failed_cache["999"]["failed"])
        self.assertIsNone(
            subject._resolve_media_ref(missing, failed_cache, FailingResolver())
        )
        self.assertEqual(FailingResolver.calls, 1)
        failed_cache["999"]["failed_at"] = -100000
        self.assertIsNone(
            subject._resolve_media_ref(missing, failed_cache, FailingResolver())
        )
        self.assertEqual(FailingResolver.calls, 2)

    def test_large_douban_batch_uses_parallel_title_resolution(self):
        source = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        method = next(
            node
            for item in tree.body
            if isinstance(item, ast.ClassDef) and item.name == "SmartCollections"
            for node in item.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_resolve_large_douban_batch"
        )
        namespace = {
            "Any": Any,
            "Dict": Dict,
            "List": list,
            "Optional": Optional,
            "Tuple": tuple,
            "Callable": Callable,
            "MediaRef": sources.MediaRef,
            "SourceResolver": object,
            "ThreadPoolExecutor": ThreadPoolExecutor,
            "as_completed": as_completed,
        }
        exec(
            "class Subject:\n"
            + "\n".join(
                f"    {line}" for line in ast.unparse(method).splitlines()
            ),
            namespace,
        )
        subject = namespace["Subject"]()
        calls = []
        subject._find_title_match = lambda *_args: None

        def resolve(item, _cache, _resolver, skip_douban_chain=False):
            calls.append(skip_douban_chain)
            return sources.MediaRef(
                media_type="movie",
                tmdb_id=int(item.douban_id),
                douban_id=item.douban_id,
                title=item.title,
            )

        subject._resolve_media_ref = resolve
        items = [
            sources.MediaRef(douban_id=str(index), title=f"电影 {index}")
            for index in range(1, 101)
        ]
        result = subject._resolve_large_douban_batch(
            items, {}, {}, object()
        )
        self.assertEqual(len(result), 100)
        self.assertTrue(all(calls))

    def test_douban_parser_retains_preview_metadata(self):
        page = """
        <div id="1" class="doulist-item">
          <div class="post"><img src="https://img.example/poster.jpg"></div>
          <div class="title"><a href="https://movie.douban.com/subject/1292052/">肖申克的救赎 The Shawshank Redemption</a></div>
          <div>年份: 1994</div>
        </div><div class="paginator"></div>
        """
        items = sources.SourceResolver._parse_douban_page(page)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].douban_id, "1292052")
        self.assertEqual(items[0].title, "肖申克的救赎")
        self.assertIsNone(items[0].media_type)
        self.assertIn("The Shawshank Redemption", items[0].aliases)
        self.assertEqual(items[0].year, 1994)
        self.assertEqual(items[0].poster_url, "https://img.example/poster.jpg")
        tv_items = sources.SourceResolver._parse_douban_page(page, media_type="tv")
        self.assertEqual(tv_items[0].media_type, "tv")

    def test_mixed_douban_titles_match_existing_emby_aliases(self):
        source = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        method = next(
            node
            for item in tree.body
            if isinstance(item, ast.ClassDef) and item.name == "SmartCollections"
            for node in item.body
            if isinstance(node, ast.FunctionDef) and node.name == "_find_title_match"
        )
        namespace = {
            "MediaRef": sources.MediaRef,
            "Any": Any,
            "Dict": Dict,
            "List": list,
            "Tuple": tuple,
            "Optional": Optional,
            "SourceResolver": sources.SourceResolver,
            "EmbyCollectionClient": emby.EmbyCollectionClient,
        }
        exec(
            "class Subject:\n"
            + "\n".join(
                f"    {line}" for line in ast.unparse(method).splitlines()
            ),
            namespace,
        )
        title_index = {
            ("怒火重案", 2021): [
                {"id": "m1", "media_type": "movie", "tmdb_id": 513692}
            ],
            ("lacasadepapel", 2017): [
                {"id": "s1", "media_type": "tv", "tmdb_id": 71446}
            ],
            ("寄生兽灰色部队", 2024): [
                {"id": "s2", "media_type": "tv", "tmdb_id": 208825}
            ],
        }
        cases = [
            sources.MediaRef(
                title="怒火·重案 怒火", year=2021
            ),
            sources.MediaRef(
                title="纸钞屋 第四季",
                year=2020,
                aliases=("La casa de papel Season 4", "La casa de papel"),
            ),
            sources.MediaRef(
                title="寄生兽：灰色部队",
                year=2024,
                aliases=("기생수: 더 그레이",),
            ),
        ]
        matches = [
            namespace["Subject"]._find_title_match(item, title_index)
            for item in cases
        ]
        self.assertEqual([item["id"] for item in matches], ["m1", "s1", "s2"])

    def test_tmdb_title_fallback_recognizes_tv_season(self):
        class SearchRequestUtils:
            def __init__(self, *args, **kwargs):
                pass

            def get_res(self, _url, params=None):
                if "La casa de papel" not in str((params or {}).get("query")):
                    return FakeResponse({"results": []})
                return FakeResponse(
                    {
                        "results": [
                            {
                                "id": 71446,
                                "media_type": "tv",
                                "name": "纸房子",
                                "original_name": "La casa de papel",
                                "first_air_date": "2017-05-02",
                                "poster_path": "/paper.jpg",
                                "popularity": 150,
                            }
                        ]
                    }
                )

        resolver = sources.SourceResolver(tmdb_token="test-token")
        with patch.object(sources, "RequestUtils", SearchRequestUtils):
            result = resolver.resolve_tmdb_by_title(
                sources.MediaRef(
                    douban_id="34911053",
                    title="纸钞屋 第四季",
                    year=2020,
                    aliases=("La casa de papel Season 4", "La casa de papel"),
                )
            )
        self.assertEqual((result.media_type, result.tmdb_id), ("tv", 71446))

    def test_douban_reported_total_keeps_public_gap_visible(self):
        page = """
        <h1><span>测试豆列</span></h1>
        <div class="doulist-filter"><a>全部<span>(2)</span></a></div>
        <div id="1" class="doulist-item">
          <div class="title"><a href="https://movie.douban.com/subject/1/">测试电影</a></div>
          <div>年份: 2024</div>
        </div><div class="paginator"></div>
        """

        class PageRequestUtils:
            def __init__(self, *args, **kwargs):
                pass

            def get_res(self, _url, params=None):
                return FakeResponse({}, text=page if (params or {}).get("start") == 0 else "")

        with patch.object(sources, "RequestUtils", PageRequestUtils):
            result = sources.SourceResolver()._fetch_douban_list("123")
        self.assertEqual(result.reported_total, 2)
        self.assertEqual(len(result.items), 1)

    def test_tmdb_and_template_items_keep_type_year_and_poster(self):
        items = sources.SourceResolver._tmdb_items(
            [{"id": 101, "title": "测试电影", "release_date": "2024-01-02", "poster_path": "/a.jpg"}],
            default_media_type="movie",
        )
        self.assertEqual((items[0].media_type, items[0].year), ("movie", 2024))
        self.assertTrue(items[0].poster_url.endswith("/a.jpg"))

        parsed = sources.SourceResolver._parse_template(
            sources.CollectionSpec(
                source_type="template",
                name="模板",
                items=[{"media_type": "tv", "tmdb_id": 202, "title": "测试剧集", "year": 2023}],
            )
        )
        self.assertEqual((parsed.items[0].media_type, parsed.items[0].tmdb_id), ("tv", 202))

    def test_catalog_sources_have_canonical_urls_and_correct_oscar_title(self):
        oscar = next(
            item
            for item in sources.POPULAR_TMDB_LISTS
            if item.get("list_id") == "8648843"
        )
        self.assertEqual(oscar["title"], "奥斯卡历届最佳影片")
        self.assertEqual(oscar["url"], "https://www.themoviedb.org/list/8648843")
        self.assertEqual(
            sources.SourceResolver.source_url(
                sources.CollectionSpec(
                    source_type="tmdb_builtin", list_id=oscar["value"]
                )
            ),
            oscar["url"],
        )
        tmdb_expected = {
            "8648843": "奥斯卡历届最佳影片",
            "8648849": "金球奖最佳剧情片",
            "8648848": "英国电影学院奖最佳影片",
            "8648844": "戛纳电影节金棕榈奖",
            "8648854": "威尼斯电影节金狮奖",
            "8647021": "IMDb Top 250 Movies",
            "8647022": "IMDb Top 250 TV Shows",
            "8647023": "豆瓣电影 Top 250",
            "8648802": "Letterboxd's Top 500 Films",
            "8649225": "Letterboxd's Top 250 Animated Films",
            "8649108": "Criterion Collection",
        }
        for list_id, title in tmdb_expected.items():
            definition = next(
                item
                for item in sources.POPULAR_TMDB_LISTS
                if item.get("list_id") == list_id
            )
            self.assertEqual(definition["title"], title)
            self.assertEqual(
                definition["url"], f"https://www.themoviedb.org/list/{list_id}"
            )
        requested_ids = {
            "8648821", "8649224", "8649231", "8649058", "8649050", "8648851",
            "8648850", "8649219", "8649220", "8649218", "8649217", "8649041",
        }
        self.assertTrue(
            requested_ids.issubset(
                {str(item.get("list_id")) for item in sources.POPULAR_TMDB_LISTS}
            )
        )
        douban_expected = {
            "240962": "★豆瓣高分电影榜★ （上）9.7-8.6分",
            "243559": "★豆瓣高分电影榜★ （中）8.5-8.3分",
            "248893": "★豆瓣高分电影榜★ （下）8.2-8.0分",
            "13922": "【豆瓣冷门佳片】10-8.5分｜评分人数<5000",
            "249029": "【豆瓣冷门佳片】8.4-8分｜评分人数<5000",
            "223781": "【豆瓣高分动画长片】",
            "30299": "豆瓣电影【口碑榜】2023-09-11 更新",
            "515203": "历届奥斯卡最佳动画长片及提名",
            "40435": "值得一看的电影和美剧",
            "110522": "有生之年一定要看的1001部电影",
            "213727": "IMDb TV Shows Top 250",
            "172901": "【豆瓣五星电视剧】(1/2)",
        }
        for list_id, title in douban_expected.items():
            definition = next(
                item
                for item in sources.POPULAR_DOUBAN_LISTS
                if item.get("value") == list_id
            )
            self.assertEqual(definition["title"], title)
        self.assertEqual(
            next(
                item
                for item in sources.POPULAR_DOUBAN_LISTS
                if item["value"] == "213727"
            )["media_type"],
            "tv",
        )
        resolver = sources.SourceResolver(tmdb_token="test")
        with patch.object(
            resolver,
            "_fetch_tmdb_list",
            return_value=sources.ResolvedSource(title="来源实时标题", items=[]),
        ):
            resolved = resolver._fetch_tmdb_builtin("finly_golden_globes")
        self.assertEqual(resolved.title, "来源实时标题")

    def test_tmdb_list_metadata_and_id_lookup_keep_description_count_and_poster(self):
        class MetadataRequestUtils:
            def __init__(self, *args, **kwargs):
                pass

            def get_res(self, url, params=None):
                if "/4/list/" in url:
                    return FakeResponse(
                        {
                            "name": "实时片单标题",
                            "description": "实时片单简介",
                            "total_results": 321,
                            "total_pages": 1,
                            "results": [
                                {
                                    "id": 101,
                                    "media_type": "movie",
                                    "title": "测试电影",
                                    "release_date": "2024-01-01",
                                    "poster_path": "/list.jpg",
                                }
                            ],
                        }
                    )
                return FakeResponse(
                    {
                        "id": 101,
                        "title": "测试电影",
                        "release_date": "2024-01-01",
                        "poster_path": "/detail.jpg",
                    }
                )

        resolver = sources.SourceResolver(tmdb_token="token", max_items=2000)
        with patch.object(sources, "RequestUtils", MetadataRequestUtils):
            resolved = resolver._fetch_tmdb_v4("8648821")
            detail = resolver.resolve_tmdb_by_id(
                sources.MediaRef(douban_id="1", title="测试电影"),
                "movie",
                101,
            )
        self.assertEqual(resolved.title, "实时片单标题")
        self.assertEqual(resolved.description, "实时片单简介")
        self.assertEqual(resolved.reported_total, 321)
        self.assertTrue(resolved.items[0].poster_url.endswith("/list.jpg"))
        self.assertTrue(detail.poster_url.endswith("/detail.jpg"))

    def test_tmdb_v3_list_reads_every_page_up_to_configured_limit(self):
        class PagedRequestUtils:
            pages = []

            def __init__(self, *args, **kwargs):
                pass

            def get_res(self, _url, params=None):
                page = int((params or {}).get("page") or 1)
                type(self).pages.append(page)
                start = 1 if page == 1 else 21
                count = 20 if page == 1 else 5
                return FakeResponse(
                    {
                        "name": "分页片单",
                        "description": "完整简介",
                        "item_count": 25,
                        "total_pages": 2,
                        "items": [
                            {
                                "id": index,
                                "media_type": "movie",
                                "title": f"电影 {index}",
                                "release_date": "2024-01-01",
                            }
                            for index in range(start, start + count)
                        ],
                    }
                )

        PagedRequestUtils.pages = []
        resolver = sources.SourceResolver(max_items=2000)
        with patch.object(sources, "RequestUtils", PagedRequestUtils):
            resolved = resolver._fetch_tmdb_v3("8648821")
        self.assertEqual(PagedRequestUtils.pages, [1, 2])
        self.assertEqual(len(resolved.items), 25)
        self.assertEqual(resolved.reported_total, 25)
        self.assertEqual(resolved.description, "完整简介")

    def test_subscribe_missing_filters_preview_and_reports_progress(self):
        source = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        methods = {
            node.name: node
            for item in tree.body
            if isinstance(item, ast.ClassDef) and item.name == "SmartCollections"
            for node in item.body
            if isinstance(node, ast.FunctionDef)
            and node.name
            in {
                "api_subscribe_missing",
                "api_subscribe_missing_status",
                "_run_subscribe_missing",
            }
        }

        class FakeThread:
            def __init__(self, target, args=(), **_options):
                self.target = target
                self.args = args

            def start(self):
                self.target(*self.args)

        class FakeLogger:
            def exception(self, *_args, **_kwargs):
                pass

        namespace = {
            "Any": Any,
            "Dict": Dict,
            "List": list,
            "Body": lambda *args, **kwargs: None,
            "logger": FakeLogger(),
            "threading": types.SimpleNamespace(Thread=FakeThread),
        }
        method_source = "\n".join(
            ast.unparse(methods[name])
            for name in (
                "api_subscribe_missing_status",
                "api_subscribe_missing",
                "_run_subscribe_missing",
            )
        )
        exec(
            "class Subject:\n"
            + "\n".join(f"    {line}" for line in method_source.splitlines()),
            namespace,
        )
        subject = namespace["Subject"]()
        subject._subscription_batch_lock = threading.Lock()
        subject._subscription_batch_status_lock = threading.RLock()
        subject._subscription_batch_status = {}
        subject._get_preview = lambda _preview_id: {
            "items": [
                {"key": "movie:1", "matched": True, "tmdb_id": 1, "media_type": "movie", "title": "已有"},
                {"key": "movie:2", "matched": False, "tmdb_id": 2, "media_type": "movie", "title": "缺失"},
                {"key": "unknown:3", "matched": False, "tmdb_id": None, "media_type": None, "title": "不可订阅"},
            ]
        }
        subject._subscribe_item = lambda item, background_search: {
            "success": item.get("tmdb_id") == 2 and background_search is False
        }
        response = subject.api_subscribe_missing({"preview_id": "preview1"})
        self.assertTrue(response["success"])
        status = subject.api_subscribe_missing_status()["data"]
        self.assertFalse(status["running"])
        self.assertEqual(status["total"], 1)
        self.assertEqual(status["subscribed"], 1)
        self.assertEqual(status["result"]["subscribed_keys"], ["movie:2"])

    def test_emby_catalog_supports_exact_and_title_indexes(self):
        fake = FakeEmby()
        client = emby.EmbyCollectionClient(types.SimpleNamespace(instance=fake))
        catalog, title_index, duplicates = client.build_library_catalog()
        self.assertEqual(duplicates, 0)
        self.assertEqual(catalog[("movie", 101)]["name"], "测试电影")
        self.assertEqual(title_index[("testmovie", 2024)][0]["id"], "m1")
        self.assertEqual(client.normalize_title("기생수: 더 그레이"), "기생수더그레이")
        client.delete_collection("box1")
        self.assertIn("Items/box1", FakeRequestUtils.deleted_urls[-1])
        self.assertIn("item?id=m1", client.get_item_url("m1"))
        client.set_collection_poster("box1", b"jpeg-bytes")
        self.assertIn("Images/Primary", fake.uploaded[-1][0])

        collections = client.list_collections()
        self.assertEqual([item["id"] for item in collections], ["box1", "box2"])
        self.assertEqual(client.get_collection_item_ids("box1"), {"m1"})
        self.assertEqual(client.get_collection_poster("box1"), b"poster-bytes")
        restored = client.restore_collection(
            record={
                "name": "测试合集",
                "sort_name": "CSHJ",
                "overview": "恢复简介",
                "provider_ids": {"Tmdb": "10"},
                "tags": ["恢复"],
                "item_ids": ["m1", "m2"],
            },
            poster=b"restored-poster",
            existing_id="box1",
        )
        self.assertFalse(restored.created)
        self.assertEqual(restored.added, 1)
        self.assertTrue(any("Collections/box1/Items" in item[0] for item in fake.uploaded))
        self.assertTrue(any("Items/box1?" in item[0] for item in fake.uploaded))
        fake.uploaded.clear()
        synced = client.sync_collection(
            "测试合集", ["m1"], mode="sync", overview="来自片单的简介"
        )
        self.assertFalse(synced.created)
        metadata_payloads = [
            json.loads(data)
            for url, data, _headers in fake.uploaded
            if "Items/box1?" in url and data
        ]
        self.assertEqual(metadata_payloads[-1]["Overview"], "来自片单的简介")

    def test_other_collection_backup_cleanup_and_restore(self):
        class FakeBackupClient:
            def __init__(self):
                self.collections = [
                    {"id": "legacy1", "name": "旧合集", "image_tag": "cover"},
                    {"id": "smart1", "name": "智能合集", "image_tag": None},
                ]
                self.deleted = []
                self.restored = []

            def list_collections(self):
                return list(self.collections)

            def get_collection_item_ids(self, collection_id):
                return {"m1", "m2"} if collection_id == "legacy1" else {"m3"}

            def get_collection_poster(self, collection_id):
                return b"poster" if collection_id == "legacy1" else None

            def delete_collection(self, collection_id):
                self.deleted.append(collection_id)
                self.collections = [
                    item for item in self.collections if item["id"] != collection_id
                ]

            def restore_collection(self, record, poster=None, existing_id=None):
                self.restored.append((record, poster, existing_id))
                return types.SimpleNamespace(
                    collection_id=existing_id or "restored1",
                    created=not bool(existing_id),
                    added=len(record.get("item_ids") or []),
                )

        fake = FakeBackupClient()
        with tempfile.TemporaryDirectory() as directory:
            manager = collection_backup.EmbyCollectionBackupManager(Path(directory), fake)
            backup = manager.create_backup({"smart1"}, "测试 Emby")
            self.assertEqual(backup["collection_count"], 1)
            with zipfile.ZipFile(Path(directory) / backup["backup_id"], "r") as archive:
                self.assertIn("manifest.json", archive.namelist())
                self.assertIn("posters/legacy1.jpg", archive.namelist())

            cleanup = manager.backup_and_cleanup({"smart1"}, "测试 Emby")
            self.assertEqual(cleanup["deleted"], 1)
            self.assertEqual(fake.deleted, ["legacy1"])
            self.assertEqual(fake.collections[0]["id"], "smart1")

            restored = manager.restore_backup(backup["backup_id"], {"smart1"})
            self.assertEqual(restored["created"], 1)
            self.assertEqual(restored["failed"], 0)
            self.assertEqual(fake.restored[-1][1], b"poster")
            deleted = manager.delete_backup(backup["backup_id"])
            self.assertTrue(deleted["deleted"])
            self.assertFalse((Path(directory) / backup["backup_id"]).exists())
            with self.assertRaises(ValueError):
                manager.restore_backup("../outside.zip", {"smart1"})

        class FailingBackupClient(FakeBackupClient):
            def get_collection_item_ids(self, collection_id):
                raise RuntimeError("模拟备份失败")

        failing = FailingBackupClient()
        with tempfile.TemporaryDirectory() as directory:
            manager = collection_backup.EmbyCollectionBackupManager(
                Path(directory), failing
            )
            with self.assertRaises(RuntimeError):
                manager.backup_and_cleanup({"smart1"}, "测试 Emby")
            self.assertEqual(failing.deleted, [])

    def test_background_preview_reports_progress_result_and_notification(self):
        source = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        method_names = {
            "_run_preview_task",
            "_preview_task_snapshot",
            "_set_preview_task_status",
        }
        methods = [
            node
            for item in tree.body
            if isinstance(item, ast.ClassDef) and item.name == "SmartCollections"
            for node in item.body
            if isinstance(node, ast.FunctionDef) and node.name in method_names
        ]

        class FakeLogger:
            def exception(self, *_args, **_kwargs):
                pass

        namespace = {
            "Any": Any,
            "Dict": Dict,
            "CollectionSpec": object,
            "NotificationType": types.SimpleNamespace(Plugin="plugin"),
            "logger": FakeLogger(),
        }
        exec(
            "class Subject:\n"
            + "\n".join(
                f"    {line}"
                for method in methods
                for line in ast.unparse(method).splitlines()
            ),
            namespace,
        )
        subject = namespace["Subject"]()
        subject._preview_task_lock = threading.Lock()
        subject._preview_task_lock.acquire()
        subject._preview_task_status_lock = threading.RLock()
        subject._preview_task_status = {
            "task_id": "task1",
            "running": True,
            "progress": 1,
            "message": "准备中",
            "result": None,
            "error": None,
        }
        notifications = []
        subject.post_message = lambda **kwargs: notifications.append(kwargs)

        def build_preview(_spec, progress=None):
            progress(55, "正在匹配")
            return {
                "title": "测试片单",
                "total_count": 10,
                "matched_count": 8,
                "missing_count": 2,
            }

        subject._build_preview = build_preview
        subject._run_preview_task("task1", object())
        snapshot = subject._preview_task_snapshot()
        self.assertFalse(snapshot["running"])
        self.assertEqual(snapshot["progress"], 100)
        self.assertEqual(snapshot["result"]["matched_count"], 8)
        self.assertIn("预览匹配完成", notifications[-1]["title"])
        self.assertFalse(subject._preview_task_lock.locked())

    def test_frontend_keeps_tmdb_and_emby_links_separate_and_shows_async_metadata(self):
        frontend = (PLUGIN / "src" / "components" / "SmartCollectionsApp.vue").read_text(
            encoding="utf-8"
        )
        self.assertIn('v-if="tmdbLink(item)"', frontend)
        self.assertNotIn('v-if="item.matched && item.emby_url"', frontend)
        self.assertIn('referrerpolicy="no-referrer"', frontend)
        self.assertIn("slice(0, 2000)", frontend)
        self.assertIn("/preview/status", frontend)
        self.assertIn("preview.description", frontend)
        self.assertIn("source.item_count", frontend)
        self.assertIn("/collections/resync/all", frontend)
        self.assertIn("/collections/schedule", frontend)
        self.assertIn("/cache/export", frontend)
        self.assertIn("/settings", frontend)
        self.assertIn("/collections/tools/backup/delete", frontend)
        self.assertIn("/batch/sync/status", frontend)
        self.assertIn("关闭页面不会中断任务", frontend)
        self.assertIn("导出映射缓存", frontend)
        self.assertIn("解析上限", frontend)
        self.assertNotIn('managed-info flex-grow-1', frontend)
        self.assertIn('max-width="760"', frontend)

        seed = json.loads(
            (PLUGIN / "assets" / "douban_tmdb_seed.json").read_text(encoding="utf-8")
        )
        self.assertEqual(seed["version"], 1)
        self.assertIsInstance(seed["mappings"], dict)
        backend = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("_load_douban_cache", backend)
        self.assertIn("github_seed", backend)

    def test_partial_source_results_never_remove_existing_collection_members(self):
        source = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        method = next(
            node
            for item in tree.body
            if isinstance(item, ast.ClassDef) and item.name == "SmartCollections"
            for node in item.body
            if isinstance(node, ast.FunctionDef) and node.name == "_safe_sync_mode"
        )
        namespace = {
            "Any": Any,
            "Dict": Dict,
            "List": list,
            "Optional": Optional,
            "Tuple": tuple,
        }
        exec(
            "class Subject:\n"
            + "\n".join(f"    {line}" for line in ast.unparse(method).splitlines()),
            namespace,
        )
        guard = namespace["Subject"]._safe_sync_mode
        mode, reason = guard(
            "sync",
            source_count=20,
            reported_total=250,
            matched_count=20,
            previous={"total_count": 250, "matched_count": 242},
        )
        self.assertEqual(mode, "append")
        self.assertIn("20/250", reason)
        healthy_mode, healthy_reason = guard(
            "sync",
            source_count=250,
            reported_total=250,
            matched_count=242,
            previous={"total_count": 250, "matched_count": 242},
        )
        self.assertEqual(healthy_mode, "sync")
        self.assertIsNone(healthy_reason)

    def test_mapping_export_contains_only_local_successful_results(self):
        source = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        method = next(
            node
            for item in tree.body
            if isinstance(item, ast.ClassDef) and item.name == "SmartCollections"
            for node in item.body
            if isinstance(node, ast.FunctionDef) and node.name == "api_cache_export"
        )
        namespace = {"Any": Any, "Dict": Dict}
        exec(
            "class Subject:\n"
            + "\n".join(f"    {line}" for line in ast.unparse(method).splitlines()),
            namespace,
        )
        subject = namespace["Subject"]()
        subject.get_data = lambda _key: {
            "100": {"type": "movie", "tmdb_id": 10, "title": "有效映射", "year": 2024},
            "101": {"type": "movie", "tmdb_id": 11, "failed": True},
            "102": {"type": "tv", "tmdb_id": 12, "source": "github_seed"},
        }
        subject._now = lambda: "2026-07-03T12:00:00+08:00"
        exported = subject.api_cache_export()["data"]
        self.assertEqual(exported["mapping_count"], 1)
        self.assertEqual(set(exported["mappings"]), {"100"})

    def test_batch_sync_returns_immediately_and_reports_background_progress(self):
        source = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        wanted = {"api_batch_sync", "api_batch_sync_status", "_run_batch_sync"}
        methods = [
            node
            for item in tree.body
            if isinstance(item, ast.ClassDef) and item.name == "SmartCollections"
            for node in item.body
            if isinstance(node, ast.FunctionDef) and node.name in wanted
        ]

        class DeferredThread:
            latest = None

            def __init__(self, target, args=(), **_kwargs):
                self.target = target
                self.args = args
                type(self).latest = self

            def start(self):
                pass

        class FakeLogger:
            def exception(self, *_args, **_kwargs):
                pass

            def debug(self, *_args, **_kwargs):
                pass

        namespace = {
            "Any": Any,
            "Body": lambda *_args, **_kwargs: None,
            "Dict": Dict,
            "List": list,
            "NotificationType": types.SimpleNamespace(Plugin="plugin"),
            "logger": FakeLogger(),
            "threading": types.SimpleNamespace(Thread=DeferredThread),
            "uuid": types.SimpleNamespace(
                uuid4=lambda: types.SimpleNamespace(hex="batch-task")
            ),
        }
        exec(
            "class Subject:\n"
            + "\n".join(
                f"    {line}"
                for method in methods
                for line in ast.unparse(method).splitlines()
            ),
            namespace,
        )
        subject = namespace["Subject"]()
        subject._run_lock = threading.Lock()
        subject._batch_sync_status_lock = threading.RLock()
        subject._batch_sync_status = {}
        subject._sync_mode = "sync"
        subject._preview_context = lambda: object()
        subject._spec_from_payload = lambda value: types.SimpleNamespace(
            name=value.get("name"), mode=None
        )
        subject._build_preview = lambda spec, context=None, progress=None: (
            progress(50, "匹配中") or {"title": spec.name}
        )
        subject._sync_preview_data = lambda preview, name, mode: {
            "success": True,
            "name": name,
        }
        notifications = []
        subject.post_message = lambda **kwargs: notifications.append(kwargs)

        started = subject.api_batch_sync({"sources": [{"name": "测试片单"}]})
        self.assertTrue(started["success"])
        self.assertEqual(started["data"]["task_id"], "batch-task")
        self.assertTrue(subject.api_batch_sync_status()["data"]["running"])
        self.assertTrue(subject._run_lock.locked())

        DeferredThread.latest.target(*DeferredThread.latest.args)
        status = subject.api_batch_sync_status()["data"]
        self.assertFalse(status["running"])
        self.assertEqual(status["progress"], 100)
        self.assertEqual(status["succeeded"], 1)
        self.assertFalse(subject._run_lock.locked())
        self.assertIn("批量同步完成", notifications[-1]["title"])

    def test_collection_poster_generate_and_normalize(self):
        source_images = [
            Image.new("RGB", (400, 600), (30 + index * 20, 80, 150))
            for index in range(3)
        ]
        with patch.object(
            poster.CollectionPosterBuilder,
            "_download_images",
            return_value=source_images,
        ):
            content = poster.CollectionPosterBuilder.generate("测试智能合集", ["a", "b"])
        with Image.open(io.BytesIO(content)) as image:
            self.assertEqual(image.size, (1000, 1500))
            self.assertLess(
                sum(image.getpixel((500, 1450))),
                sum(image.getpixel((500, 500))),
            )
            gold_pixels = sum(
                1
                for red, green, blue in image.crop(
                    (0, 1050, 1000, 1500)
                ).get_flattened_data()
                if red > 200 and green > 130 and blue < 150
            )
            self.assertGreater(gold_pixels, 1000)
        normalized = poster.CollectionPosterBuilder.normalize_upload(content)
        self.assertTrue(normalized.startswith(b"\xff\xd8"))
        contained = poster.CollectionPosterBuilder._contain(source_images[0], 407, 439)
        self.assertEqual(contained.size, (293, 439))
        self.assertTrue(
            (PLUGIN / "assets" / "fonts" / "NotoSansCJKsc-Medium.otf").exists()
        )
        self.assertTrue(
            (PLUGIN / "assets" / "fonts" / "NotoSansCJK-LICENSE.txt").exists()
        )
        chinese_font = poster.CollectionPosterBuilder._font(72)
        self.assertNotEqual(
            bytes(chinese_font.getmask("电")), bytes(chinese_font.getmask("\uffff"))
        )
        self.assertNotIn(
            "SMART COLLECTION",
            (PLUGIN / "poster.py").read_text(encoding="utf-8"),
        )
        draw = ImageDraw.Draw(Image.new("RGB", (1000, 1500), "black"))
        for title in ("IMDb Top 250 TV Shows", "Letterboxd's Top 500 Films"):
            _font, lines, _line_height = poster.CollectionPosterBuilder._fit_title(
                draw, title
            )
            self.assertLessEqual(len(lines), 2)
            self.assertEqual(" ".join(lines).split(), title.split())


if __name__ == "__main__":
    unittest.main()
