"""【通用】从外部 JSON 规则文件加载自动化任务步骤，支持队长独立策略与队员共享策略。"""

# 【通用】导入 JSON 以读取用户编写的任务规则。
import json
# 【通用】导入数据类以表示完整任务规则。
from dataclasses import dataclass, field
# 【通用】导入枚举以限制规则中可用的角色目标。
from enum import StrEnum
# 【通用】导入路径类型以处理规则文件位置。
from pathlib import Path
# 【通用】导入自动化步骤模型和类型以构造可执行任务。
from monsterbox.services.automation import AutomationStep, StepType


# 【通用】定义规则文件中可指定步骤执行的目标角色范围。
class RuleTarget(StrEnum):
    """【通用】控制一条规则在哪些角色上执行。"""

    # 【队长】仅队长执行（通常是识图判断步骤）。
    LEADER_ONLY = "仅队长"
    # 【队员1】仅队员1独立执行（使用专属策略）。
    MEMBER_1_ONLY = "仅队员1"
    # 【队员2/3】仅共享策略队员执行。
    SHARED_MEMBERS = "队员2_3"
    # 【队长/队员】所有在线角色同步执行。
    ALL = "全员同步"


# 【通用】保存一个完整任务规则包，包含各角色策略步骤。
@dataclass(slots=True)
class TaskRule:
    """【通用】组织队长独立步骤、队员1专属步骤和队员2/3共享步骤。"""

    # 【通用】规则名称，用于日志显示和选择。
    name: str
    # 【通用】规则描述，说明任务用途。
    description: str = ""
    # 【通用】队长专属步骤序列（如识图判断、界面导航）。
    leader_steps: list[AutomationStep] = field(default_factory=list)
    # 【通用】队员1专属步骤序列（与队员2/3策略不同时使用）。
    member1_steps: list[AutomationStep] = field(default_factory=list)
    # 【通用】队员2和队员3共享步骤序列。
    shared_member_steps: list[AutomationStep] = field(default_factory=list)
    # 【通用】队长点击同步：队长的坐标点击是否广播到队员。
    sync_leader_taps: bool = True
    # 【通用】步骤间默认等待秒数。
    default_wait: float = 0.5
    # 【通用】识图默认置信度阈值。
    default_threshold: float = 0.85
    # 【通用】单步骤默认重试次数。
    default_retries: int = 3


# 【通用】从JSON字典构造单个自动化步骤。
def _parse_step(raw_step: dict, default_threshold: float, default_retries: int, base_path: Path) -> AutomationStep:
    """【通用】解析单条步骤配置，支持坐标点击、识图点击和等待。"""

    # 【通用】读取步骤类型，缺失时抛出明确错误。
    step_type_raw = raw_step.get("type", "").strip()
    # 【通用】映射中文步骤类型到内部枚举。
    type_mapping = {
        "点击": StepType.TAP,
        "tap": StepType.TAP,
        "识图点击": StepType.FIND_AND_TAP,
        "find_tap": StepType.FIND_AND_TAP,
        "等待": StepType.WAIT,
        "wait": StepType.WAIT,
    }
    # 【通用】未知步骤类型拒绝加载。
    if step_type_raw not in type_mapping:
        # 【通用】提示用户合法的步骤类型选项。
        raise ValueError(f"不支持的步骤类型：{step_type_raw}，可选：点击/识图点击/等待")
    step_type = type_mapping[step_type_raw]

    # 【通用】等待步骤只需读取秒数。
    if step_type is StepType.WAIT:
        # 【通用】等待时间默认1秒，允许配置覆盖。
        wait_seconds = float(raw_step.get("seconds", 1.0))
        # 【通用】返回等待步骤，其他字段使用默认值。
        return AutomationStep(step_type=step_type, wait_seconds=wait_seconds)

    # 【通用】点击步骤读取坐标。
    x = int(raw_step.get("x", 0))
    y = int(raw_step.get("y", 0))

    # 【通用】识图点击需要加载模板图片。
    template_png = b""
    threshold = float(raw_step.get("threshold", default_threshold))
    if step_type is StepType.FIND_AND_TAP:
        # 【通用】模板路径相对于规则文件所在目录。
        template_path = raw_step.get("template", "").strip()
        if not template_path:
            # 【通用】识图点击必须指定模板图片。
            raise ValueError("识图点击步骤必须配置 template 图片路径")
        # 【通用】组合为绝对路径并检查文件存在。
        full_template_path = (base_path / template_path).resolve() if not Path(template_path).is_absolute() else Path(template_path)
        if not full_template_path.is_file():
            # 【通用】提示用户模板路径相对于规则文件。
            raise FileNotFoundError(f"找不到识图模板：{template_path}（相对于规则文件目录）")
        # 【通用】读取PNG字节供内存匹配使用。
        template_png = full_template_path.read_bytes()

    # 【通用】单步骤重试次数，使用规则默认值。
    retries = int(raw_step.get("retries", default_retries))

    # 【通用】返回构造完成的步骤对象。
    return AutomationStep(
        step_type=step_type,
        x=x,
        y=y,
        wait_seconds=0,
        template_png=template_png,
        threshold=threshold,
        retries=retries,
    )


