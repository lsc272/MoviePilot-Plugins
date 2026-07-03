import base64
import datetime
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import Body

from app.chain.media import MediaChain
from app.chain.subscribe import SubscribeChain
from app.core.config import settings
from app.core.event import Event, eventmanager
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.mediaserver import MediaServerHelper
from app.log import logger
from app.plugins import _PluginBase
from app.scheduler import Scheduler
from app.schemas.types import EventType, MediaType, NotificationType, SystemConfigKey

from .collection_backup import EmbyCollectionBackupManager
from .emby import EmbyCollectionClient
from .poster import CollectionPosterBuilder
from .sources import (
    POPULAR_DOUBAN_LISTS,
    POPULAR_TMDB_LISTS,
    CollectionSpec,
    MediaRef,
    SourceResolver,
)


class SmartCollections(_PluginBase):
    _LEGACY_OSCAR_TITLE = "历届奥斯卡最佳动画长片及提名"
    _OSCAR_BEST_PICTURE_TITLE = "奥斯卡历届最佳影片"
    _POSTER_VERSION = 5
    _DOUBAN_FAILURE_CACHE_TTL = 6 * 3600
    _LEGACY_CATALOG_TITLES = {
        ("tmdb_builtin", "finly_golden_globes", "历届金球奖电影精选"): "金球奖最佳剧情片",
        ("tmdb_builtin", "finly_bafta", "历届英国电影学院奖精选"): "英国电影学院奖最佳影片",
        ("tmdb_builtin", "finly_cannes", "戛纳电影节精选"): "戛纳电影节金棕榈奖",
        ("tmdb_builtin", "finly_venice", "威尼斯电影节精选"): "威尼斯电影节金狮奖",
        ("tmdb_builtin", "finly_imdb_movies", "IMDb Top 250 电影"): "IMDb Top 250 Movies",
        ("tmdb_builtin", "finly_imdb_tv", "IMDb Top 250 剧集"): "IMDb Top 250 TV Shows",
        ("tmdb_builtin", "finly_letterboxd_500", "Letterboxd Top 500"): "Letterboxd's Top 500 Films",
        ("tmdb_builtin", "finly_letterboxd_animation_250", "Letterboxd Top 250 动画长片"): "Letterboxd's Top 250 Animated Films",
        ("tmdb_builtin", "finly_criterion", "Criterion Collection 精选"): "Criterion Collection",
        ("douban", "240962", "豆瓣高分电影榜（上）9.7–8.6"): "★豆瓣高分电影榜★ （上）9.7-8.6分",
        ("douban", "243559", "豆瓣高分电影榜（中）8.5–8.3"): "★豆瓣高分电影榜★ （中）8.5-8.3分",
        ("douban", "248893", "豆瓣高分电影榜（下）8.2–8.0"): "★豆瓣高分电影榜★ （下）8.2-8.0分",
        ("douban", "13922", "豆瓣冷门佳片（上）"): "【豆瓣冷门佳片】10-8.5分｜评分人数<5000",
        ("douban", "249029", "豆瓣冷门佳片（下）"): "【豆瓣冷门佳片】8.4-8分｜评分人数<5000",
        ("douban", "223781", "豆瓣高分动画长片"): "【豆瓣高分动画长片】",
        ("douban", "30299", "豆瓣电影 Top 250"): "豆瓣电影【口碑榜】2023-09-11 更新",
        ("douban", "515203", "豆瓣五星电影"): "历届奥斯卡最佳动画长片及提名",
        ("douban", "40435", "豆瓣高分科幻片"): "值得一看的电影和美剧",
        ("douban", "110522", "豆瓣高分喜剧片"): "有生之年一定要看的1001部电影",
        ("douban", "213727", "豆瓣高分爱情片"): "IMDb TV Shows Top 250",
        ("douban", "172901", "豆瓣高分悬疑片"): "【豆瓣五星电视剧】(1/2)",
        ("douban", "172901", "豆瓣五星电视剧"): "【豆瓣五星电视剧】(1/2)",
    }
    plugin_name = "智能合集"
    plugin_desc = "从热门 TMDB 片单、热门豆列或手动链接同步 Emby 合集。"
    plugin_icon = "smartcollections.svg"
    plugin_version = "0.5.0"
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
    _max_items = 2000
    _use_proxy = False
    _show_sidebar_nav = True
    _auto_poster = True
    _popular_tmdb: List[str] = []
    _popular_douban: List[str] = []
    _manual_urls = ""
    _sources = "[]"
    _managed_schedule_enabled = False
    _managed_schedule_cron = "0 4 * * *"
    _scheduler: Optional[BackgroundScheduler] = None
    _run_lock = threading.Lock()

    def __init__(self):
        super().__init__()
        self._scheduler = None
        self._run_lock = threading.Lock()
        self._preview_lock = threading.RLock()
        self._preview_cache: Dict[str, Dict[str, Any]] = {}
        self._preview_task_lock = threading.Lock()
        self._preview_task_status_lock = threading.RLock()
        self._preview_task_status: Dict[str, Any] = {
            "task_id": None,
            "running": False,
            "progress": 0,
            "message": "",
            "result": None,
            "error": None,
        }
        self._catalog_metadata_lock = threading.Lock()
        self._douban_chain_cooldown_until = 0.0
        self._collection_tools_lock = threading.Lock()
        self._collection_tools_status_lock = threading.RLock()
        self._collection_tools_status: Dict[str, Any] = {
            "running": False,
            "action": None,
            "progress": 0,
            "message": "",
            "result": None,
            "error": None,
            "inventory": None,
        }
        self._subscription_batch_lock = threading.Lock()
        self._subscription_batch_status_lock = threading.RLock()
        self._subscription_batch_status: Dict[str, Any] = {
            "running": False,
            "progress": 0,
            "message": "",
            "total": 0,
            "subscribed": 0,
            "failed": 0,
            "result": None,
            "error": None,
        }

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
        configured_max = config.get("max_items")
        migrate_max_items = configured_max is None or str(configured_max).strip() in {
            "",
            "500",
        }
        if migrate_max_items:
            configured_max = 2000
        self._max_items = self._safe_int(configured_max, 2000, 1, 5000)
        self._use_proxy = bool(config.get("use_proxy"))
        self._show_sidebar_nav = bool(config.get("show_sidebar_nav", True))
        self._auto_poster = bool(config.get("auto_poster", True))
        self._popular_tmdb = list(config.get("popular_tmdb") or [])
        self._popular_douban = list(config.get("popular_douban") or [])
        self._manual_urls = str(config.get("manual_urls") or "").strip()
        self._sources = config.get("sources") or "[]"
        self._managed_schedule_enabled = bool(
            config.get("managed_schedule_enabled", False)
        )
        self._managed_schedule_cron = str(
            config.get("managed_schedule_cron") or "0 4 * * *"
        ).strip()

        if self._onlyonce or self._managed_schedule_enabled:
            self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            if self._onlyonce:
                self._scheduler.add_job(
                    func=self.sync_all,
                    trigger="date",
                    run_date=datetime.datetime.now(tz=ZoneInfo(settings.TZ))
                    + datetime.timedelta(seconds=3),
                    name="智能合集立即同步",
                )
                self._onlyonce = False
                self._save_config()
            if self._managed_schedule_enabled:
                try:
                    managed_trigger = CronTrigger.from_crontab(
                        self._managed_schedule_cron
                    )
                    self._scheduler.add_job(
                        func=self.resync_managed_all,
                        trigger=managed_trigger,
                        id="smartcollections-managed-resync",
                        replace_existing=True,
                        name="智能合集定时批量重新同步",
                    )
                except ValueError as exc:
                    logger.error(f"智能合集定时批量重新同步 Cron 无效：{exc}")
                    self._managed_schedule_enabled = False
                    self._save_config()
            if self._scheduler.get_jobs():
                self._scheduler.start()
        if migrate_max_items:
            self._save_config()

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        return "vue", "dist/assets"

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        if not self._enabled or not self._show_sidebar_nav:
            return []
        return [
            {
                "nav_key": "main",
                "title": "智能合集",
                "icon": "mdi-playlist-star",
                "section": "organize",
                "permission": "manage",
                "order": 35,
            }
        ]

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
            {
                "path": "/status",
                "endpoint": self.api_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取智能合集页面数据",
            },
            {
                "path": "/settings",
                "endpoint": self.api_settings,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "保存工作台解析上限与默认更新模式",
            },
            {
                "path": "/catalog",
                "endpoint": self.api_catalog,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "获取动态片单目录元数据",
            },
            {
                "path": "/cache/export",
                "endpoint": self.api_cache_export,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "导出本地豆瓣到 TMDB 成功映射",
            },
            {
                "path": "/preview",
                "endpoint": self.api_preview,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "启动后台片单匹配预览",
            },
            {
                "path": "/preview/status",
                "endpoint": self.api_preview_status,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "查询片单匹配预览进度",
            },
            {
                "path": "/preview/sync",
                "endpoint": self.api_sync_preview,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "将预览结果同步到 Emby",
            },
            {
                "path": "/batch/sync",
                "endpoint": self.api_batch_sync,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "批量预览并同步片单",
            },
            {
                "path": "/templates/save",
                "endpoint": self.api_template_save,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "保存预览为模板",
            },
            {
                "path": "/templates/delete",
                "endpoint": self.api_template_delete,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "删除模板",
            },
            {
                "path": "/templates/import",
                "endpoint": self.api_templates_import,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "导入模板",
            },
            {
                "path": "/collections/resync",
                "endpoint": self.api_collection_resync,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "重新同步已管理合集",
            },
            {
                "path": "/collections/resync/all",
                "endpoint": self.api_collections_resync_all,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "后台批量重新同步全部已管理合集",
            },
            {
                "path": "/collections/schedule",
                "endpoint": self.api_managed_schedule,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "保存已管理合集的定时批量同步设置",
            },
            {
                "path": "/collections/delete",
                "endpoint": self.api_collection_delete,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "删除已管理合集",
            },
            {
                "path": "/collections/tools/status",
                "endpoint": self.api_collection_tools_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "查询 Emby 其他合集与备份状态",
            },
            {
                "path": "/collections/tools/backup",
                "endpoint": self.api_collection_tools_backup,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "备份非智能合集",
            },
            {
                "path": "/collections/tools/restore",
                "endpoint": self.api_collection_tools_restore,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "恢复非智能合集备份",
            },
            {
                "path": "/collections/tools/backup/delete",
                "endpoint": self.api_collection_tools_backup_delete,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "删除指定的其他合集备份",
            },
            {
                "path": "/collections/tools/cleanup",
                "endpoint": self.api_collection_tools_cleanup,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "自动备份后清理非智能合集",
            },
            {
                "path": "/subscribe",
                "endpoint": self.api_subscribe,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "订阅缺失影视",
            },
            {
                "path": "/subscribe/missing",
                "endpoint": self.api_subscribe_missing,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "后台批量订阅预览中的缺失影视",
            },
            {
                "path": "/subscribe/missing/status",
                "endpoint": self.api_subscribe_missing_status,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "查询批量订阅进度",
            },
            {
                "path": "/collections/poster/auto",
                "endpoint": self.api_collection_poster_auto,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "自动生成并设置合集海报",
            },
            {
                "path": "/collections/poster/upload",
                "endpoint": self.api_collection_poster_upload,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "上传自定义合集海报",
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
            "show_sidebar_nav": True,
            "auto_poster": True,
            "onlyonce": False,
            "notify": False,
            "use_proxy": False,
            "cron": "0 4 * * *",
            "emby_server": emby_servers[0]["value"] if len(emby_servers) == 1 else "",
            "sync_mode": "sync",
            "tmdb_token": "",
            "language": "zh-CN",
            "max_items": 2000,
            "popular_tmdb": [],
            "popular_douban": [],
            "manual_urls": "",
            "sources": "[]",
            "managed_schedule_enabled": False,
            "managed_schedule_cron": "0 4 * * *",
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

    def api_catalog(self) -> Dict[str, Any]:
        catalog = self._source_catalog()
        refreshing = self._catalog_metadata_lock.locked()
        if not refreshing:
            catalog = self._source_catalog()
        return {
            "success": True,
            "data": {
                "catalog": catalog,
                "refreshing": refreshing,
            },
        }

    def api_status(self) -> Dict[str, Any]:
        catalog = self._source_catalog()
        collections = []
        for item in self._load_managed_collections():
            record = dict(item)
            source_spec = record.get("source_spec") or {}
            record["name"] = self._migrate_catalog_title(
                str(source_spec.get("source_type") or ""),
                str(source_spec.get("list_id") or ""),
                str(record.get("name") or ""),
            )
            if not record.get("source_url"):
                try:
                    record["source_url"] = SourceResolver.source_url(
                        self._spec_from_payload(source_spec)
                    )
                except Exception:
                    record["source_url"] = None
            collections.append(record)
        collection_tools = self._collection_tools_snapshot(refresh_inventory=True)
        if not self._catalog_metadata_lock.locked():
            catalog = self._source_catalog()
        return {
            "success": True,
            "data": {
                "catalog": catalog,
                "catalog_refreshing": self._catalog_metadata_lock.locked(),
                "templates": self._load_templates(),
                "collections": collections,
                "collection_tools": collection_tools,
                "preview_task": self._preview_task_snapshot(include_result=False),
                "subscription_batch": self.api_subscribe_missing_status()["data"],
                "history": self.get_data("history") or [],
                "running": self._run_lock.locked(),
                "server": self._emby_server,
                "settings": {
                    "max_items": self._max_items,
                    "sync_mode": self._sync_mode,
                },
                "managed_schedule": {
                    "enabled": self._managed_schedule_enabled,
                    "cron": self._managed_schedule_cron,
                },
                "emby_servers": [
                    conf.name
                    for conf in MediaServerHelper().get_configs().values()
                    if conf.type == "emby"
                ],
            },
        }

    def api_preview(self, payload: dict = Body(...)) -> Dict[str, Any]:
        if not self._preview_task_lock.acquire(blocking=False):
            snapshot = self._preview_task_snapshot()
            return {
                "success": False,
                "message": snapshot.get("message") or "已有预览匹配任务正在运行",
            }
        try:
            spec = self._spec_from_payload(payload or {})
            task_id = uuid.uuid4().hex
            self._set_preview_task_status(
                task_id=task_id,
                running=True,
                progress=1,
                message="正在准备片单预览…",
                result=None,
                error=None,
            )
            threading.Thread(
                target=self._run_preview_task,
                args=(task_id, spec),
                name="SmartCollectionsPreview",
                daemon=True,
            ).start()
            return {
                "success": True,
                "data": {"task_id": task_id},
                "message": "预览匹配已在后台启动",
            }
        except Exception as exc:
            self._preview_task_lock.release()
            return {"success": False, "message": str(exc)}

    def api_preview_status(self, payload: dict = Body(...)) -> Dict[str, Any]:
        task_id = str((payload or {}).get("task_id") or "")
        snapshot = self._preview_task_snapshot()
        if task_id and snapshot.get("task_id") != task_id:
            return {"success": False, "message": "预览任务不存在或已经过期"}
        return {"success": True, "data": snapshot}

    def _run_preview_task(self, task_id: str, spec: CollectionSpec) -> None:
        try:
            preview = self._build_preview(
                spec,
                progress=lambda progress, message: self._set_preview_task_status(
                    task_id=task_id,
                    running=True,
                    progress=progress,
                    message=message,
                ),
            )
            self._set_preview_task_status(
                task_id=task_id,
                running=False,
                progress=100,
                message=(
                    f"预览完成：匹配 {preview.get('matched_count', 0)} / "
                    f"{preview.get('total_count', 0)}"
                ),
                result=preview,
                error=None,
            )
            try:
                self.post_message(
                    mtype=NotificationType.Plugin,
                    title="智能合集预览匹配完成",
                    text=(
                        f"{preview.get('title') or '未命名片单'}：共 "
                        f"{preview.get('total_count', 0)} 项，已匹配 "
                        f"{preview.get('matched_count', 0)} 项，缺失 "
                        f"{preview.get('missing_count', 0)} 项。"
                    ),
                )
            except Exception as notify_error:
                logger.warning(f"智能合集预览完成通知发送失败：{notify_error}")
        except Exception as exc:
            logger.exception(f"智能合集预览失败：{exc}")
            self._set_preview_task_status(
                task_id=task_id,
                running=False,
                message="预览匹配失败",
                error=str(exc),
            )
            try:
                self.post_message(
                    mtype=NotificationType.Plugin,
                    title="智能合集预览匹配失败",
                    text=str(exc),
                )
            except Exception as notify_error:
                logger.warning(f"智能合集预览失败通知发送失败：{notify_error}")
        finally:
            self._preview_task_lock.release()

    def _preview_task_snapshot(self, include_result: bool = True) -> Dict[str, Any]:
        with self._preview_task_status_lock:
            snapshot = dict(self._preview_task_status)
        if not include_result:
            snapshot.pop("result", None)
        return snapshot

    def _set_preview_task_status(self, **values: Any) -> None:
        with self._preview_task_status_lock:
            current_task = values.get("task_id")
            if (
                current_task
                and self._preview_task_status.get("task_id")
                and self._preview_task_status.get("task_id") != current_task
                and self._preview_task_status.get("running")
            ):
                return
            self._preview_task_status.update(values)

    def api_sync_preview(self, payload: dict = Body(...)) -> Dict[str, Any]:
        if not self._run_lock.acquire(blocking=False):
            return {"success": False, "message": "已有同步或批量任务正在运行"}
        try:
            preview = self._get_preview(str((payload or {}).get("preview_id") or ""))
            if not preview:
                raise ValueError("预览已过期，请重新预览后再同步")
            result = self._sync_preview_data(
                preview=preview,
                name=str((payload or {}).get("name") or preview.get("title") or "").strip(),
                mode=str((payload or {}).get("mode") or self._sync_mode),
                selected_keys=(payload or {}).get("selected_keys"),
            )
            return {"success": True, "data": result, "message": "合集同步完成"}
        except Exception as exc:
            logger.exception(f"智能合集同步预览失败：{exc}")
            return {"success": False, "message": str(exc)}
        finally:
            self._run_lock.release()

    def api_batch_sync(self, payload: dict = Body(...)) -> Dict[str, Any]:
        sources = (payload or {}).get("sources") or []
        if not isinstance(sources, list) or not sources:
            return {"success": False, "message": "请至少选择一个片单"}
        if not self._run_lock.acquire(blocking=False):
            return {"success": False, "message": "已有同步或批量任务正在运行"}
        results: List[dict] = []
        try:
            context = self._preview_context()
            for source in sources:
                try:
                    spec = self._spec_from_payload(source or {})
                    preview = self._build_preview(spec, context=context)
                    results.append(
                        self._sync_preview_data(
                            preview=preview,
                            name=spec.name or preview.get("title"),
                            mode=spec.mode or self._sync_mode,
                        )
                    )
                except Exception as exc:
                    results.append(
                        {
                            "success": False,
                            "name": (source or {}).get("name")
                            or (source or {}).get("title")
                            or "未命名片单",
                            "error": str(exc),
                        }
                    )
            return {
                "success": any(item.get("success") for item in results),
                "data": results,
                "message": f"批量任务完成：成功 {sum(bool(item.get('success')) for item in results)} / {len(results)}",
            }
        finally:
            self._run_lock.release()

    def api_template_save(self, payload: dict = Body(...)) -> Dict[str, Any]:
        try:
            preview = self._get_preview(str((payload or {}).get("preview_id") or ""))
            if not preview:
                raise ValueError("预览已过期，请重新预览后保存模板")
            name = str((payload or {}).get("name") or preview.get("title") or "").strip()
            if not name:
                raise ValueError("模板名称不能为空")
            items = [
                {
                    "type": row.get("media_type"),
                    "tmdb_id": row.get("tmdb_id"),
                    "title": row.get("title"),
                    "year": row.get("year"),
                    "poster_url": row.get("poster_url"),
                }
                for row in preview.get("items") or []
                if row.get("media_type") in {"movie", "tv"} and row.get("tmdb_id")
            ]
            if not items:
                raise ValueError("当前预览没有可保存的 TMDB 条目")
            templates = self._load_templates()
            template = {
                "id": uuid.uuid4().hex,
                "name": name,
                "description": str((payload or {}).get("description") or "").strip(),
                "source_spec": preview.get("spec"),
                "items": items,
                "item_count": len(items),
                "created_at": self._now(),
            }
            templates.insert(0, template)
            self.save_data("templates", templates[:100])
            return {"success": True, "data": template, "message": "模板已保存"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    def api_template_delete(self, payload: dict = Body(...)) -> Dict[str, Any]:
        template_id = str((payload or {}).get("template_id") or "")
        templates = [
            item for item in self._load_templates() if str(item.get("id")) != template_id
        ]
        self.save_data("templates", templates)
        return {"success": True, "message": "模板已删除"}

    def api_templates_import(self, payload: dict = Body(...)) -> Dict[str, Any]:
        raw_templates = (payload or {}).get("templates")
        if not isinstance(raw_templates, list):
            return {"success": False, "message": "模板数据必须是数组"}
        templates = self._load_templates()
        imported = 0
        for raw in raw_templates[:100]:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or "").strip()
            items = raw.get("items") or []
            if not name or not isinstance(items, list):
                continue
            try:
                parsed = SourceResolver._parse_template(
                    CollectionSpec(source_type="template", name=name, items=items)
                )
            except Exception:
                continue
            templates.insert(
                0,
                {
                    "id": uuid.uuid4().hex,
                    "name": name,
                    "description": str(raw.get("description") or "").strip(),
                    "source_spec": raw.get("source_spec"),
                    "items": [asdict(item) for item in parsed.items],
                    "item_count": len(parsed.items),
                    "created_at": self._now(),
                },
            )
            imported += 1
        self.save_data("templates", templates[:100])
        return {"success": True, "data": {"imported": imported}, "message": f"已导入 {imported} 个模板"}

    def api_collection_resync(self, payload: dict = Body(...)) -> Dict[str, Any]:
        collection_id = str((payload or {}).get("collection_id") or "")
        record = next(
            (item for item in self._load_managed_collections() if str(item.get("id")) == collection_id),
            None,
        )
        if not record:
            return {"success": False, "message": "未找到合集记录"}
        if not self._run_lock.acquire(blocking=False):
            return {"success": False, "message": "已有同步或批量任务正在运行"}
        try:
            spec = self._spec_from_payload(record.get("source_spec") or {})
            preview = self._build_preview(spec)
            source_spec = record.get("source_spec") or {}
            collection_name = self._migrate_catalog_title(
                str(source_spec.get("source_type") or ""),
                str(source_spec.get("list_id") or ""),
                str(record.get("name") or preview.get("title") or ""),
            )
            result = self._sync_preview_data(
                preview=preview,
                name=collection_name,
                mode=record.get("mode") or self._sync_mode,
                record_id=collection_id,
            )
            return {"success": True, "data": result, "message": "合集已重新同步"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}
        finally:
            self._run_lock.release()

    def api_collections_resync_all(self) -> Dict[str, Any]:
        if self._run_lock.locked():
            return {"success": False, "message": "已有同步或批量任务正在运行"}
        if not self._load_managed_collections():
            return {"success": False, "message": "还没有已管理的智能合集"}
        threading.Thread(
            target=self.resync_managed_all,
            name="SmartCollectionsManagedResync",
            daemon=True,
        ).start()
        return {"success": True, "message": "批量重新同步已在后台启动"}

    def api_managed_schedule(self, payload: dict = Body(...)) -> Dict[str, Any]:
        enabled = bool((payload or {}).get("enabled"))
        cron = str((payload or {}).get("cron") or "0 4 * * *").strip()
        if enabled:
            try:
                CronTrigger.from_crontab(cron)
            except ValueError as exc:
                return {"success": False, "message": f"Cron 表达式无效：{exc}"}
        self._managed_schedule_enabled = enabled
        self._managed_schedule_cron = cron
        self._save_config()
        self._configure_managed_scheduler()
        return {
            "success": True,
            "data": {"enabled": enabled, "cron": cron},
            "message": "定时批量重新同步设置已保存",
        }

    def _configure_managed_scheduler(self) -> None:
        if self._scheduler:
            try:
                self._scheduler.remove_job("smartcollections-managed-resync")
            except Exception:
                pass
        if self._managed_schedule_enabled:
            if not self._scheduler:
                self._scheduler = BackgroundScheduler(timezone=settings.TZ)
            self._scheduler.add_job(
                func=self.resync_managed_all,
                trigger=CronTrigger.from_crontab(self._managed_schedule_cron),
                id="smartcollections-managed-resync",
                replace_existing=True,
                name="智能合集定时批量重新同步",
            )
            if not self._scheduler.running:
                self._scheduler.start()
        elif self._scheduler and not self._scheduler.get_jobs():
            if self._scheduler.running:
                self._scheduler.shutdown(wait=False)
            self._scheduler = None

    def resync_managed_all(self) -> None:
        if not self._run_lock.acquire(blocking=False):
            logger.warning("智能合集批量重新同步任务已在运行，本次触发已跳过")
            if self._managed_schedule_enabled and self._scheduler:
                self._scheduler.add_job(
                    func=self.resync_managed_all,
                    trigger="date",
                    run_date=datetime.datetime.now(tz=ZoneInfo(settings.TZ))
                    + datetime.timedelta(minutes=5),
                    id="smartcollections-managed-resync-retry",
                    replace_existing=True,
                    name="智能合集批量重新同步重试",
                )
            return
        started = time.monotonic()
        run_record: Dict[str, Any] = {
            "time": self._now(),
            "server": self._emby_server,
            "success": False,
            "collections": [],
        }
        try:
            records = self._load_managed_collections()
            if not records:
                raise ValueError("还没有已管理的智能合集")
            context = self._preview_context()
            for record in records:
                try:
                    spec = self._spec_from_payload(record.get("source_spec") or {})
                    preview = self._build_preview(spec, context=context)
                    source_spec = record.get("source_spec") or {}
                    name = self._migrate_catalog_title(
                        str(source_spec.get("source_type") or ""),
                        str(source_spec.get("list_id") or ""),
                        str(record.get("name") or preview.get("title") or ""),
                    )
                    run_record["collections"].append(
                        self._sync_preview_data(
                            preview=preview,
                            name=name,
                            mode=record.get("mode") or self._sync_mode,
                            record_id=str(record.get("id") or ""),
                            append_history=False,
                        )
                    )
                except Exception as exc:
                    run_record["collections"].append(
                        {
                            "success": False,
                            "name": record.get("name") or "未命名合集",
                            "error": str(exc),
                        }
                    )
            run_record["success"] = all(
                item.get("success") for item in run_record["collections"]
            )
        except Exception as exc:
            logger.exception(f"智能合集批量重新同步失败：{exc}")
            run_record["error"] = str(exc)
        finally:
            run_record["duration"] = round(time.monotonic() - started, 2)
            self._append_history(run_record)
            self._run_lock.release()
        if self._notify:
            self._notify_result(run_record)

    def api_collection_delete(self, payload: dict = Body(...)) -> Dict[str, Any]:
        collection_id = str((payload or {}).get("collection_id") or "")
        records = self._load_managed_collections()
        record = next((item for item in records if str(item.get("id")) == collection_id), None)
        if not record:
            return {"success": False, "message": "未找到合集记录"}
        try:
            if bool((payload or {}).get("delete_emby", True)) and record.get("emby_collection_id"):
                self._emby_client().delete_collection(str(record["emby_collection_id"]))
            self.save_data(
                "managed_collections",
                [item for item in records if str(item.get("id")) != collection_id],
            )
            return {"success": True, "message": "合集记录已删除"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    def api_collection_tools_status(self) -> Dict[str, Any]:
        return {
            "success": True,
            "data": self._collection_tools_snapshot(refresh_inventory=True),
        }

    def api_collection_tools_backup(self) -> Dict[str, Any]:
        return self._start_collection_tool("backup", {})

    def api_collection_tools_restore(
        self, payload: dict = Body(...)
    ) -> Dict[str, Any]:
        backup_id = str((payload or {}).get("backup_id") or "").strip()
        if not backup_id:
            try:
                backups = self._collection_backup_manager().list_backups()
            except Exception as exc:
                return {"success": False, "message": str(exc)}
            backup_id = str(backups[0]["id"]) if backups else ""
        if not backup_id:
            return {"success": False, "message": "还没有可恢复的合集备份"}
        return self._start_collection_tool(
            "restore", {"backup_id": backup_id}
        )

    def api_collection_tools_backup_delete(
        self, payload: dict = Body(...)
    ) -> Dict[str, Any]:
        backup_id = str((payload or {}).get("backup_id") or "").strip()
        if not backup_id:
            return {"success": False, "message": "请选择要删除的备份"}
        if not self._collection_tools_lock.acquire(blocking=False):
            return {"success": False, "message": "其他合集工具任务正在运行"}
        try:
            result = self._collection_backup_manager().delete_backup(backup_id)
            return {"success": True, "data": result, "message": "备份已删除"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}
        finally:
            self._collection_tools_lock.release()

    def api_collection_tools_cleanup(
        self, payload: dict = Body(...)
    ) -> Dict[str, Any]:
        try:
            expected = int((payload or {}).get("confirm_count"))
        except (TypeError, ValueError):
            return {"success": False, "message": "请先确认待清理合集数量"}
        try:
            inventory = self._collection_backup_manager().inventory(
                self._managed_emby_collection_ids()
            )
        except Exception as exc:
            return {"success": False, "message": str(exc)}
        current = int(inventory.get("other") or 0)
        if current <= 0:
            return {"success": False, "message": "当前没有需要清理的其他合集"}
        if expected != current:
            return {
                "success": False,
                "message": f"合集数量已变化：当前为 {current} 个，请刷新后重新确认",
            }
        return self._start_collection_tool(
            "cleanup", {"confirm_count": current}
        )

    def _start_collection_tool(
        self, action: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not self._collection_tools_lock.acquire(blocking=False):
            return {"success": False, "message": "合集备份或恢复任务正在运行"}
        if not self._run_lock.acquire(blocking=False):
            self._collection_tools_lock.release()
            return {"success": False, "message": "智能合集同步任务正在运行，请稍后再试"}
        labels = {
            "backup": "备份其他合集",
            "restore": "恢复其他合集",
            "cleanup": "备份并清理其他合集",
        }
        with self._collection_tools_status_lock:
            inventory = self._collection_tools_status.get("inventory")
            self._collection_tools_status = {
                "running": True,
                "action": action,
                "progress": 0,
                "message": f"正在准备{labels.get(action, '合集任务')}...",
                "result": None,
                "error": None,
                "inventory": inventory,
            }
        try:
            threading.Thread(
                target=self._run_collection_tool,
                args=(action, payload),
                name=f"SmartCollections-{action}",
                daemon=True,
            ).start()
        except Exception as exc:
            self._run_lock.release()
            self._collection_tools_lock.release()
            with self._collection_tools_status_lock:
                self._collection_tools_status.update(
                    {"running": False, "error": str(exc), "message": "合集任务启动失败"}
                )
            return {"success": False, "message": str(exc)}
        return {
            "success": True,
            "data": {"action": action},
            "message": f"{labels.get(action, '合集任务')}已启动",
        }

    def _run_collection_tool(
        self, action: str, payload: Dict[str, Any]
    ) -> None:
        try:
            manager = self._collection_backup_manager()
            protected_ids = self._managed_emby_collection_ids()

            def update_progress(done: int, total: int, message: str) -> None:
                value = round(done / max(1, total) * 100, 1)
                with self._collection_tools_status_lock:
                    self._collection_tools_status.update(
                        {"progress": min(100, value), "message": message}
                    )

            if action == "backup":
                result = manager.create_backup(
                    protected_ids=protected_ids,
                    server_name=self._emby_server or "Emby",
                    progress=update_progress,
                )
                message = f"已备份 {result.get('collection_count', 0)} 个其他合集"
            elif action == "restore":
                result = manager.restore_backup(
                    backup_id=str(payload.get("backup_id") or ""),
                    protected_ids=protected_ids,
                    progress=update_progress,
                )
                message = (
                    f"恢复完成：新建 {result.get('created', 0)}，"
                    f"合并 {result.get('merged', 0)}，失败 {result.get('failed', 0)}"
                )
            elif action == "cleanup":
                result = manager.backup_and_cleanup(
                    protected_ids=protected_ids,
                    server_name=self._emby_server or "Emby",
                    progress=update_progress,
                )
                message = (
                    f"已自动备份并清理 {result.get('deleted', 0)} 个其他合集，"
                    f"失败 {result.get('failed', 0)}"
                )
            else:
                raise ValueError("未知的合集工具任务")
            inventory = manager.inventory(protected_ids)
            with self._collection_tools_status_lock:
                self._collection_tools_status.update(
                    {
                        "running": False,
                        "progress": 100,
                        "message": message,
                        "result": result,
                        "error": None,
                        "inventory": inventory,
                    }
                )
        except Exception as exc:
            logger.exception(f"智能合集 Emby 合集工具执行失败：{exc}")
            with self._collection_tools_status_lock:
                self._collection_tools_status.update(
                    {
                        "running": False,
                        "message": "合集任务执行失败",
                        "error": str(exc),
                    }
                )
        finally:
            self._run_lock.release()
            self._collection_tools_lock.release()

    def api_subscribe(self, payload: dict = Body(...)) -> Dict[str, Any]:
        return self._subscribe_item(payload or {}, background_search=True)

    def _subscribe_item(
        self, payload: Dict[str, Any], background_search: bool
    ) -> Dict[str, Any]:
        payload = payload or {}
        try:
            tmdb_id = int(payload.get("tmdb_id"))
        except (TypeError, ValueError):
            return {"success": False, "message": "缺少有效的 TMDB ID"}
        media_type = str(payload.get("media_type") or "").lower()
        if media_type not in {"movie", "tv"}:
            return {"success": False, "message": "缺少有效的媒体类型"}
        title = str(payload.get("title") or "").strip()
        if not title:
            return {"success": False, "message": "缺少影视标题"}
        mtype = MediaType.MOVIE if media_type == "movie" else MediaType.TV
        try:
            default_filter_groups = (
                SystemConfigOper().get(SystemConfigKey.SubscribeFilterRuleGroups)
                or None
            )
            subscription_id, message = SubscribeChain().add(
                title=title,
                year=str(payload.get("year") or ""),
                mtype=mtype,
                tmdbid=tmdb_id,
                exist_ok=True,
                message=False,
                username="智能合集",
                filter_groups=default_filter_groups,
            )
            message = str(message or "")
            if subscription_id:
                search_kwargs = {
                    "job_id": "subscribe_search",
                    "sid": int(subscription_id),
                    "state": None,
                    "manual": True,
                }
                if background_search:
                    threading.Thread(
                        target=Scheduler().start,
                        kwargs=search_kwargs,
                        name=f"SmartCollectionsSubscribeSearch-{subscription_id}",
                        daemon=True,
                    ).start()
                else:
                    Scheduler().start(**search_kwargs)
                already_exists = any(
                    keyword in message for keyword in ("存在", "重复", "订阅中")
                )
                return {
                    "success": True,
                    "data": {
                        "subscription_id": subscription_id,
                        "already_exists": already_exists,
                        "search_started": True,
                    },
                    "message": f"{message or '已添加订阅'}，已开始搜索资源",
                }
            if any(keyword in message for keyword in ("存在", "重复", "订阅中")):
                return {
                    "success": True,
                    "data": {"subscription_id": None, "already_exists": True},
                    "message": message or "订阅已存在",
                }
            return {"success": False, "message": message or "添加订阅失败"}
        except Exception as exc:
            logger.exception(f"智能合集添加订阅失败：{exc}")
            return {"success": False, "message": str(exc)}

    def api_subscribe_missing_status(self) -> Dict[str, Any]:
        with self._subscription_batch_status_lock:
            return {"success": True, "data": dict(self._subscription_batch_status)}

    def api_subscribe_missing(
        self, payload: dict = Body(...)
    ) -> Dict[str, Any]:
        preview = self._get_preview(str((payload or {}).get("preview_id") or ""))
        if not preview:
            return {"success": False, "message": "预览已过期，请重新预览后再订阅"}
        items = [
            dict(item)
            for item in preview.get("items") or []
            if not item.get("matched")
            and item.get("tmdb_id")
            and item.get("media_type") in {"movie", "tv"}
        ]
        if not items:
            return {"success": False, "message": "当前没有可订阅的缺失项目"}
        if not self._subscription_batch_lock.acquire(blocking=False):
            return {"success": False, "message": "已有一键订阅任务正在运行"}

        with self._subscription_batch_status_lock:
            self._subscription_batch_status = {
                "running": True,
                "progress": 0,
                "message": f"准备订阅 {len(items)} 个缺失项目",
                "total": len(items),
                "subscribed": 0,
                "failed": 0,
                "result": None,
                "error": None,
            }
        try:
            threading.Thread(
                target=self._run_subscribe_missing,
                args=(items,),
                name="SmartCollectionsSubscribeMissing",
                daemon=True,
            ).start()
        except Exception as exc:
            with self._subscription_batch_status_lock:
                self._subscription_batch_status.update(
                    {
                        "running": False,
                        "message": "一键订阅任务启动失败",
                        "error": str(exc),
                    }
                )
            self._subscription_batch_lock.release()
            return {"success": False, "message": str(exc)}
        return {
            "success": True,
            "data": {"total": len(items)},
            "message": f"已开始订阅 {len(items)} 个缺失项目",
        }

    def _run_subscribe_missing(self, items: List[Dict[str, Any]]) -> None:
        subscribed = 0
        failed = 0
        subscribed_keys: List[str] = []
        failures: List[Dict[str, str]] = []
        total = len(items)
        try:
            for index, item in enumerate(items, start=1):
                response = self._subscribe_item(item, background_search=False)
                if response.get("success"):
                    subscribed += 1
                    subscribed_keys.append(str(item.get("key") or ""))
                else:
                    failed += 1
                    failures.append(
                        {
                            "title": str(item.get("title") or "未命名"),
                            "message": str(response.get("message") or "添加订阅失败"),
                        }
                    )
                with self._subscription_batch_status_lock:
                    self._subscription_batch_status.update(
                        {
                            "progress": round(index / max(1, total) * 100, 1),
                            "message": f"正在处理 {index}/{total}：{item.get('title') or '未命名'}",
                            "subscribed": subscribed,
                            "failed": failed,
                        }
                    )
            result = {
                "total": total,
                "subscribed": subscribed,
                "failed": failed,
                "subscribed_keys": subscribed_keys,
                "failures": failures[:20],
            }
            with self._subscription_batch_status_lock:
                self._subscription_batch_status.update(
                    {
                        "running": False,
                        "progress": 100,
                        "message": f"一键订阅完成：成功 {subscribed}，失败 {failed}",
                        "result": result,
                        "error": None,
                    }
                )
        except Exception as exc:
            logger.exception(f"智能合集一键订阅缺失项目失败：{exc}")
            with self._subscription_batch_status_lock:
                self._subscription_batch_status.update(
                    {
                        "running": False,
                        "message": "一键订阅任务失败",
                        "error": str(exc),
                    }
                )
        finally:
            self._subscription_batch_lock.release()

    def api_collection_poster_auto(self, payload: dict = Body(...)) -> Dict[str, Any]:
        record = self._managed_collection_from_payload(payload)
        if not record:
            return {"success": False, "message": "未找到合集记录"}
        try:
            spec = self._spec_from_payload(record.get("source_spec") or {})
            preview = self._build_preview(spec)
            self._generate_and_set_poster(record, preview, source="auto")
            return {"success": True, "message": "合集海报已自动生成并上传"}
        except Exception as exc:
            logger.exception(f"智能合集自动生成海报失败：{exc}")
            return {"success": False, "message": str(exc)}

    def api_collection_poster_upload(self, payload: dict = Body(...)) -> Dict[str, Any]:
        record = self._managed_collection_from_payload(payload)
        if not record:
            return {"success": False, "message": "未找到合集记录"}
        encoded = str((payload or {}).get("image") or "").strip()
        if not encoded:
            return {"success": False, "message": "请选择要上传的海报图片"}
        try:
            if "," in encoded:
                encoded = encoded.split(",", 1)[1]
            content = base64.b64decode(encoded, validate=True)
            image = CollectionPosterBuilder.normalize_upload(content)
            self._emby_client().set_collection_poster(
                str(record.get("emby_collection_id") or ""), image
            )
            self._mark_collection_poster(str(record["id"]), "custom")
            return {"success": True, "message": "自定义合集海报已上传"}
        except Exception as exc:
            logger.exception(f"智能合集上传海报失败：{exc}")
            return {"success": False, "message": str(exc)}

    def _managed_collection_from_payload(self, payload: dict) -> Optional[dict]:
        collection_id = str((payload or {}).get("collection_id") or "")
        return next(
            (
                item
                for item in self._load_managed_collections()
                if str(item.get("id")) == collection_id
            ),
            None,
        )

    @staticmethod
    def _now() -> str:
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def _migrate_catalog_title(
        cls, source_type: str, list_id: str, title: str
    ) -> str:
        if list_id == "finly_oscars_animation" and title == cls._LEGACY_OSCAR_TITLE:
            return cls._OSCAR_BEST_PICTURE_TITLE
        return cls._LEGACY_CATALOG_TITLES.get(
            (str(source_type), str(list_id), str(title)), str(title)
        )

    def _source_catalog(self) -> Dict[str, List[dict]]:
        metadata = self._catalog_metadata()
        return {
            "tmdb": [
                {
                    "id": f"tmdb:{item['value']}",
                    "source_type": "tmdb_builtin",
                    "list_id": item["value"],
                    "name": metadata.get(f"tmdb:{item['value']}", {}).get("title")
                    or item["title"],
                    "title": metadata.get(f"tmdb:{item['value']}", {}).get("title")
                    or item["title"],
                    "url": item.get("url"),
                    "media_type": item.get("media_type"),
                    "description": metadata.get(f"tmdb:{item['value']}", {}).get("description")
                    or "",
                    "item_count": metadata.get(f"tmdb:{item['value']}", {}).get("item_count"),
                    "use_source_title": True,
                }
                for item in POPULAR_TMDB_LISTS
            ],
            "douban": [
                {
                    "id": f"douban:{item['value']}",
                    "source_type": "douban",
                    "list_id": item["value"],
                    "name": metadata.get(f"douban:{item['value']}", {}).get("title")
                    or item["title"],
                    "title": metadata.get(f"douban:{item['value']}", {}).get("title")
                    or item["title"],
                    "url": f"https://www.douban.com/doulist/{item['value']}/",
                    "media_type": item.get("media_type") or "movie",
                    "description": metadata.get(f"douban:{item['value']}", {}).get("description")
                    or "",
                    "item_count": metadata.get(f"douban:{item['value']}", {}).get("item_count"),
                    "use_source_title": True,
                }
                for item in POPULAR_DOUBAN_LISTS
            ],
        }

    def _catalog_metadata(self) -> Dict[str, Dict[str, Any]]:
        cached = self.get_data("catalog_metadata") or {}
        cached_items = cached.get("items") if isinstance(cached, dict) else {}
        cached_items = cached_items if isinstance(cached_items, dict) else {}
        try:
            age = time.time() - float(cached.get("updated_at") or 0)
        except (TypeError, ValueError):
            age = 10**9
        if age < 6 * 3600:
            return cached_items

        if not self._catalog_metadata_lock.acquire(blocking=False):
            return cached_items
        threading.Thread(
            target=self._refresh_catalog_metadata,
            args=(dict(cached_items),),
            name="SmartCollectionsCatalogMetadata",
            daemon=True,
        ).start()
        return cached_items

    def _refresh_catalog_metadata(
        self, cached_items: Dict[str, Dict[str, Any]]
    ) -> None:
        try:
            resolver = SourceResolver(
                tmdb_token=self._tmdb_token,
                language=self._language,
                max_items=1,
                use_proxy=self._use_proxy,
            )
            definitions: List[Tuple[str, CollectionSpec]] = []
            for item in POPULAR_TMDB_LISTS:
                definitions.append(
                    (
                        f"tmdb:{item['value']}",
                        CollectionSpec(
                            source_type="tmdb_builtin",
                            list_id=str(item["value"]),
                            media_type=item.get("media_type"),
                        ),
                    )
                )
            for item in POPULAR_DOUBAN_LISTS:
                definitions.append(
                    (
                        f"douban:{item['value']}",
                        CollectionSpec(
                            source_type="douban",
                            list_id=str(item["value"]),
                            media_type=item.get("media_type"),
                        ),
                    )
                )

            refreshed = dict(cached_items)

            def load(definition: Tuple[str, CollectionSpec]):
                key, spec = definition
                resolved = resolver.fetch(spec)
                return key, {
                    "title": resolved.title,
                    "description": resolved.description or "",
                    "item_count": resolved.reported_total
                    if resolved.reported_total is not None
                    else len(resolved.items),
                }

            with ThreadPoolExecutor(
                max_workers=min(8, len(definitions)),
                thread_name_prefix="SmartCollectionsCatalog",
            ) as executor:
                futures = [executor.submit(load, definition) for definition in definitions]
                for future in as_completed(futures):
                    try:
                        key, value = future.result()
                        refreshed[key] = value
                    except Exception as exc:
                        logger.debug(f"智能合集片单目录元数据刷新失败：{exc}")

            self.save_data(
                "catalog_metadata",
                {"updated_at": time.time(), "items": refreshed},
            )
        except Exception as exc:
            logger.warning(f"智能合集片单目录元数据刷新失败：{exc}")
        finally:
            self._catalog_metadata_lock.release()

    def _load_templates(self) -> List[dict]:
        templates = self.get_data("templates") or []
        return templates if isinstance(templates, list) else []

    def _load_managed_collections(self) -> List[dict]:
        records = self.get_data("managed_collections") or []
        return records if isinstance(records, list) else []

    def _spec_from_payload(self, payload: dict) -> CollectionSpec:
        payload = payload or {}
        if isinstance(payload.get("source"), dict):
            payload = payload["source"]
        if isinstance(payload.get("source_spec"), dict) and not payload.get("source_type"):
            payload = payload["source_spec"]

        template_id = str(payload.get("template_id") or "").strip()
        if template_id:
            template = next(
                (item for item in self._load_templates() if str(item.get("id")) == template_id),
                None,
            )
            if not template:
                raise ValueError("模板不存在或已删除")
            return CollectionSpec(
                source_type="template",
                name=str(payload.get("name") or template.get("name") or "").strip(),
                items=template.get("items") or [],
                mode=str(payload.get("mode") or "").strip() or None,
                description=str(template.get("description") or "").strip() or None,
            )

        source_type = str(
            payload.get("source_type") or payload.get("type") or ""
        ).strip().lower()
        url = str(payload.get("url") or "").strip()
        name = str(payload.get("name") or payload.get("title") or "").strip() or None
        mode = str(payload.get("mode") or "").strip().lower() or None
        if source_type in {"manual", "url", ""} and url:
            spec = SourceResolver.spec_from_url(url)
            spec.name = name
            spec.mode = mode
            spec.description = str(payload.get("description") or "").strip() or None
            return spec
        if source_type not in {"tmdb", "tmdb_builtin", "douban", "template"}:
            raise ValueError("不支持的片单来源")
        list_id = str(payload.get("list_id") or payload.get("value") or "").strip() or None
        if (
            source_type == "tmdb_builtin"
            and list_id == "finly_oscars_animation"
            and name == self._LEGACY_OSCAR_TITLE
        ):
            name = self._OSCAR_BEST_PICTURE_TITLE
        name = (
            self._migrate_catalog_title(
                source_type, str(list_id or ""), name or ""
            )
            or None
        )
        media_type = str(payload.get("media_type") or "").lower().strip() or None
        if source_type == "douban" and not media_type:
            definition = next(
                (
                    item
                    for item in POPULAR_DOUBAN_LISTS
                    if str(item.get("value")) == str(list_id or "")
                ),
                None,
            )
            media_type = (definition or {}).get("media_type") or "movie"
        items = payload.get("items") or []
        spec = CollectionSpec(
            source_type=source_type,
            name=name,
            url=url or None,
            list_id=list_id,
            items=items,
            mode=mode,
            media_type=media_type,
            use_source_title=bool(payload.get("use_source_title")),
            description=str(payload.get("description") or "").strip() or None,
        )
        if source_type == "template" and not items:
            raise ValueError("模板没有影视条目")
        if source_type != "template" and not (url or list_id):
            raise ValueError("片单缺少链接或 ID")
        return spec

    def _emby_client(self) -> EmbyCollectionClient:
        service = MediaServerHelper().get_service(
            name=self._emby_server, type_filter="emby"
        )
        if not service:
            raise RuntimeError("未找到已启用的 Emby 服务器，请检查插件配置")
        if service.instance.is_inactive():
            raise RuntimeError("Emby 服务器当前未连接")
        return EmbyCollectionClient(service)

    def _managed_emby_collection_ids(self) -> List[str]:
        return [
            str(item.get("emby_collection_id"))
            for item in self._load_managed_collections()
            if item.get("emby_collection_id")
        ]

    def _collection_backup_manager(self) -> EmbyCollectionBackupManager:
        return EmbyCollectionBackupManager(
            backup_root=self.get_data_path() / "collection_backups",
            client=self._emby_client(),
        )

    def _collection_tools_snapshot(
        self, refresh_inventory: bool = False
    ) -> Dict[str, Any]:
        with self._collection_tools_status_lock:
            snapshot = dict(self._collection_tools_status)
        try:
            manager = self._collection_backup_manager()
            snapshot["backups"] = manager.list_backups()
            if refresh_inventory and not snapshot.get("running"):
                inventory = manager.inventory(self._managed_emby_collection_ids())
                snapshot["inventory"] = inventory
                with self._collection_tools_status_lock:
                    self._collection_tools_status["inventory"] = inventory
            snapshot["available"] = True
        except Exception as exc:
            snapshot.setdefault("backups", [])
            snapshot["available"] = False
            snapshot["inventory_error"] = str(exc)
        return snapshot

    def _preview_context(self) -> Dict[str, Any]:
        emby = self._emby_client()
        catalog, title_index, duplicate_count = emby.build_library_catalog()
        logger.info(
            f"智能合集预览已读取 {len(catalog)} 个带 TMDB ID 的 Emby 媒体"
            f"，忽略重复项 {duplicate_count} 个"
        )
        return {
            "emby": emby,
            "catalog": catalog,
            "title_index": title_index,
            "resolver": SourceResolver(
                tmdb_token=self._tmdb_token,
                language=self._language,
                max_items=self._max_items,
                use_proxy=self._use_proxy,
            ),
            "douban_cache": self._load_douban_cache(),
        }

    def api_settings(self, payload: dict = Body(...)) -> Dict[str, Any]:
        payload = payload or {}
        sync_mode = str(payload.get("sync_mode") or "sync").strip().lower()
        if sync_mode not in {"sync", "append"}:
            return {"success": False, "message": "更新模式必须为同步或仅追加"}
        self._max_items = self._safe_int(payload.get("max_items"), 2000, 1, 5000)
        self._sync_mode = sync_mode
        self._save_config()
        return {
            "success": True,
            "data": {
                "max_items": self._max_items,
                "sync_mode": self._sync_mode,
            },
            "message": "工作台设置已保存",
        }

    def api_cache_export(self) -> Dict[str, Any]:
        cache = self.get_data("douban_tmdb_cache") or {}
        mappings: Dict[str, Dict[str, Any]] = {}
        if isinstance(cache, dict):
            for douban_id, item in cache.items():
                if not isinstance(item, dict) or item.get("failed"):
                    continue
                if item.get("source") == "github_seed":
                    continue
                if item.get("type") not in {"movie", "tv"} or not item.get("tmdb_id"):
                    continue
                try:
                    tmdb_id = int(item.get("tmdb_id"))
                except (TypeError, ValueError):
                    continue
                mappings[str(douban_id)] = {
                    "type": item.get("type"),
                    "tmdb_id": tmdb_id,
                    "title": item.get("title"),
                    "year": item.get("year"),
                }
        return {
            "success": True,
            "data": {
                "version": 1,
                "exported_at": self._now(),
                "description": "请将 mappings 合并到共享种子并通过 GitHub PR 提交审核。",
                "mappings": mappings,
                "mapping_count": len(mappings),
            },
        }

    def _load_douban_cache(self) -> Dict[str, dict]:
        """Merge reviewed bundled mappings with the user's persistent cache."""

        local = self.get_data("douban_tmdb_cache") or {}
        local = dict(local) if isinstance(local, dict) else {}
        seed_path = Path(__file__).resolve().parent / "assets" / "douban_tmdb_seed.json"
        try:
            payload = json.loads(seed_path.read_text(encoding="utf-8"))
            mappings = payload.get("mappings") if isinstance(payload, dict) else {}
            if isinstance(mappings, dict):
                for douban_id, mapping in mappings.items():
                    if not isinstance(mapping, dict):
                        continue
                    current = local.get(str(douban_id)) or {}
                    if str(mapping.get("type") or "") not in {"movie", "tv"}:
                        continue
                    try:
                        tmdb_id = int(mapping.get("tmdb_id"))
                    except (TypeError, ValueError):
                        continue
                    if not current or current.get("failed"):
                        local[str(douban_id)] = {
                            "type": str(mapping["type"]),
                            "tmdb_id": tmdb_id,
                            "title": mapping.get("title"),
                            "year": mapping.get("year"),
                            "poster_url": mapping.get("poster_url"),
                            "source": "github_seed",
                        }
        except FileNotFoundError:
            pass
        except Exception as exc:
            logger.warning(f"智能合集共享豆瓣映射种子读取失败：{exc}")
        return local

    def _build_preview(
        self,
        spec: CollectionSpec,
        context: Optional[Dict[str, Any]] = None,
        progress: Optional[Callable[[int, str], None]] = None,
    ) -> Dict[str, Any]:
        report = progress or (lambda _progress, _message: None)
        report(4, "正在读取 Emby 媒体库索引…")
        context = context or self._preview_context()
        report(12, "正在获取片单内容和简介…")
        resolved = context["resolver"].fetch(spec)
        title = (
            resolved.title
            if spec.use_source_title and resolved.title
            else spec.name or resolved.title or "未命名合集"
        )
        batch_resolutions = self._resolve_large_douban_batch(
            items=resolved.items,
            title_index=context["title_index"],
            douban_cache=context["douban_cache"],
            resolver=context["resolver"],
            progress=lambda completed, total: report(
                15 + round(50 * completed / max(1, total)),
                f"正在识别豆列条目 {completed} / {total}…",
            ),
        )
        rows: List[dict] = []
        total_items = len(resolved.items)
        for position, source_item in enumerate(resolved.items, start=1):
            resolution_key = str(source_item.douban_id or "")
            converted = batch_resolutions.get(resolution_key)
            match = self._find_title_match(source_item, context["title_index"])
            match_method = "title" if match else None
            if match:
                effective = self._media_ref_from_emby_match(source_item, match)
                if (
                    converted
                    and converted.tmdb_id == effective.tmdb_id
                    and converted.media_type == effective.media_type
                ):
                    effective = MediaRef(
                        media_type=effective.media_type,
                        tmdb_id=effective.tmdb_id,
                        douban_id=effective.douban_id,
                        title=source_item.title or converted.title,
                        year=source_item.year or converted.year,
                        poster_url=converted.poster_url or source_item.poster_url,
                        aliases=source_item.aliases,
                    )
            else:
                if resolution_key in batch_resolutions:
                    converted = batch_resolutions[resolution_key]
                else:
                    converted = self._resolve_media_ref(
                        source_item,
                        context["douban_cache"],
                        context["resolver"],
                    )
                effective = converted or source_item
            if effective.tmdb_id and effective.media_type in {"movie", "tv"}:
                tmdb_match = context["catalog"].get(
                    (str(effective.media_type), int(effective.tmdb_id))
                )
                if tmdb_match:
                    match = tmdb_match
                    match_method = "tmdb"
            if not match and effective.title:
                match = self._find_title_match(effective, context["title_index"])
                if match:
                    match_method = "title"

            media_type = effective.media_type if effective.media_type in {"movie", "tv"} else None
            row_key = f"{media_type or 'unknown'}:{effective.tmdb_id or effective.douban_id or position}"
            rows.append(
                {
                    "key": row_key,
                    "position": position,
                    "media_type": media_type,
                    "tmdb_id": effective.tmdb_id,
                    "douban_id": effective.douban_id,
                    "title": effective.title or source_item.title or f"豆瓣条目 {effective.douban_id}",
                    "year": effective.year or source_item.year,
                    "poster_url": effective.poster_url or source_item.poster_url,
                    "matched": bool(match),
                    "match_method": match_method,
                    "emby_item_id": match.get("id") if match else None,
                    "emby_name": match.get("name") if match else None,
                    "emby_year": match.get("year") if match else None,
                    "emby_url": context["emby"].get_item_url(match.get("id"))
                    if match
                    else None,
                    "missing_reason": None
                    if match
                    else "豆瓣 ID 与标题搜索均未能识别 TMDB"
                    if effective.douban_id and not effective.tmdb_id
                    else "Emby 媒体库中未找到匹配项目",
                }
            )
            if position == total_items or position % max(1, total_items // 100) == 0:
                report(
                    66 + round(30 * position / max(1, total_items)),
                    f"正在匹配 Emby {position} / {total_items}…",
                )

        self.save_data("douban_tmdb_cache", context["douban_cache"])
        matched = sum(bool(row.get("matched")) for row in rows)
        source_gap = max(0, int(resolved.reported_total or len(rows)) - len(rows))
        unavailable_count = source_gap if spec.source_type == "douban" else 0
        truncated_count = source_gap if spec.source_type != "douban" else 0
        if unavailable_count:
            logger.warning(
                f"智能合集来源标称 {resolved.reported_total} 个条目，"
                f"公开页面实际返回 {len(rows)} 个，另有 {unavailable_count} 个条目不可公开读取"
            )
        preview = {
            "preview_id": uuid.uuid4().hex,
            "title": title,
            "description": resolved.description or spec.description or "",
            "source": spec.source_type,
            "source_url": SourceResolver.source_url(spec),
            "spec": asdict(spec),
            "total_count": len(rows),
            "source_reported_total": resolved.reported_total,
            "unavailable_count": unavailable_count,
            "truncated_count": truncated_count,
            "movie_count": sum(row.get("media_type") == "movie" for row in rows),
            "tv_count": sum(row.get("media_type") == "tv" for row in rows),
            "matched_count": matched,
            "missing_count": len(rows) - matched,
            "unresolved_count": sum(
                not row.get("matched") and not row.get("tmdb_id")
                for row in rows
            ),
            "items": rows,
            "created_at": self._now(),
            "_created_monotonic": time.monotonic(),
        }
        self._store_preview(preview)
        report(99, "正在整理预览结果…")
        return preview

    @staticmethod
    def _media_ref_from_emby_match(
        source_item: MediaRef, match: Dict[str, Any]
    ) -> MediaRef:
        try:
            tmdb_id = int(match.get("tmdb_id"))
        except (TypeError, ValueError):
            tmdb_id = None
        return MediaRef(
            media_type=match.get("media_type") or source_item.media_type,
            tmdb_id=tmdb_id,
            douban_id=source_item.douban_id,
            title=source_item.title or match.get("name"),
            year=source_item.year or match.get("year"),
            poster_url=source_item.poster_url,
            aliases=source_item.aliases,
        )

    def _resolve_large_douban_batch(
        self,
        items: List[MediaRef],
        title_index: Dict[Tuple[str, Optional[int]], List[Dict[str, Any]]],
        douban_cache: Dict[str, dict],
        resolver: SourceResolver,
        progress: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Optional[MediaRef]]:
        """Resolve large mixed doulists concurrently without hammering Douban."""

        if len(items) < 100:
            return {}
        pending = [item for item in items if item.douban_id]
        if not pending:
            return {}

        def resolve(item: MediaRef) -> Tuple[str, Optional[MediaRef]]:
            key = str(item.douban_id)
            match = self._find_title_match(item, title_index)
            if match and match.get("tmdb_id") and match.get("media_type") in {"movie", "tv"}:
                cached = douban_cache.get(key) or {}
                if (
                    str(cached.get("tmdb_id") or "") == str(match.get("tmdb_id"))
                    and cached.get("type") == match.get("media_type")
                ):
                    return key, self._resolve_media_ref(
                        item, douban_cache, resolver, skip_douban_chain=True
                    )
                resolved = resolver.resolve_tmdb_by_id(
                    item,
                    str(match["media_type"]),
                    int(match["tmdb_id"]),
                )
                if not resolved:
                    resolved = MediaRef(
                        media_type=str(match["media_type"]),
                        tmdb_id=int(match["tmdb_id"]),
                        douban_id=item.douban_id,
                        title=item.title or match.get("name"),
                        year=item.year or match.get("year"),
                        poster_url=item.poster_url,
                        aliases=item.aliases,
                    )
                if resolved:
                    douban_cache[key] = {
                        "type": resolved.media_type,
                        "tmdb_id": resolved.tmdb_id,
                        "title": resolved.title,
                        "year": resolved.year,
                        "poster_url": resolved.poster_url,
                    }
                return key, resolved
            return key, self._resolve_media_ref(
                item, douban_cache, resolver, skip_douban_chain=True
            )

        workers = min(6, len(pending))
        results: Dict[str, Optional[MediaRef]] = {}
        with ThreadPoolExecutor(
            max_workers=workers,
            thread_name_prefix="SmartCollectionsTmdbFallback",
        ) as executor:
            futures = [executor.submit(resolve, item) for item in pending]
            for completed, future in enumerate(as_completed(futures), start=1):
                key, value = future.result()
                results[key] = value
                if progress:
                    progress(completed, len(futures))
        return results

    @staticmethod
    def _find_title_match(
        media_ref: MediaRef,
        title_index: Dict[Tuple[str, Optional[int]], List[Dict[str, Any]]],
    ) -> Optional[Dict[str, Any]]:
        values: List[str] = []
        for value in (media_ref.title, *media_ref.aliases):
            for candidate in SourceResolver.title_candidates(value):
                if candidate not in values:
                    values.append(candidate)
        season_hint = SourceResolver.has_season_marker(media_ref)
        for value in values:
            normalized = EmbyCollectionClient.normalize_title(value)
            if not normalized:
                continue
            candidates: Dict[str, Dict[str, Any]] = {}
            for (title, year), records in title_index.items():
                if title != normalized:
                    continue
                for record in records:
                    if (
                        media_ref.year
                        and year
                        and abs(int(media_ref.year) - int(year)) > 1
                        and not (season_hint and record.get("media_type") == "tv")
                    ):
                        continue
                    if (
                        media_ref.media_type in {"movie", "tv"}
                        and record.get("media_type") != media_ref.media_type
                    ):
                        continue
                    candidates[str(record.get("id"))] = record
            if len(candidates) == 1:
                return next(iter(candidates.values()))
        return None

    def _store_preview(self, preview: Dict[str, Any]) -> None:
        with self._preview_lock:
            cutoff = time.monotonic() - 1800
            self._preview_cache = {
                key: value
                for key, value in self._preview_cache.items()
                if float(value.get("_created_monotonic") or 0) >= cutoff
            }
            self._preview_cache[str(preview["preview_id"])] = preview
            while len(self._preview_cache) > 20:
                self._preview_cache.pop(next(iter(self._preview_cache)))

    def _get_preview(self, preview_id: str) -> Optional[Dict[str, Any]]:
        if not preview_id:
            return None
        with self._preview_lock:
            preview = self._preview_cache.get(preview_id)
            if not preview:
                return None
            if time.monotonic() - float(preview.get("_created_monotonic") or 0) > 1800:
                self._preview_cache.pop(preview_id, None)
                return None
            return preview

    @staticmethod
    def _source_key(source_spec: Dict[str, Any]) -> str:
        identity = dict(source_spec or {})
        for field in ("name", "mode", "description"):
            identity.pop(field, None)
        return json.dumps(identity, ensure_ascii=False, sort_keys=True)

    def _managed_record_for_spec(
        self, source_spec: Dict[str, Any], record_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        records = self._load_managed_collections()
        if record_id:
            match = next(
                (item for item in records if str(item.get("id")) == str(record_id)),
                None,
            )
            if match:
                return match
        source_key = self._source_key(source_spec)
        for item in records:
            if item.get("source_key") == source_key:
                return item
            saved = item.get("source_spec") or {}
            if (
                str(saved.get("source_type") or "")
                == str(source_spec.get("source_type") or "")
                and str(saved.get("list_id") or "")
                == str(source_spec.get("list_id") or "")
                and str(saved.get("url") or "") == str(source_spec.get("url") or "")
                and str(saved.get("template_id") or "")
                == str(source_spec.get("template_id") or "")
            ):
                return item
        return None

    @staticmethod
    def _safe_sync_mode(
        requested_mode: str,
        source_count: int,
        reported_total: Optional[int],
        matched_count: int,
        previous: Optional[Dict[str, Any]],
    ) -> Tuple[str, Optional[str]]:
        if requested_mode != "sync":
            return "append", None
        reasons: List[str] = []
        try:
            expected_total = int(reported_total) if reported_total is not None else None
        except (TypeError, ValueError):
            expected_total = None
        if expected_total is not None and source_count < expected_total:
            reasons.append(f"来源仅返回 {source_count}/{expected_total} 项")
        previous_total = int((previous or {}).get("total_count") or 0)
        previous_matched = int(
            (previous or {}).get("match_baseline")
            or (previous or {}).get("matched_count")
            or 0
        )
        if previous_total >= 20 and source_count < previous_total * 0.7:
            reasons.append(f"来源数量较上次 {previous_total} 项异常下降")
        if previous_matched >= 20 and matched_count < previous_matched * 0.7:
            reasons.append(f"匹配数量较上次 {previous_matched} 项异常下降")
        if reasons:
            return "append", "；".join(reasons)
        return "sync", None

    def _sync_preview_data(
        self,
        preview: Dict[str, Any],
        name: str,
        mode: str,
        selected_keys: Optional[List[str]] = None,
        record_id: Optional[str] = None,
        append_history: bool = True,
    ) -> Dict[str, Any]:
        if not name:
            raise ValueError("合集名称不能为空")
        selected = {str(key) for key in selected_keys or []}
        rows = [
            row
            for row in preview.get("items") or []
            if row.get("matched")
            and row.get("emby_item_id")
            and (not selected or str(row.get("key")) in selected)
        ]
        item_ids = list(dict.fromkeys(str(row["emby_item_id"]) for row in rows))
        requested_mode = mode if mode in {"sync", "append"} else self._sync_mode
        previous = self._managed_record_for_spec(
            preview.get("spec") or {}, record_id=record_id
        )
        effective_mode, guard_reason = self._safe_sync_mode(
            requested_mode=requested_mode,
            source_count=int(preview.get("total_count") or 0),
            reported_total=preview.get("source_reported_total"),
            matched_count=int(preview.get("matched_count") or len(item_ids)),
            previous=previous,
        )
        if guard_reason:
            logger.warning(
                f"智能合集 {name} 检测到来源或匹配结果不完整，"
                f"本次禁止删除并降级为追加：{guard_reason}"
            )
        sync_result = self._emby_client().sync_collection(
            name=name,
            item_ids=item_ids,
            mode=effective_mode,
            overview=preview.get("description") or None,
        )
        result = {
            "success": True,
            "name": name,
            "source": preview.get("source"),
            "source_items": preview.get("total_count", 0),
            "matched": len(item_ids),
            "resolved_matched": int(preview.get("matched_count") or len(item_ids)),
            "missing": max(0, int(preview.get("total_count") or 0) - len(item_ids)),
            "collection_id": sync_result.collection_id,
            "created": sync_result.created,
            "added": sync_result.added,
            "removed": sync_result.removed,
            "description": preview.get("description") or "",
            "requested_mode": requested_mode,
            "effective_mode": effective_mode,
            "sync_guard": guard_reason,
        }
        managed = self._upsert_managed_collection(
            preview=preview,
            result=result,
            mode=mode,
            record_id=record_id,
        )
        result["record_id"] = managed["id"]
        poster_needs_refresh = not managed.get("poster_source") or (
            managed.get("poster_source") == "auto"
            and int(managed.get("poster_version") or 0) < self._POSTER_VERSION
        )
        if self._auto_poster and poster_needs_refresh:
            try:
                self._generate_and_set_poster(managed, preview, source="auto")
                result["poster_generated"] = True
            except Exception as exc:
                result["poster_error"] = str(exc)
                logger.warning(f"智能合集 {name} 自动生成海报失败：{exc}")
        if append_history:
            self._append_history(
                {
                    "time": self._now(),
                    "server": self._emby_server,
                    "success": True,
                    "duration": 0,
                    "collections": [result],
                }
            )
        return result

    def _upsert_managed_collection(
        self,
        preview: Dict[str, Any],
        result: Dict[str, Any],
        mode: str,
        record_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        records = self._load_managed_collections()
        source_spec = preview.get("spec") or {}
        source_key = self._source_key(source_spec)
        current = self._managed_record_for_spec(source_spec, record_id=record_id)
        now = self._now()
        guarded = bool(result.get("sync_guard") and current)
        record = {
            "id": str(current.get("id")) if current else uuid.uuid4().hex,
            "name": result.get("name"),
            "source": preview.get("source"),
            "source_url": preview.get("source_url") or SourceResolver.source_url(
                self._spec_from_payload(source_spec)
            ),
            "source_spec": source_spec,
            "source_key": source_key,
            "mode": mode if mode in {"sync", "append"} else self._sync_mode,
            "emby_collection_id": result.get("collection_id"),
            "total_count": (
                current.get("total_count", 0)
                if guarded
                else result.get("source_items", 0)
            ),
            "matched_count": (
                current.get("matched_count", 0)
                if guarded
                else result.get("matched", 0)
            ),
            "match_baseline": (
                current.get("match_baseline", current.get("matched_count", 0))
                if guarded
                else result.get("resolved_matched", result.get("matched", 0))
            ),
            "missing_count": (
                current.get("missing_count", 0)
                if guarded
                else result.get("missing", 0)
            ),
            "last_attempt_total": result.get("source_items", 0),
            "last_attempt_matched": result.get("matched", 0),
            "last_sync_guard": result.get("sync_guard"),
            "description": preview.get("description") or "",
            "created_at": current.get("created_at") if current else now,
            "last_sync_at": now,
            "poster_source": current.get("poster_source") if current else None,
            "poster_updated_at": current.get("poster_updated_at") if current else None,
            "poster_version": current.get("poster_version") if current else None,
        }
        records = [item for item in records if str(item.get("id")) != record["id"]]
        records.insert(0, record)
        self.save_data("managed_collections", records[:100])
        return record

    def _generate_and_set_poster(
        self,
        record: Dict[str, Any],
        preview: Dict[str, Any],
        source: str = "auto",
    ) -> None:
        collection_id = str(record.get("emby_collection_id") or "")
        if not collection_id:
            raise ValueError("合集尚未同步到 Emby")
        poster_urls = [
            str(item.get("poster_url") or "")
            for item in preview.get("items") or []
            if item.get("poster_url")
        ]
        image = CollectionPosterBuilder.generate(
            str(record.get("name") or preview.get("title") or "智能合集"),
            poster_urls,
        )
        self._emby_client().set_collection_poster(collection_id, image)
        self._mark_collection_poster(str(record["id"]), source)

    def _mark_collection_poster(self, record_id: str, source: str) -> None:
        records = self._load_managed_collections()
        for item in records:
            if str(item.get("id")) == str(record_id):
                item["poster_source"] = source
                item["poster_updated_at"] = self._now()
                item["poster_version"] = (
                    self._POSTER_VERSION if source == "auto" else None
                )
                break
        self.save_data("managed_collections", records)

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

        # The interactive workbench is the primary source of truth in v0.3+.
        # Every managed collection keeps the source needed for scheduled resync.
        for record in self._load_managed_collections():
            try:
                source_spec = record.get("source_spec") or {}
                managed_spec = self._spec_from_payload(source_spec)
                managed_name = self._migrate_catalog_title(
                    str(source_spec.get("source_type") or ""),
                    str(source_spec.get("list_id") or ""),
                    str(record.get("name") or managed_spec.name or ""),
                )
                managed_spec.name = managed_name.strip() or None
                managed_spec.mode = str(record.get("mode") or managed_spec.mode or "").strip() or None
                managed_spec.use_source_title = False
                specs.append(managed_spec)
            except Exception as exc:
                logger.warning(
                    f"智能合集忽略无效的已管理合集来源 {record.get('name') or record.get('id')}：{exc}"
                )

        for list_key in self._popular_tmdb:
            definition = tmdb_catalog.get(list_key)
            if not definition:
                raise ValueError(f"未知的热门 TMDB 片单：{list_key}")
            specs.append(
                CollectionSpec(
                    source_type="tmdb_builtin",
                    name=definition["title"],
                    list_id=list_key,
                    use_source_title=True,
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
                    media_type=definition.get("media_type") or "movie",
                    use_source_title=True,
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
            library_catalog, title_index, duplicate_count = emby.build_library_catalog()
            logger.info(
                f"智能合集已读取 {len(library_catalog)} 个带 TMDB ID 的 Emby 媒体"
                f"，忽略重复项 {duplicate_count} 个"
            )
            resolver = SourceResolver(
                tmdb_token=self._tmdb_token,
                language=self._language,
                max_items=self._max_items,
                use_proxy=self._use_proxy,
            )
            douban_cache = self._load_douban_cache()

            for spec in specs:
                result = self._sync_one(
                    spec=spec,
                    resolver=resolver,
                    emby=emby,
                    library_catalog=library_catalog,
                    title_index=title_index,
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
        library_catalog: Dict[Tuple[str, int], Dict[str, Any]],
        title_index: Dict[Tuple[str, Optional[int]], List[Dict[str, Any]]],
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
            collection_name = (
                resolved.title
                if spec.use_source_title and resolved.title
                else spec.name or resolved.title
            )
            if not collection_name:
                raise ValueError("无法确定 Emby 合集名称，请在配置中填写 name")
            item_result["name"] = collection_name
            item_result["source_items"] = len(resolved.items)
            if resolved.reported_total and resolved.reported_total > len(resolved.items):
                logger.warning(
                    f"智能合集 {collection_name} 来源标称 {resolved.reported_total} 个条目，"
                    f"公开页面实际返回 {len(resolved.items)} 个"
                )

            batch_resolutions = self._resolve_large_douban_batch(
                items=resolved.items,
                title_index=title_index,
                douban_cache=douban_cache,
                resolver=resolver,
            )
            normalized: List[MediaRef] = []
            for source_item in resolved.items:
                resolution_key = str(source_item.douban_id or "")
                converted = batch_resolutions.get(resolution_key)
                title_match = self._find_title_match(source_item, title_index)
                if title_match:
                    matched_ref = self._media_ref_from_emby_match(
                        source_item, title_match
                    )
                    if (
                        converted
                        and converted.tmdb_id == matched_ref.tmdb_id
                        and converted.media_type == matched_ref.media_type
                    ):
                        matched_ref = MediaRef(
                            media_type=matched_ref.media_type,
                            tmdb_id=matched_ref.tmdb_id,
                            douban_id=matched_ref.douban_id,
                            title=source_item.title or converted.title,
                            year=source_item.year or converted.year,
                            poster_url=converted.poster_url or source_item.poster_url,
                            aliases=source_item.aliases,
                        )
                    normalized.append(matched_ref)
                    continue
                if resolution_key in batch_resolutions:
                    media_ref = batch_resolutions[resolution_key]
                else:
                    media_ref = self._resolve_media_ref(
                        source_item, douban_cache, resolver
                    )
                if media_ref or source_item.title:
                    normalized.append(media_ref or source_item)

            matched_ids = []
            matched_keys = set()
            for media_ref in normalized:
                key = None
                match = None
                if media_ref.tmdb_id and media_ref.media_type in {"movie", "tv"}:
                    key = (str(media_ref.media_type), int(media_ref.tmdb_id))
                    match = library_catalog.get(key)
                if not match and media_ref.title:
                    match = self._find_title_match(media_ref, title_index)
                emby_id = str(match.get("id")) if match else None
                dedupe_key = key or ("emby", emby_id)
                if not emby_id or dedupe_key in matched_keys:
                    continue
                matched_keys.add(dedupe_key)
                matched_ids.append(emby_id)

            item_result["matched"] = len(matched_ids)
            item_result["missing"] = max(
                0, item_result["source_items"] - len(matched_ids)
            )
            requested_mode = spec.mode or self._sync_mode
            previous = self._managed_record_for_spec(asdict(spec))
            effective_mode, guard_reason = self._safe_sync_mode(
                requested_mode=requested_mode,
                source_count=item_result["source_items"],
                reported_total=resolved.reported_total,
                matched_count=len(matched_ids),
                previous=previous,
            )
            if guard_reason:
                logger.warning(
                    f"智能合集 {collection_name} 检测到来源或匹配结果不完整，"
                    f"本次禁止删除并降级为追加：{guard_reason}"
                )
            sync_result = emby.sync_collection(
                name=collection_name,
                item_ids=matched_ids,
                mode=effective_mode,
                overview=resolved.description or spec.description or None,
            )
            item_result.update(
                {
                    "success": True,
                    "collection_id": sync_result.collection_id,
                    "created": sync_result.created,
                    "added": sync_result.added,
                    "removed": sync_result.removed,
                    "requested_mode": requested_mode,
                    "effective_mode": effective_mode,
                    "sync_guard": guard_reason,
                }
            )
            poster_preview = {
                "source": spec.source_type,
                "spec": asdict(spec),
                "title": collection_name,
                "description": resolved.description or spec.description or "",
                "items": [asdict(item) for item in normalized],
            }
            managed = self._upsert_managed_collection(
                preview=poster_preview,
                result=item_result,
                mode=spec.mode or self._sync_mode,
            )
            poster_needs_refresh = not managed.get("poster_source") or (
                managed.get("poster_source") == "auto"
                and int(managed.get("poster_version") or 0) < self._POSTER_VERSION
            )
            if self._auto_poster and poster_needs_refresh:
                try:
                    self._generate_and_set_poster(managed, poster_preview, source="auto")
                    item_result["poster_generated"] = True
                except Exception as exc:
                    item_result["poster_error"] = str(exc)
                    logger.warning(f"智能合集 {collection_name} 自动生成海报失败：{exc}")
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
        self,
        media_ref: MediaRef,
        douban_cache: Dict[str, dict],
        resolver: SourceResolver,
        skip_douban_chain: bool = False,
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
                title=cached.get("title") or media_ref.title,
                year=cached.get("year") or media_ref.year,
                poster_url=cached.get("poster_url") or media_ref.poster_url,
                aliases=media_ref.aliases,
            )
        if cached and cached.get("failed"):
            try:
                failed_age = time.time() - float(cached.get("failed_at") or 0)
            except (TypeError, ValueError):
                failed_age = self._DOUBAN_FAILURE_CACHE_TTL + 1
            if 0 <= failed_age < self._DOUBAN_FAILURE_CACHE_TTL:
                return None
            douban_cache.pop(str(media_ref.douban_id), None)

        tmdbinfo = None
        attempted_douban_chain = not skip_douban_chain and (
            time.monotonic()
            >= float(getattr(self, "_douban_chain_cooldown_until", 0) or 0)
        )
        if attempted_douban_chain:
            try:
                tmdbinfo = MediaChain().get_tmdbinfo_by_doubanid(
                    doubanid=str(media_ref.douban_id)
                )
            except Exception as exc:
                logger.warning(
                    f"智能合集 豆瓣 ID {media_ref.douban_id} 转换异常，改用标题搜索：{exc}"
                )
            if not tmdbinfo:
                self._douban_chain_cooldown_until = time.monotonic() + 60

        resolved: Optional[MediaRef] = None
        if tmdbinfo:
            try:
                tmdb_id = int(tmdbinfo.get("id") or tmdbinfo.get("tmdb_id"))
            except (TypeError, ValueError):
                tmdb_id = None

            raw_media_type = tmdbinfo.get("media_type") or tmdbinfo.get("type")
            if isinstance(raw_media_type, MediaType):
                media_type = (
                    "movie"
                    if raw_media_type == MediaType.MOVIE
                    else "tv"
                    if raw_media_type == MediaType.TV
                    else None
                )
            else:
                normalized_type = str(raw_media_type or "").strip().lower()
                if normalized_type in {"movie", "电影"}:
                    media_type = "movie"
                elif normalized_type in {"tv", "series", "电视剧", "剧集"}:
                    media_type = "tv"
                elif tmdbinfo.get("title") is not None:
                    media_type = "movie"
                elif tmdbinfo.get("name") is not None:
                    media_type = "tv"
                else:
                    media_type = None

            if tmdb_id and media_type:
                resolved = MediaRef(
                    media_type=media_type,
                    tmdb_id=tmdb_id,
                    douban_id=media_ref.douban_id,
                    title=tmdbinfo.get("title")
                    or tmdbinfo.get("name")
                    or media_ref.title,
                    year=SourceResolver._extract_year(
                        tmdbinfo.get("release_date")
                        or tmdbinfo.get("first_air_date")
                    )
                    or media_ref.year,
                    poster_url=SourceResolver._tmdb_poster(
                        tmdbinfo.get("poster_path")
                    )
                    or media_ref.poster_url,
                    aliases=media_ref.aliases,
                )

        if not resolved:
            resolved = resolver.resolve_tmdb_by_title(media_ref)
            if resolved:
                logger.info(
                    f"智能合集 豆瓣 ID {media_ref.douban_id} 已通过标题回退匹配 "
                    f"TMDB {resolved.media_type}:{resolved.tmdb_id}"
                )

        if not resolved:
            logger.warning(
                f"智能合集 豆瓣 ID {media_ref.douban_id} 未能匹配到 TMDB"
            )
            douban_cache[str(media_ref.douban_id)] = {
                "failed": True,
                "failed_at": time.time(),
                "title": media_ref.title,
                "year": media_ref.year,
                "reason": "tmdb_not_resolved",
            }
            return None
        douban_cache[str(media_ref.douban_id)] = {
            "type": resolved.media_type,
            "tmdb_id": resolved.tmdb_id,
            "title": resolved.title,
            "year": resolved.year,
            "poster_url": resolved.poster_url,
        }
        return resolved

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
                + (
                    f"（安全保护：{item.get('sync_guard')}，本次未删除）"
                    if item.get("sync_guard")
                    else ""
                )
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
                "show_sidebar_nav": self._show_sidebar_nav,
                "auto_poster": self._auto_poster,
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
                "managed_schedule_enabled": self._managed_schedule_enabled,
                "managed_schedule_cron": self._managed_schedule_cron,
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
