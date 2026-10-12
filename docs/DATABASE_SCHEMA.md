# AI Coding Radar V1.0 数据库设计

使用 SQLite。

## account

保存平台账号。

字段：
- id
- platform
- account_name
- priority
- enabled

## quota

保存额度状态。

字段：
- id
- account_id
- cycle_type
- total
- used
- remaining
- reset_time
- update_time

## settings

保存用户设置。

字段：
- key
- value

设计原则：简单、够用、方便后续扩展。
