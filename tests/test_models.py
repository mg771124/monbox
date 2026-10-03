"""【通用】验证固定两队四角色数据约束。"""

# 【通用】导入 pytest 验证异常。
import pytest
# 【通用】导入待测试模型。
from monsterbox.models import DeviceBinding, Role, TeamConfig


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
