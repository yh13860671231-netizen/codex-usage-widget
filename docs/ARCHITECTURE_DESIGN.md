# AI Coding Radar V1.0 架构设计

## 定位
小型 Windows 桌面工具，目标是快速查看 AI 编程资源状态。

## 架构

UI层
↓
业务服务层
↓
Provider适配层
↓
SQLite本地数据层

## 模块

UI：展示平台、额度、倒计时、提醒。

Service：负责额度计算、状态判断、刷新任务。

Provider：每个平台独立适配：
- volcano
- zcode
- codex

Storage：保存账号配置、状态缓存、用户设置。

## 原则

第一版优先可用，不追求复杂架构。保持后续扩展能力即可。
