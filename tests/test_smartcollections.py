import ast
import importlib.util
import io
import sys
import types
import unittest
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


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.content = b"{}"

    def json(self):
        return self._payload


class FakeEmby:
    def __init__(self):
        self.deleted = []
        self.uploaded = []
        self._host = "http://emby/"
        self._apikey = "test-key"

    def get_data(self, url):
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
        method = next(
            node
            for item in tree.body
            if isinstance(item, ast.ClassDef) and item.name == "SmartCollections"
            for node in item.body
            if isinstance(node, ast.FunctionDef) and node.name == "api_subscribe"
        )

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

        namespace = {
            "Any": Any,
            "Dict": Dict,
            "MediaType": MediaType,
            "SubscribeChain": FakeSubscribeChain,
            "logger": FakeLogger(),
            "Body": lambda *args, **kwargs: None,
        }
        method_source = ast.unparse(method)
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
        normalized = poster.CollectionPosterBuilder.normalize_upload(content)
        self.assertTrue(normalized.startswith(b"\xff\xd8"))


if __name__ == "__main__":
    unittest.main()
