# 任务规则编写说明

本目录用于存放 MonsterBox 自动化任务规则，以 JSON 格式编写。

## 规则文件结构

```json
{
  "name": "任务名称",
  "description": "任务描述说明",
  "sync_leader_taps": true,
  "default_wait": 0.8,
  "default_threshold": 0.9,
  "default_retries": 3,
  "leader_steps": [...],
  "member1_steps": [...],
  "shared_member_steps": [...]
}
```

## 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 规则名称，显示在下拉选择框 |
| `description` | string | 任务描述，日志中显示 |
| `sync_leader_taps` | bool | 队长点击是否同步到队员（预留功能） |
| `default_wait` | float | 默认步骤间等待秒数 |
| `default_threshold` | float | 识图点击默认匹配置信度（0-1） |
| `default_retries` | int | 单步骤失败默认重试次数 |

## 角色步骤策略

- **leader_steps**: 队长独立执行的步骤（如识图判断、界面导航）
- **member1_steps**: 队员1独立步骤（可与其他队员策略不同）
- **shared_member_steps**: 队员2和队员3共享执行的步骤
- **steps** (可选): 如果所有角色使用相同步骤，可以统一配置在此

## 步骤类型

### 1. 等待 (wait)
```json
{"type": "等待", "seconds": 1.5}
```

### 2. 坐标点击 (tap)
```json
{"type": "点击", "x": 540, "y": 1200, "retries": 3}
```

### 3. 识图点击 (find_tap)
```json
{"type": "识图点击", "template": "images/button.png", "threshold": 0.9, "retries": 10}
```

- `template`: 模板图片路径，相对于规则文件所在目录
- `threshold`: 匹配置信度阈值，越高越严格

## 参考业界主流中控做法

本框架参考了以下开源/商业方案的架构：

1. **ThreadPoolExecutor 并行执行** - 参考网上 ADB 集群方案，多设备命令并行发送减少延迟
2. **角色策略分离** - 队长/队员1/共享成员三级策略，类似触动精灵/按键精灵的多端控制
3. **JSON 规则热加载** - 无需修改代码，编写JSON即可定义任务，参考各种脚本IDE的配置驱动
4. **独立重试机制** - 每个步骤有独立重试计数，失败立即终止避免误操作
5. **自动ADB发现** - 通过 ldconsole adb 命令自动获取序列号，无需手动配置
