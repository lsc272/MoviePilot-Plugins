import ast
import importlib.util
import io
import sys
import tempfile
import threading
import types
import unittest
import zipfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import patch

from PIL import Image


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
class FakeRequestUtils:
    deleted_urls = []

    def __init__(self, *args, **kwargs):
        pass

    def delete_res(self, url):
        self.deleted_urls.append(url)
        return FakeResponse({}, 204)


http.RequestUtils = FakeRequestUtils
sys.modules.update(
    {
        "app": app,
        "app.core": core,
        "app.core.config": config,
        "app.utils": utils,
        "app.utils.http": http,
    }
)

sources = load_module("smartcollections_sources_test", PLUGIN / "sources.py")
emby = load_module("smartcollections_emby_test", PLUGIN / "emby.py")
poster = load_module("smartcollections_poster_test", PLUGIN / "poster.py")
collection_backup = load_module(
    "smartcollections_collection_backup_test", PLUGIN / "collection_backup.py"
)


class FakeResponse:
    def __init__(self, payload, status_code=200, content=b"{}"):
        self._payload = payload
        self.status_code = status_code
        self.content = content

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
            "logger": FakeLogger(),
        }
        method_source = ast.unparse(method)
        exec(
            "class Subject:\n"
            + "\n".join(f"    {line}" for line in method_source.splitlines()),
            namespace,
        )
        subject = namespace["Subject"]()

        FakeMediaChain.result = {
            "id": "303",
            "name": "测试剧集",
            "media_type": "tv",
            "first_air_date": "2024-01-01",
            "poster_path": "/poster.jpg",
        }
        cache = {}
        result = subject._resolve_media_ref(MediaRef(douban_id="1001"), cache)
        self.assertEqual((result.media_type, result.tmdb_id, result.year), ("tv", 303, 2024))
        self.assertEqual(cache["1001"]["title"], "测试剧集")

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
        self.assertEqual(items[0].year, 1994)
        self.assertEqual(items[0].poster_url, "https://img.example/poster.jpg")
        tv_items = sources.SourceResolver._parse_douban_page(page, media_type="tv")
        self.assertEqual(tv_items[0].media_type, "tv")

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
            self.assertGreater(
                sum(image.getpixel((500, 1450))),
                sum(image.getpixel((500, 500))),
            )
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


if __name__ == "__main__":
    unittest.main()
