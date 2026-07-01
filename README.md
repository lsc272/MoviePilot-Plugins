# SmartCollections（智能合集）

MoviePilot V2 插件：从公开的 TMDB List、豆瓣豆列或内联模板读取电影和剧集，按 TMDB ID 精确匹配 Emby 媒体库中已有项目，并创建或更新 Emby 合集。

## 功能

- TMDB List：支持 TMDB v4 混合片单；未配置 v4 Token 时回退到 MoviePilot 的 TMDB v3 API Key。
- 豆瓣豆列：读取公开豆列中的影视条目，通过 MoviePilot 媒体识别链转换为 TMDB ID，并缓存识别结果。
- 自定义模板：直接使用 `movie:TMDBID` 与 `tv:TMDBID` 定义合集。
- Emby 精确匹配：只处理媒体库中已存在且具有相同 TMDB ID 的电影和剧集。
- 两种更新模式：`sync` 会增删成员，使合集与片单一致；`append` 只添加新成员。
- 支持 Cron 定时同步、立即运行、远程命令、运行记录和通知。
- 安全保护：来源异常或零匹配时不会创建空合集，也不会清空已有合集。

## 安装

本插件是 V2 专用插件，目录应保持为：

```text
plugins.v2/smartcollections/
```

将本仓库加入 MoviePilot 插件市场，或把插件目录放入 MoviePilot 的本地插件仓库后安装。插件会直接复用 MoviePilot 中已经启用的 Emby 配置，不需要再次填写 Emby 地址和 API Key。

## 配置示例

在“合集定义（JSON）”中填写一个数组：

```json
[
  {
    "name": "我的 TMDB 片单",
    "type": "tmdb",
    "url": "https://www.themoviedb.org/list/123456"
  },
  {
    "name": "豆瓣高分电影",
    "type": "douban",
    "url": "https://www.douban.com/doulist/240962/",
    "mode": "append"
  },
  {
    "name": "星战与权游",
    "type": "template",
    "items": [
      "movie:11",
      "movie:1891",
      "tv:1399"
    ]
  }
]
```

每个合集支持以下字段：

- `name`：Emby 合集名称。TMDB、豆瓣来源可省略，此时使用公开片单标题。
- `type`：`tmdb`、`douban` 或 `template`。
- `url` / `list_id`：TMDB List 或豆瓣豆列地址/ID。
- `items`：模板条目数组，格式为 `movie:TMDBID` 或 `tv:TMDBID`；也可使用 `{"type":"movie","tmdb_id":11}`。
- `mode`：可选，覆盖全局模式；`sync` 或 `append`。
- `enabled`：可选，设为 `false` 可暂时跳过该合集。

TMDB v4 Read Access Token 建议填写，以支持新版混合片单中的电影和剧集。Token 只保存在 MoviePilot 插件配置中。

## 使用

- 保存配置时勾选“立即运行一次”，插件会在数秒后执行。
- 启用定时同步后按 Cron 表达式运行，默认每天 04:00。
- 远程命令：`/smartcollections_sync`。
- 插件详情页会显示最近十次记录，数据层保留最近二十次记录。

首次同步大型豆列需要逐条识别豆瓣 ID，速度会较慢；后续运行会使用插件缓存。

## 说明

This product uses the TMDB API but is not endorsed or certified by TMDB.

豆瓣网页结构和访问策略可能变化。插件仅支持无需登录即可访问的公开豆列，并遵守配置的最大读取条目数。
