"""【通用】验证默认配置会建立两队八窗口。"""

# 【通用】导入路径类型建立不存在的配置位置。
from pathlib import Path
# 【通用】导入配置加载、资料夹搜索和保存函数。
from monsterbox.config import find_ldplayer_tools, load_settings, save_settings
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


# 【通用】验证用户只需选择上层资料夹即可自动找到雷电工具。
def test_find_ldplayer_tools_searches_child_directories(tmp_path: Path) -> None:
    """【通用】递归找到位于同一雷电子目录的控制台与 ADB。"""

    # 【通用】建立模拟雷电安装子目录。
    install_directory = tmp_path / "LDPlayer" / "LDPlayer9"
    # 【通用】建立完整测试目录结构。
    install_directory.mkdir(parents=True)
    # 【通用】建立模拟 ldconsole 文件。
    console = install_directory / "ldconsole.exe"
    # 【通用】写入最小内容使路径成为普通文件。
    console.write_bytes(b"console")
    # 【通用】建立模拟 ADB 文件。
    adb = install_directory / "adb.exe"
    # 【通用】写入最小内容使路径成为普通文件。
    adb.write_bytes(b"adb")
    # 【通用】从上层资料夹执行自动搜索。
    tools = find_ldplayer_tools(tmp_path)
    # 【通用】必须优先返回同目录工具组合。
    assert tools == (console, adb)


# 【通用】验证浏览框选择结果可以保存并重新加载。
def test_save_settings_persists_discovered_tools(tmp_path: Path) -> None:
    """【通用】保存路径时必须保留原有两队八窗口映射。"""

    # 【通用】加载默认两队配置作为保存来源。
    settings = load_settings(tmp_path / "missing.json")
    # 【通用】指定隔离的测试配置文件。
    settings_path = tmp_path / "config" / "settings.json"
    # 【通用】保存当前应用配置。
    save_settings(settings_path, settings)
    # 【通用】重新加载保存后的配置。
    loaded = load_settings(settings_path)
    # 【通用】确认工具路径保持一致。
    assert loaded.ldconsole_path == settings.ldconsole_path
    # 【通用】确认两队配置没有因路径保存而丢失。
    assert [team.team_id for team in loaded.teams] == [1, 2]
