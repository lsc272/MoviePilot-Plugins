import datetime
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.event import Event, eventmanager
from app.helper.mediaserver import MediaServerHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, MediaType, NotificationType

from .emby import EmbyCollectionClient
from .sources import (
    POPULAR_DOUBAN_LISTS,
    POPULAR_TMDB_LISTS,
    CollectionSpec,
    MediaRef,
    SourceResolver,
)


class SmartCollections(_PluginBase):
    plugin_name = "智能合集"
    plugin_desc = "从热门 TMDB 片单、热门豆列或手动链接同步 Emby 合集。"
    plugin_icon = "smartcollections.svg"
    plugin_version = "0.2.0"
    plugin_author = "lsc272"
    author_url = "https://github.com/lsc272"
    plugin_config_prefix = "smartcollections_"
    plugin_order = 25
    auth_level = 1

    _enabled = False
    _onlyonce = False
    _notify = False
    _cron = "0 4 * * *"
    _emby_server = ""
    _sync_mode = "sync"
    _tmdb_token = ""
    _language = "zh-CN"
    _max_items = 500
    _use_proxy = False
    _popular_tmdb: List[str] = []
    _popular_douban: List[str] = []
    _manual_urls = ""
    _sources = "[]"
    _scheduler: Optional[BackgroundScheduler] = None
    _run_lock = threading.Lock()

    def __init__(self):
        super().__init__()
        self._scheduler = None
        self._run_lock = threading.Lock()

    def init_plugin(self, config: dict = None):
        self.stop_service()
        config = config or {}
        self._enabled = bool(config.get("enabled"))
        self._onlyonce = bool(config.get("onlyonce"))
        self._notify = bool(config.get("notify"))
        self._cron = str(config.get("cron") or "0 4 * * *").strip()
        self._emby_server = str(config.get("emby_server") or "").strip()
        self._sync_mode = str(config.get("sync_mode") or "sync").lower()
        self._tmdb_token = str(config.get("tmdb_token") or "").strip()
        self._language = str(config.get("language") or "zh-CN").strip()
        self._max_items = self._safe_int(config.get("max_items"), 500, 1, 5000)
        self._use_proxy = bool(config.get("use_proxy"))
        self._popular_tmdb = list(config.get("popular_tmdb") or [])
        self._popular_douban = list(config.get("popular_douban") or [])
        self._manual_urls = str(config.get("manual_urls") or "").strip()
        self._sources = config.get("sources") or "[]"

        if self._onlyonce:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            self._scheduler.add_job(
                func=self.sync_all,
                trigger="date",
                run_date=datetime.datetime.now(tz=ZoneInfo(settings.TZ))
                + datetime.timedelta(seconds=3),
                name="智能合集立即同步",
            )
            self._onlyonce = False
            self._save_config()
            self._scheduler.start()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return [
            {
                "cmd": "/smartcollections_sync",
                "event": EventType.PluginAction,
                "desc": "立即同步智能合集",
                "category": "智能合集",
                "data": {"action": "smartcollections_sync"},
            }
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/sync",
                "endpoint": self.api_sync,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "立即同步智能合集",
                "description": "在后台启动一次智能合集同步。",
            },
            {
                "path": "/history",
                "endpoint": self.api_history,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "查询智能合集同步记录",
                "description": "返回最近二十次同步记录。",
            },
        ]

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled or not self._cron:
            return []
        try:
            trigger = CronTrigger.from_crontab(self._cron)
        except ValueError as exc:
            logger.error(f"智能合集 Cron 表达式无效：{exc}")
            return []
        return [
            {
                "id": f"{self.__class__.__name__}.Sync",
                "name": "智能合集定时同步",
                "trigger": trigger,
                "func": self.sync_all,
                "kwargs": {},
            }
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        emby_servers = [
            {"title": conf.name, "value": conf.name}
            for conf in MediaServerHelper().get_configs().values()
            if conf.type == "emby"
        ]
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用定时同步",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "onlyonce",
                                            "label": "立即运行一次",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "notify",
                                            "label": "发送同步通知",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "use_proxy",
                                            "label": "访问片单使用代理",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "emby_server",
                                            "label": "Emby 服务器",
                                            "items": emby_servers,
                                            "clearable": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "cron",
                                            "label": "Cron 表达式",
                                            "placeholder": "0 4 * * *",
                                            "hint": "默认每天凌晨 4 点同步",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "sync_mode",
                                            "label": "默认更新模式",
                                            "items": [
                                                {"title": "同步（增删成员）", "value": "sync"},
                                                {"title": "追加（只添加）", "value": "append"},
                                            ],
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "tmdb_token",
                                            "label": "TMDB v4 Read Access Token",
                                            "type": "password",
                                            "hint": "推荐填写；未填写时使用 MoviePilot 的 TMDB v3 API Key 回退",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 6, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "language",
                                            "label": "TMDB 语言",
                                            "placeholder": "zh-CN",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 6, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "max_items",
                                            "label": "每个片单最多读取",
                                            "type": "number",
                                            "min": 1,
                                            "max": 5000,
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "popular_tmdb",
                                            "label": "热门 TMDB 片单",
                                            "items": POPULAR_TMDB_LISTS,
                                            "multiple": True,
                                            "chips": True,
                                            "clearable": True,
                                            "hint": "可多选，自动创建同名 Emby 合集",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "popular_douban",
                                            "label": "热门豆瓣豆列",
                                            "items": POPULAR_DOUBAN_LISTS,
                                            "multiple": True,
                                            "chips": True,
                                            "clearable": True,
                                            "hint": "可多选，首次识别大型豆列会稍慢",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "manual_urls",
                                            "label": "手动添加 TMDB List 或豆瓣豆列链接",
                                            "placeholder": "https://www.themoviedb.org/list/5292-tmdb-watchlist\nhttps://www.douban.com/doulist/240962/",
                                            "rows": 5,
                                            "auto-grow": True,
                                            "hint": "每行一个公开链接，合集名称将自动读取",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "component": "VAlert",
                        "props": {
                            "type": "info",
                            "variant": "tonal",
                            "text": "插件只会把 Emby 媒体库中已存在且 TMDB ID 一致的电影或剧集加入合集。同步模式在零匹配时不会清空现有合集。",
                        },
                    },
                ],
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            "notify": False,
            "use_proxy": False,
            "cron": "0 4 * * *",
            "emby_server": emby_servers[0]["value"] if len(emby_servers) == 1 else "",
            "sync_mode": "sync",
            "tmdb_token": "",
            "language": "zh-CN",
            "max_items": 500,
            "popular_tmdb": [],
            "popular_douban": [],
            "manual_urls": "",
            "sources": "[]",
        }

    def get_page(self) -> List[dict]:
        history = self.get_data("history") or []
        if not history:
            return [
                {
                    "component": "VAlert",
                    "props": {
                        "type": "info",
                        "variant": "tonal",
                        "text": "暂无同步记录。保存配置并勾选“立即运行一次”即可开始。",
                    },
                }
            ]

        cards: List[dict] = []
        for run in history[:10]:
            details = []
            for item in run.get("collections") or []:
                status = "成功" if item.get("success") else "失败"
                details.append(
                    f"{item.get('name') or '未命名'}：{status}，片单 {item.get('source_items', 0)}，"
                    f"匹配 {item.get('matched', 0)}，新增 {item.get('added', 0)}，"
                    f"移除 {item.get('removed', 0)}，未匹配 {item.get('missing', 0)}"
                    + (f"；{item.get('error')}" if item.get("error") else "")
                )
            cards.append(
                {
                    "component": "VCard",
                    "props": {"variant": "tonal", "class": "mb-3"},
                    "content": [
                        {
                            "component": "VCardTitle",
                            "text": f"{run.get('time')} · {'完成' if run.get('success') else '有错误'}",
                        },
                        {
                            "component": "VCardSubtitle",
                            "text": f"耗时 {run.get('duration', 0)} 秒 · Emby：{run.get('server') or '-'}",
                        },
                        {
                            "component": "VCardText",
                            "text": "\n".join(details) or run.get("error") or "无合集定义",
                        },
                    ],
                }
            )
        return cards

    def api_sync(self) -> Dict[str, Any]:
        if self._run_lock.locked():
            return {"success": False, "message": "同步任务正在运行"}
        threading.Thread(
            target=self.sync_all,
            name="SmartCollectionsSync",
            daemon=True,
        ).start()
        return {"success": True, "message": "同步任务已启动"}

    def api_history(self) -> Dict[str, Any]:
        return {"success": True, "data": self.get_data("history") or []}

    @eventmanager.register(EventType.PluginAction)
    def on_plugin_action(self, event: Event):
        data = event.event_data or {}
        if data.get("action") != "smartcollections_sync":
            return
        if self._run_lock.locked():
            self.post_message(
                mtype=NotificationType.Plugin,
                title="智能合集",
                text="同步任务正在运行，请稍后再试。",
            )
            return
        threading.Thread(
            target=self.sync_all,
            name="SmartCollectionsCommand",
            daemon=True,
        ).start()

    def _collection_specs(self) -> List[CollectionSpec]:
        """Build collection definitions from the three user-facing source inputs."""

        specs: List[CollectionSpec] = []
        tmdb_catalog = {item["value"]: item for item in POPULAR_TMDB_LISTS}
        douban_catalog = {item["value"]: item for item in POPULAR_DOUBAN_LISTS}

        for list_key in self._popular_tmdb:
            definition = tmdb_catalog.get(list_key)
            if not definition:
                raise ValueError(f"未知的热门 TMDB 片单：{list_key}")
            specs.append(
                CollectionSpec(
                    source_type="tmdb_builtin",
                    name=definition["title"],
                    list_id=list_key,
                )
            )

        for list_id in self._popular_douban:
            definition = douban_catalog.get(str(list_id))
            if not definition:
                raise ValueError(f"未知的热门豆瓣豆列：{list_id}")
            specs.append(
                CollectionSpec(
                    source_type="douban",
                    name=definition["title"],
                    list_id=str(list_id),
                )
            )

        for line in self._manual_urls.splitlines():
            url = line.strip()
            if url:
                specs.append(SourceResolver.spec_from_url(url))

        # v0.1.x used a JSON field. Keep it as a fallback so existing users do
        # not lose their collections after upgrading, but prefer the new UI as
        # soon as any new-style source is configured.
        if not specs:
            specs.extend(SourceResolver.parse_specs(self._sources))

        deduplicated: List[CollectionSpec] = []
        seen = set()
        for spec in specs:
            key = (spec.source_type, spec.list_id or spec.url or spec.name)
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(spec)
        return deduplicated

    def sync_all(self):
        if not self._run_lock.acquire(blocking=False):
            logger.warning("智能合集同步任务已在运行，本次触发已跳过")
            return
        started = time.monotonic()
        run_record: Dict[str, Any] = {
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "server": self._emby_server,
            "success": False,
            "collections": [],
        }
        try:
            specs = self._collection_specs()
            if not specs:
                raise ValueError("尚未配置任何合集定义")

            service = MediaServerHelper().get_service(
                name=self._emby_server, type_filter="emby"
            )
            if not service:
                raise RuntimeError("未找到已启用的 Emby 服务器，请检查插件配置")
            if service.instance.is_inactive():
                raise RuntimeError("Emby 服务器当前未连接")

            emby = EmbyCollectionClient(service)
            library_index, duplicate_count = emby.build_library_index()
            logger.info(
                f"智能合集已读取 {len(library_index)} 个带 TMDB ID 的 Emby 媒体"
                f"，忽略重复项 {duplicate_count} 个"
            )
            resolver = SourceResolver(
                tmdb_token=self._tmdb_token,
                language=self._language,
                max_items=self._max_items,
                use_proxy=self._use_proxy,
            )
            douban_cache = self.get_data("douban_tmdb_cache") or {}

            for spec in specs:
                result = self._sync_one(
                    spec=spec,
                    resolver=resolver,
                    emby=emby,
                    library_index=library_index,
                    douban_cache=douban_cache,
                )
                run_record["collections"].append(result)

            self.save_data("douban_tmdb_cache", douban_cache)
            run_record["success"] = all(
                item.get("success") for item in run_record["collections"]
            )
        except Exception as exc:
            logger.exception(f"智能合集同步失败：{exc}")
            run_record["error"] = str(exc)
        finally:
            run_record["duration"] = round(time.monotonic() - started, 2)
            self._append_history(run_record)
            self._run_lock.release()

        if self._notify:
            self._notify_result(run_record)

    def _sync_one(
        self,
        spec: CollectionSpec,
        resolver: SourceResolver,
        emby: EmbyCollectionClient,
        library_index: Dict[Tuple[str, int], str],
        douban_cache: Dict[str, dict],
    ) -> Dict[str, Any]:
        item_result: Dict[str, Any] = {
            "name": spec.name,
            "source": spec.source_type,
            "success": False,
            "source_items": 0,
            "matched": 0,
            "missing": 0,
            "added": 0,
            "removed": 0,
        }
        try:
            resolved = resolver.fetch(spec)
            collection_name = spec.name or resolved.title
            if not collection_name:
                raise ValueError("无法确定 Emby 合集名称，请在配置中填写 name")
            item_result["name"] = collection_name
            item_result["source_items"] = len(resolved.items)

            normalized: List[MediaRef] = []
            for source_item in resolved.items:
                media_ref = self._resolve_media_ref(source_item, douban_cache)
                if media_ref:
                    normalized.append(media_ref)

            matched_ids = []
            matched_keys = set()
            for media_ref in normalized:
                key = (str(media_ref.media_type), int(media_ref.tmdb_id))
                emby_id = library_index.get(key)
                if not emby_id or key in matched_keys:
                    continue
                matched_keys.add(key)
                matched_ids.append(emby_id)

            item_result["matched"] = len(matched_ids)
            item_result["missing"] = max(
                0, item_result["source_items"] - len(matched_ids)
            )
            sync_result = emby.sync_collection(
                name=collection_name,
                item_ids=matched_ids,
                mode=spec.mode or self._sync_mode,
            )
            item_result.update(
                {
                    "success": True,
                    "collection_id": sync_result.collection_id,
                    "created": sync_result.created,
                    "added": sync_result.added,
                    "removed": sync_result.removed,
                }
            )
            logger.info(
                f"智能合集 {collection_name} 同步完成：来源 {item_result['source_items']}，"
                f"匹配 {item_result['matched']}，新增 {item_result['added']}，"
                f"移除 {item_result['removed']}"
            )
        except Exception as exc:
            item_result["error"] = str(exc)
            logger.error(f"智能合集 {item_result.get('name') or spec.source_type} 同步失败：{exc}")
        return item_result

    def _resolve_media_ref(
        self, media_ref: MediaRef, douban_cache: Dict[str, dict]
    ) -> Optional[MediaRef]:
        if media_ref.tmdb_id and media_ref.media_type in {"movie", "tv"}:
            return media_ref
        if not media_ref.douban_id:
            return None

        cached = douban_cache.get(str(media_ref.douban_id))
        if cached and cached.get("tmdb_id") and cached.get("type") in {"movie", "tv"}:
            return MediaRef(
                media_type=cached["type"],
                tmdb_id=int(cached["tmdb_id"]),
                douban_id=media_ref.douban_id,
                title=cached.get("title"),
            )

        mediainfo = self.chain.recognize_media(doubanid=str(media_ref.douban_id))
        if not mediainfo or not mediainfo.tmdb_id:
            return None
        media_type = (
            "movie" if mediainfo.type == MediaType.MOVIE else "tv"
            if mediainfo.type == MediaType.TV
            else None
        )
        if not media_type:
            return None
        douban_cache[str(media_ref.douban_id)] = {
            "type": media_type,
            "tmdb_id": int(mediainfo.tmdb_id),
            "title": mediainfo.title,
        }
        return MediaRef(
            media_type=media_type,
            tmdb_id=int(mediainfo.tmdb_id),
            douban_id=media_ref.douban_id,
            title=mediainfo.title,
        )

    def _append_history(self, run_record: Dict[str, Any]):
        history = self.get_data("history") or []
        history.insert(0, run_record)
        self.save_data("history", history[:20])

    def _notify_result(self, run_record: Dict[str, Any]):
        lines = []
        for item in run_record.get("collections") or []:
            state = "✅" if item.get("success") else "❌"
            lines.append(
                f"{state} {item.get('name') or '未命名'}：匹配 {item.get('matched', 0)}，"
                f"新增 {item.get('added', 0)}，移除 {item.get('removed', 0)}"
                + (f"（{item.get('error')}）" if item.get("error") else "")
            )
        if run_record.get("error"):
            lines.append(f"❌ {run_record['error']}")
        self.post_message(
            mtype=NotificationType.Plugin,
            title="智能合集同步完成" if run_record.get("success") else "智能合集同步有错误",
            text="\n".join(lines) or "没有可同步的合集。",
        )

    def _save_config(self):
        self.update_config(
            {
                "enabled": self._enabled,
                "onlyonce": self._onlyonce,
                "notify": self._notify,
                "cron": self._cron,
                "emby_server": self._emby_server,
                "sync_mode": self._sync_mode,
                "tmdb_token": self._tmdb_token,
                "language": self._language,
                "max_items": self._max_items,
                "use_proxy": self._use_proxy,
                "popular_tmdb": self._popular_tmdb,
                "popular_douban": self._popular_douban,
                "manual_urls": self._manual_urls,
                "sources": self._sources,
            }
        )

    @staticmethod
    def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            return max(minimum, min(int(value), maximum))
        except (TypeError, ValueError):
            return default

    def stop_service(self):
        if self._scheduler:
            try:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown(wait=False)
            except Exception as exc:
                logger.debug(f"停止智能合集临时调度器失败：{exc}")
            finally:
                self._scheduler = None
