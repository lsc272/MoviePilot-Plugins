import ast
import importlib.util
import sys
import types
import unittest
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Optional


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
http.RequestUtils = object
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

    def delete_data(self, url):
        self.deleted.append(url)
        return FakeResponse({}, 204)


class SmartCollectionsTests(unittest.TestCase):
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
        self.assertIn("Items/box1", fake.deleted[0])


if __name__ == "__main__":
    unittest.main()
