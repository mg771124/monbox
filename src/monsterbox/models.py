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

    # 【通用】返回该身份对应的游戏逻辑说明，供界面提示用户。
    @property
    def logic_description(self) -> str:
        """【通用】说明四个身份的游戏逻辑差异，右键分配身份时展示。"""

        # 【队长】队长使用独立的识图判断与界面导航逻辑。
        if self is Role.LEADER:
            # 【队长】指向规则文件中的 leader_steps。
            return "队长逻辑：执行 leader_steps（识图判断、界面导航、发起同步操作）"
        # 【队员1】队员1使用与共享队员不同的独立队员逻辑。
        if self is Role.MEMBER_1:
            # 【队员1】指向规则文件中的 member1_steps。
            return "队员1逻辑：执行 member1_steps（独立队员策略，跟随队长指令）"
        # 【队员2/3】队员2与队员3复用同一套共享队员逻辑。
        return "队员2/3逻辑：执行 shared_member_steps（共享队员策略，队友2与3复用同一实现）"


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
    # 【通用】记录 ldconsole 使用的实例索引，-1 表示该身份尚未分配窗口。
    instance_index: int
    # 【通用】记录 ADB 设备序列号，例如 emulator-5554。
    adb_serial: str = ""
    # 【通用】保存最近一次检查得到的设备状态。
    status: DeviceStatus = DeviceStatus.UNKNOWN

    # 【通用】判断该身份是否已经绑定真实实例。
    @property
    def is_assigned(self) -> bool:
        """【通用】空位身份不参与表格显示、状态查询和任务执行。"""

        # 【通用】只有非负索引才对应雷电模拟器中的真实实例。
        return self.instance_index >= 0


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


# 【通用】在现有队伍配置中查找某个雷电实例被分配到的队伍和身份。
def find_assignment(teams: tuple[TeamConfig, ...], instance_index: int) -> tuple[int, Role] | None:
    """【通用】返回实例所属的队伍编号与身份，未分配时返回空值。"""

    # 【通用】空位占位索引不代表真实实例，直接返回未分配。
    if instance_index < 0:
        # 【通用】避免把空位误判成已分配窗口。
        return None
    # 【通用】依次检查两支队伍的绑定。
    for team in teams:
        # 【通用】依次检查队长、队员1以及共用逻辑的队员2/3。
        for role, binding in team.bindings.items():
            # 【通用】只有真实分配过的绑定才参与匹配。
            if binding.is_assigned and binding.instance_index == instance_index:
                # 【通用】返回队伍编号与身份供界面显示和右键菜单打勾。
                return team.team_id, role
    # 【通用】没有任何身份占用该实例时返回空值。
    return None


# 【通用】收集各实例当前的 ADB 序列号与状态，重新分配身份时沿用。
def _collect_connection_states(teams: tuple[TeamConfig, ...]) -> dict[int, tuple[str, DeviceStatus]]:
    """【通用】避免调整身份后丢失已经探测到的设备连接信息。"""

    # 【通用】按实例索引保存序列号和状态。
    states: dict[int, tuple[str, DeviceStatus]] = {}
    # 【通用】遍历全部队伍角色。
    for team in teams:
        # 【通用】逐个读取绑定中的连接信息。
        for binding in team.bindings.values():
            # 【通用】空位没有连接信息，不需要保存。
            if binding.is_assigned:
                # 【通用】记录该实例的连接信息供重建绑定使用。
                states[binding.instance_index] = (binding.adb_serial, binding.status)
    # 【通用】返回连接信息快照。
    return states


# 【通用】按照槽位计划重建两支队伍，保证四个身份始终齐全。
def _rebuild_teams(
    teams: tuple[TeamConfig, ...],
    planned_indexes: dict[tuple[int, Role], int],
    connection_states: dict[int, tuple[str, DeviceStatus]],
) -> tuple[TeamConfig, ...]:
    """【通用】建立全新的绑定对象，避免旧任务引用被就地修改。"""

    # 【通用】准备新的两支队伍配置。
    rebuilt: list[TeamConfig] = []
    # 【通用】逐队重建绑定。
    for team in teams:
        # 【通用】准备四个固定身份的绑定映射。
        bindings: dict[Role, DeviceBinding] = {}
        # 【通用】按固定枚举顺序建立身份，队员2/3仍复用同一模型。
        for role in Role:
            # 【通用】读取该身份在计划中的新实例索引。
            index = planned_indexes[(team.team_id, role)]
            # 【通用】沿用该实例已有的连接信息，空位使用默认值。
            serial, status = connection_states.get(index, ("", DeviceStatus.UNKNOWN))
            # 【通用】建立新的绑定对象。
            bindings[role] = DeviceBinding(team.team_id, role, index, serial, status)
        # 【通用】保存重建后的队伍。
        rebuilt.append(TeamConfig(team.team_id, bindings))
    # 【通用】返回新的不可变队伍序列。
    return tuple(rebuilt)


