"""【通用】定义两队八窗口共用的数据模型与角色约束。"""

# 【通用】导入数据类工具以建立不可变配置对象。
from dataclasses import dataclass, field
# 【通用】导入枚举以限制角色和运行状态的合法取值。
from enum import StrEnum


# 【通用】定义每支队伍固定使用的四种角色。
class Role(StrEnum):
    """【通用】表示单个模拟器窗口在队伍中的职责。"""

    # 【队长】队长负责产生需要同步的主要操作。
    LEADER = "队长"
    # 【队员1】队员1可使用独立于队员2/3的任务策略。
    MEMBER_1 = "队员1"
    # 【队员2/3】队员2使用共用成员策略。
    MEMBER_2 = "队员2"
    # 【队员2/3】队员3与队员2复用同一套逻辑。
    MEMBER_3 = "队员3"

    # 【通用】判断当前角色是否使用队员2/3共用逻辑。
    @property
    def uses_shared_member_logic(self) -> bool:
        """【队员2/3】返回角色是否属于共享策略成员。"""

        # 【队员2/3】通过角色集合判断，避免复制两套业务实现。
        return self in {Role.MEMBER_2, Role.MEMBER_3}


# 【通用】定义模拟器实例的连接状态。
class DeviceStatus(StrEnum):
    """【通用】表示雷电实例当前可用性。"""

    # 【通用】实例尚未完成状态检查。
    UNKNOWN = "未知"
    # 【通用】实例在线且 ADB 可连接。
    ONLINE = "在线"
    # 【通用】实例存在但当前不可连接。
    OFFLINE = "离线"
    # 【通用】实例检查或控制过程发生错误。
    ERROR = "异常"


# 【通用】保存一个角色与雷电实例的绑定关系。
@dataclass(slots=True)
class DeviceBinding:
    """【通用】描述单个队伍角色对应的模拟器信息。"""

    # 【通用】记录队伍编号，固定使用 1 或 2。
    team_id: int
    # 【通用】记录当前窗口的队伍角色。
    role: Role
    # 【通用】记录 ldconsole 使用的实例索引。
    instance_index: int
    # 【通用】记录 ADB 设备序列号，例如 emulator-5554。
    adb_serial: str = ""
    # 【通用】保存最近一次检查得到的设备状态。
    status: DeviceStatus = DeviceStatus.UNKNOWN


# 【通用】保存一支完整四人队伍的绑定配置。
@dataclass(slots=True)
class TeamConfig:
    """【通用】保证每支队伍始终包含四个固定角色。"""

    # 【通用】记录队伍编号。
    team_id: int
    # 【通用】按角色保存四个模拟器绑定。
    bindings: dict[Role, DeviceBinding] = field(default_factory=dict)

    # 【通用】校验队伍编号和角色集合，避免产生缺员配置。
    def validate(self) -> None:
        """【通用】检查队伍结构是否符合两队四角色约束。"""

        # 【通用】拒绝固定范围以外的队伍编号。
        if self.team_id not in {1, 2}:
            # 【通用】向配置层报告明确的编号错误。
            raise ValueError("队伍编号只能是 1 或 2")
        # 【通用】取得系统要求的完整角色集合。
        required_roles = set(Role)
        # 【通用】比较实际角色与要求角色，防止遗漏或重复逻辑。
        if set(self.bindings) != required_roles:
            # 【通用】向调用方报告必须配置四个角色。
            raise ValueError("每支队伍必须包含队长、队员1、队员2、队员3")
