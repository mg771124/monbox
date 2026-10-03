"""【通用】验证固定两队四角色数据约束以及右键指定队伍身份的逻辑。"""

# 【通用】导入 pytest 验证异常。
import pytest
# 【通用】导入待测试模型和队伍分配函数。
from monsterbox.models import (
    DeviceBinding,
    DeviceStatus,
    Role,
    TeamConfig,
    clear_instance_assignment,
    find_assignment,
    reassign_instance,
)


# 【通用】建立两队八窗口的默认配置，供身份分配测试复用。
def _build_teams() -> tuple[TeamConfig, ...]:
    """【通用】按索引 0 至 7 顺序建立第 1 队与第 2 队。"""

    # 【通用】准备保存两支队伍。
    teams: list[TeamConfig] = []
    # 【通用】逐队建立四个身份绑定。
    for team_id in (1, 2):
        # 【通用】按角色顺序分配连续索引。
        bindings = {
            # 【通用】队员2与队员3由同一循环生成，保持共享逻辑。
            role: DeviceBinding(team_id, role, (team_id - 1) * 4 + offset, "emulator-test", DeviceStatus.ONLINE)
            # 【通用】遍历固定四角色。
            for offset, role in enumerate(Role)
        }
        # 【通用】保存该队伍配置。
        teams.append(TeamConfig(team_id, bindings))
    # 【通用】返回可继续分配的队伍序列。
    return tuple(teams)


# 【通用】验证队员2和队员3始终共用策略标记。
def test_member_two_and_three_share_logic() -> None:
    """【队员2/3】确认共享逻辑不会分裂成重复实现。"""

    # 【队员2/3】队员2必须启用共享逻辑。
    assert Role.MEMBER_2.uses_shared_member_logic
    # 【队员2/3】队员3必须启用同一个共享逻辑。
    assert Role.MEMBER_3.uses_shared_member_logic
    # 【队员1】队员1保留独立角色逻辑。
    assert not Role.MEMBER_1.uses_shared_member_logic


# 【通用】验证缺少角色的队伍配置会被拒绝。
def test_team_requires_all_roles() -> None:
    """【通用】禁止缺员配置进入中控台。"""

    # 【通用】仅建立队长绑定以模拟错误配置。
    team = TeamConfig(1, {Role.LEADER: DeviceBinding(1, Role.LEADER, 0)})
    # 【通用】校验应抛出明确配置错误。
    with pytest.raises(ValueError, match="每支队伍必须包含"):
        # 【通用】执行队伍结构校验。
        team.validate()


# 【通用】验证四个身份的游戏逻辑说明互不相同。
def test_role_logic_descriptions_cover_gameplay_differences() -> None:
    """【通用】队长、队员1与共享队员必须使用不同的规则步骤。"""

    # 【队长】队长说明必须指向 leader_steps。
    assert "leader_steps" in Role.LEADER.logic_description
    # 【队员1】队员1说明必须指向 member1_steps。
    assert "member1_steps" in Role.MEMBER_1.logic_description
    # 【队员2/3】队员2与队员3共用同一份说明。
    assert Role.MEMBER_2.logic_description == Role.MEMBER_3.logic_description
    # 【通用】三类游戏逻辑说明不能互相重复。
    assert len({Role.LEADER.logic_description, Role.MEMBER_1.logic_description, Role.MEMBER_2.logic_description}) == 3


# 【通用】验证空位身份不参与实例匹配。
def test_find_assignment_ignores_empty_slots() -> None:
    """【通用】取消分配后实例不再属于任何队伍身份。"""

    # 【通用】把第 1 队队长使用的实例 0 取消分配。
    teams = clear_instance_assignment(_build_teams(), 0)
    # 【通用】空出的身份使用 -1 占位。
    assert teams[0].bindings[Role.LEADER].instance_index == -1
    # 【通用】空位不再占用实例 0。
    assert find_assignment(teams, 0) is None
    # 【通用】其他实例身份保持不变。
    assert find_assignment(teams, 5) == (2, Role.MEMBER_1)