# 【通用】从JSON文件加载单条任务规则。
def load_task_rule(path: Path) -> TaskRule:
    """【通用】读取规则JSON文件并构造可执行任务配置。"""

    # 【通用】规则文件不存在时提前报错。
    if not path.is_file():
        # 【通用】明确告知用户找不到哪个规则文件。
        raise FileNotFoundError(f"找不到规则文件：{path}")

    # 【通用】使用UTF-8读取支持中文步骤描述。
    raw = json.loads(path.read_text(encoding="utf-8"))
    # 【通用】规则文件所在目录用于解析相对模板路径。
    base_path = path.parent

    # 【通用】读取基本元数据。
    name = raw.get("name", path.stem)
    description = raw.get("description", "")
    # 【通用】读取全局默认参数。
    default_wait = float(raw.get("default_wait", 0.5))
    default_threshold = float(raw.get("default_threshold", 0.85))
    default_retries = int(raw.get("default_retries", 3))
    # 【通用】是否启用队长点击同步广播。
    sync_leader_taps = bool(raw.get("sync_leader_taps", True))

    # 【通用】解析各角色独立步骤序列。
    leader_steps_raw = raw.get("leader_steps", [])
    member1_steps_raw = raw.get("member1_steps", [])
    shared_member_steps_raw = raw.get("shared_member_steps", raw.get("member_steps", []))

    # 【通用】逐步骤解析队长策略。
    leader_steps = [_parse_step(step, default_threshold, default_retries, base_path) for step in leader_steps_raw]
    # 【通用】逐步骤解析队员1专属策略。
    member1_steps = [_parse_step(step, default_threshold, default_retries, base_path) for step in member1_steps_raw]
    # 【通用】逐步骤解析队员2/3共享策略。
    shared_member_steps = [_parse_step(step, default_threshold, default_retries, base_path) for step in shared_member_steps_raw]

    # 【通用】如果没有配置队员独立步骤，且配置了通用steps则复用。
    all_steps_raw = raw.get("steps", [])
    if all_steps_raw and not leader_steps and not member1_steps and not shared_member_steps:
        # 【通用】通用步骤所有角色使用相同序列。
        common_steps = [_parse_step(step, default_threshold, default_retries, base_path) for step in all_steps_raw]
        leader_steps = list(common_steps)
        member1_steps = list(common_steps)
        shared_member_steps = list(common_steps)

    # 【通用】返回构造完成的任务规则对象。
    return TaskRule(
        name=name,
        description=description,
        leader_steps=leader_steps,
        member1_steps=member1_steps,
        shared_member_steps=shared_member_steps,
        sync_leader_taps=sync_leader_taps,
        default_wait=default_wait,
        default_threshold=default_threshold,
        default_retries=default_retries,
    )


# 【通用】扫描目录下所有.json规则文件。
def scan_rule_directory(directory: Path) -> list[Path]:
    """【通用】返回目录中所有JSON规则文件路径，按文件名排序。"""

    # 【通用】目录不存在时返回空列表。
    if not directory.is_dir():
        # 【通用】不创建目录，由调用方决定如何处理。
        return []
    # 【通用】查找所有.json文件并按名称排序。
    rule_files = sorted(directory.glob("*.json"))
    # 【通用】排除settings.json等配置文件，仅加载任务规则。
    return [f for f in rule_files if f.name.lower() != "settings.json"]


# 【通用】创建示例规则文件作为模板参考。
def create_example_rule(path: Path) -> None:
    """【通用】生成注释清晰的示例规则，供用户参考编写。"""

    # 【通用】示例规则结构，使用纯坐标和等待步骤，无需外部图片即可测试。
    example = {
        "name": "示例任务",
        "description": "这是一个示例规则，展示点击和等待步骤；识图点击需自行配置template图片路径",
        "sync_leader_taps": True,
        "default_wait": 0.8,
        "default_threshold": 0.9,
        "default_retries": 3,
        "leader_steps": [
            {"type": "等待", "seconds": 1.0},
            {"type": "点击", "x": 540, "y": 1200, "retries": 3},
            {"type": "等待", "seconds": 0.5},
            {"type": "点击", "x": 540, "y": 800},
        ],
        "member1_steps": [
            {"type": "等待", "seconds": 1.5},
            {"type": "点击", "x": 540, "y": 1200},
        ],
        "shared_member_steps": [
            {"type": "等待", "seconds": 2.0},
            {"type": "点击", "x": 540, "y": 1200},
        ],
    }
    # 【通用】确保父目录存在。
    path.parent.mkdir(parents=True, exist_ok=True)
    # 【通用】以易读格式保存示例。
    path.write_text(json.dumps(example, ensure_ascii=False, indent=2), encoding="utf-8")
