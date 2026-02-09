# Changelog

## [1.3.0] - 2026-02-09

### Added
- `kv_list` 命令和工具支持前缀搜索功能
- `/kv list [前缀]` 可按前缀过滤键值对
- LLM 工具 `kv_list` 新增 `prefix` 参数

### Changed
- 优化帮助信息

## [1.2.0] - 2026-02-08

### Added
- KV 存储功能，支持 `kv_read`、`kv_upsert`、`kv_list` 工具
- 用户命令 `/kv` 支持读取、写入、列出数据
- 支持 `生命30 经验20` 格式批量设置属性
- 骰子支持 `+key` 后缀，读取 KV 值作为修正值

### Changed
- 统一使用 JSON 文件存储数据

## [1.1.0] - 2026-02-08

### Added
- LLM tool 调用时返回字符串类型结果
- `hidden` 参数支持暗投模式

### Changed
- `llm_roll_dice` 返回类型从 `MessageEventResult` 改为 `str`
- 错误信息增加支持的表达式格式说明

## [1.0.0] - 2025-01-??
