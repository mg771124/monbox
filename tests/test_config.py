"""【通用】验证默认配置会建立两队八窗口。"""

# 【通用】导入路径类型建立不存在的配置位置。
from pathlib import Path
# 【通用】导入配置加载函数。
from monsterbox.config import load_settings
# 【通用】导入角色枚举验证每队结构。
from monsterbox.models import Role


# 【通用】验证无本机配置时使用稳定默认映射。
def test_default_settings_create_two_complete_teams(tmp_path: Path) -> None:
    """【通用】默认配置必须包含两队且每队四个角色。"""

    # 【通用】从不存在的路径加载默认设置。
    settings = load_settings(tmp_path / "settings.json")
    # 【通用】确认仅存在两支队伍。
    assert len(settings.teams) == 2
    # 【通用】确认两队均包含完整角色集合。
    assert all(set(team.bindings) == set(Role) for team in settings.teams)
    # 【通用】确认八个默认实例索引不重复。
    assert {binding.instance_index for team in settings.teams for binding in team.bindings.values()} == set(range(8))
