# AI Coding Radar
## AI 编程资源驾驶舱 V1.0 开发任务书

## 项目目标
构建 Windows 本地桌面工具，统一查看火山 Coding Plan、Zcode、Codex 多账号额度状态。

核心能力：
- 5小时额度查看
- 7天额度查看
- 月额度查看
- 恢复倒计时
- Codex 多账号管理
- 资源状态推荐
- 本地安全存储

## V1.0范围

支持平台：
- 火山引擎 Coding Plan
- Zcode
- Codex

暂不实现：
- 自动调用AI
- 自动切换账号
- 云端同步
- 上传用户数据

## 技术方向

- Windows桌面应用
- Python + PySide6
- SQLite本地数据库
- Provider插件架构

## Provider设计

统一接口：

- get_account()
- get_quota()
- get_reset_time()
- get_status()

## 数据模型

Account:
- id
- platform
- account_name
- priority
- enabled

Quota:
- account_id
- cycle_type
- total
- used
- remaining
- reset_time
- update_time

## 开发原则

先完成可用版本，再扩展智能调度。

稳定性、安全性优先。
