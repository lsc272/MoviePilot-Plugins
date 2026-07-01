# SmartCollections（智能合集）

MoviePilot V2 插件：从热门 TMDB 片单、热门豆瓣豆列或手动输入的公开片单链接读取电影和剧集，按 TMDB ID 精确匹配 Emby 媒体库中已有项目，并创建或更新 Emby 合集。

当前版本：v0.3.0

## 功能

- Vue 智能合集工作台：原生集成在 MoviePilot 插件详情页，并可显示独立侧栏入口。
- 热门 TMDB 片单：支持热门/高分榜单，以及奥斯卡、金球奖、IMDb、豆瓣 Top 250、Letterboxd、Criterion 等公开片单。
- 热门豆瓣豆列：直接浏览并选择高分电影、类型精选、冷门佳片和高分动画豆列。
- 手动链接：粘贴公开 TMDB List 或豆瓣豆列链接，自动读取合集名称。
- TMDB List：支持 TMDB v4 混合片单；未配置 v4 Token 时回退到 MoviePilot 的 TMDB v3 API Key。
- 豆瓣豆列：通过 MoviePilot 官方 `MediaChain.get_tmdbinfo_by_doubanid` 转换为 TMDB ID，兼容电影和剧集，并缓存识别结果。
- 匹配预览：同步前逐项显示海报、片名、年份、类型、TMDB ID、Emby 匹配和缺失原因。
- Emby 匹配：优先按媒体类型与 TMDB ID 精确匹配，必要时以唯一的标题和年份结果兜底。
- 模板：可将当前预览保存为模板，并通过 JSON 导入或导出。
- 批量同步：多选公开片单或豆列后，一次创建或更新多个 Emby 合集。
- 合集管理：记录由插件管理的合集，支持重新同步或同时删除 Emby 合集。
- 两种更新模式：`sync` 会增删成员，使合集与片单一致；`append` 只添加新成员。
- 支持 Cron 定时同步、立即运行、远程命令、运行记录和通知。
- 安全保护：来源异常或零匹配时不会创建空合集，也不会清空已有合集。

## 安装

本插件是 V2 专用插件，目录应保持为：

```text
plugins.v2/smartcollections/
```

将本仓库加入 MoviePilot 插件市场，或把插件目录放入 MoviePilot 的本地插件仓库后安装。插件会直接复用 MoviePilot 中已经启用的 Emby 配置，不需要再次填写 Emby 地址和 API Key。

## 配置来源

智能合集工作台提供三种来源，可以同时使用：

1. 在“热门 TMDB 片单”中多选需要的电影或剧集榜单。
2. 在“热门豆瓣豆列”中多选需要的公开豆列。
3. 在“手动添加”中每行粘贴一个链接，例如：

```text
https://www.themoviedb.org/list/5292-tmdb-watchlist
https://www.douban.com/doulist/240962/
```

插件会先展示匹配和缺失结果；确认合集名称与条目选择后再同步到 Emby，不需要填写配置 JSON。

TMDB v4 Read Access Token 建议填写，以支持新版混合片单中的电影和剧集。Token 只保存在 MoviePilot 插件配置中。

## 使用

- 保存配置时勾选“立即运行一次”，插件会在数秒后执行。
- 启用定时同步后按 Cron 表达式运行，默认每天 04:00。
- 远程命令：`/smartcollections_sync`。
- 插件详情页包含片单目录、模板和已同步合集三个工作区；同步记录保留最近二十次。

首次同步大型豆列需要逐条识别豆瓣 ID，速度会较慢；后续运行会使用插件缓存。

## 说明

This product uses the TMDB API but is not endorsed or certified by TMDB.

豆瓣网页结构和访问策略可能变化。插件仅支持无需登录即可访问的公开豆列，并遵守配置的最大读取条目数。