# 【通用】把实例分配到指定队伍身份，实现列表右键的“第几队 + 什么身份”设置。
def reassign_instance(teams: tuple[TeamConfig, ...], instance_index: int, team_id: int, role: Role) -> tuple[TeamConfig, ...]:
    """【通用】目标身份为空位时填入，已被占用时两个实例互换位置。"""

    # 【通用】拒绝空位占位索引，避免把空位当作可分配的窗口。
    if instance_index < 0:
        # 【通用】向界面报告明确的参数错误。
        raise ValueError("实例索引不能为负数")
    # 【通用】拒绝固定范围以外的队伍编号。
    if team_id not in {1, 2}:
        # 【通用】向界面报告明确的队伍编号错误。
        raise ValueError("队伍编号只能是 1 或 2")
    # 【通用】定位目标队伍，缺失时报告配置错误。
    target_team = next((team for team in teams if team.team_id == team_id), None)
    # 【通用】目标队伍不存在时终止分配。
    if target_team is None:
        # 【通用】提示队伍编号只能是 1 或 2。
        raise ValueError("队伍编号只能是 1 或 2")
    # 【通用】查询该实例当前所属的队伍身份。
    current = find_assignment(teams, instance_index)
    # 【通用】实例已经在该身份上时不做任何修改。
    if current == (team_id, role):
        # 【通用】返回原配置供界面保持幂等。
        return tuple(teams)
    # 【通用】读取目标身份当前占用的实例索引，-1 表示空位。
    displaced_index = target_team.bindings[role].instance_index
    # 【通用】记录各实例的连接信息，交换时不会丢失。
    connection_states = _collect_connection_states(teams)
    # 【通用】按身份计算新的实例索引。
    planned_indexes: dict[tuple[int, Role], int] = {}
    # 【通用】遍历全部队伍身份。
    for team in teams:
        # 【通用】逐个身份计算新索引。
        for slot_role, binding in team.bindings.items():
            # 【通用】默认保持原有索引。
            index = binding.instance_index
            # 【通用】目标身份填入被分配的实例。
            if team.team_id == team_id and slot_role is role:
                # 【通用】把实例写入被选中的队伍身份。
                index = instance_index
            # 【通用】实例原来的身份让出槽位：有人被顶替时交换，否则变为空位。
            elif current is not None and (team.team_id, slot_role) == current:
                # 【通用】写入被顶替实例的索引，-1 表示空位。
                index = displaced_index
            # 【通用】保存该身份的新索引。
            planned_indexes[(team.team_id, slot_role)] = index
    # 【通用】返回重建后的队伍配置。
    return _rebuild_teams(teams, planned_indexes, connection_states)


# 【通用】取消实例的队伍身份，让对应身份重新显示为空位。
def clear_instance_assignment(teams: tuple[TeamConfig, ...], instance_index: int) -> tuple[TeamConfig, ...]:
    """【通用】未分配的实例在右键菜单中执行取消分配时使用。"""

    # 【通用】查询该实例当前的身份。
    current = find_assignment(teams, instance_index)
    # 【通用】本来就没有身份时保持原配置。
    if current is None:
        # 【通用】返回原配置供界面保持幂等。
        return tuple(teams)
    # 【通用】把所有该实例占用的身份改为空位，其他身份保持不变。
    planned_indexes = {
        # 【通用】以队伍编号和身份作为槽位标识。
        (team.team_id, slot_role): (-1 if binding.instance_index == instance_index else binding.instance_index)
        # 【通用】遍历全部队伍身份。
        for team in teams
        # 【通用】逐个身份计算是否为空位。
        for slot_role, binding in team.bindings.items()
    }
    # 【通用】返回重建后的队伍配置，连接信息随之丢弃。
    return _rebuild_teams(teams, planned_indexes, _collect_connection_states(teams))