# 【通用】验证实例可以填入空位身份。
def test_reassign_instance_fills_empty_slot() -> None:
    """【通用】右键选择空位时把实例放入该队伍身份。"""

    # 【通用】先腾出第 2 队队员2的空位。
    teams = clear_instance_assignment(_build_teams(), 6)
    # 【通用】把实例 0 分配到第 2 队队员2。
    teams = reassign_instance(teams, 0, 2, Role.MEMBER_2)
    # 【通用】目标身份保存新实例。
    assert teams[1].bindings[Role.MEMBER_2].instance_index == 0
    # 【通用】实例原来的第 1 队队长身份变为空位。
    assert teams[0].bindings[Role.LEADER].instance_index == -1
    # 【通用】实例只能属于一个身份。
    assert find_assignment(teams, 0) == (2, Role.MEMBER_2)


# 【通用】验证目标身份被占用时两个实例互换位置。
def test_reassign_instance_swaps_occupied_slots() -> None:
    """【通用】右键选择已被占用的身份时不会丢失原窗口。"""

    # 【通用】把实例 0 分配到第 2 队队员3占用的身份。
    teams = reassign_instance(_build_teams(), 0, 2, Role.MEMBER_3)
    # 【通用】新身份由实例 0 使用。
    assert teams[1].bindings[Role.MEMBER_3].instance_index == 0
    # 【通用】被顶替的实例 7 换到实例 0 原来的身份。
    assert teams[0].bindings[Role.LEADER].instance_index == 7
    # 【通用】两个实例的身份都已更新。
    assert find_assignment(teams, 0) == (2, Role.MEMBER_3)
    assert find_assignment(teams, 7) == (1, Role.LEADER)
    # 【通用】八窗口数量不因交换而减少。
    assert {binding.instance_index for team in teams for binding in team.bindings.values()} == set(range(8))


# 【通用】验证未分配实例占用身份时原窗口让出槽位。
def test_reassign_unassigned_instance_clears_previous_occupant() -> None:
    """【通用】被顶替的窗口没有可交换位置时变为未分配。"""

    # 【通用】取消实例 4 的身份，使其成为未分配窗口。
    teams = clear_instance_assignment(_build_teams(), 4)
    # 【通用】把未分配的实例 4 分配到第 1 队队员2。
    teams = reassign_instance(teams, 4, 1, Role.MEMBER_2)
    # 【通用】目标身份保存新实例。
    assert teams[0].bindings[Role.MEMBER_2].instance_index == 4
    # 【通用】被顶替的实例不再属于任何身份，也不会与新实例重复。
    assert find_assignment(teams, 2) is None
    # 【通用】同批窗口数量不因顶替而重复分配。
    assigned = [binding.instance_index for team in teams for binding in team.bindings.values() if binding.is_assigned]
    # 【通用】七个已分配窗口互不相同，空出的身份保持 -1。
    assert sorted(assigned) == [0, 1, 3, 4, 5, 6, 7]


# 【通用】验证重新分配后仍然保留设备连接信息。
def test_reassign_instance_keeps_connection_state() -> None:
    """【通用】交换身份不应导致已经探测到的序列号丢失。"""

    # 【通用】把实例 0 与第 2 队队员3交换。
    teams = reassign_instance(_build_teams(), 0, 2, Role.MEMBER_3)
    # 【通用】实例 0 保留原有序列号。
    assert teams[1].bindings[Role.MEMBER_3].adb_serial == "emulator-test"
    # 【通用】交换过来的实例 7 同样保留序列号。
    assert teams[0].bindings[Role.LEADER].adb_serial == "emulator-test"


# 【通用】验证非法参数不会破坏两队结构。
def test_reassign_instance_rejects_invalid_arguments() -> None:
    """【通用】右键菜单传入错误参数时必须报错而不是产生缺员队伍。"""

    # 【通用】空位占位索引不能作为分配来源。
    with pytest.raises(ValueError, match="实例索引"):
        # 【通用】传入 -1 触发校验。
        reassign_instance(_build_teams(), -1, 1, Role.LEADER)
    # 【通用】队伍编号只能是 1 或 2。
    with pytest.raises(ValueError, match="队伍编号"):
        # 【通用】传入第 3 队触发校验。
        reassign_instance(_build_teams(), 0, 3, Role.LEADER)
