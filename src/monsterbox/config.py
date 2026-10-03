"""【通用】加载本机工具路径和两队八窗口绑定配置。"""

# 【通用】导入 JSON 以读取用户可编辑配置。
import json
# 【通用】导入数据类以保存应用设置。
from dataclasses import dataclass
# 【通用】导入路径工具以自动探测 Windows 安装目录。
from pathlib import Path
# 【通用】导入队伍与设备数据模型。
from monsterbox.models import DeviceBinding, Role, TeamConfig


# 【通用】保存中控台运行所需的完整配置。
@dataclass(frozen=True, slots=True)
class AppSettings:
    """【通用】集中保存外部工具路径和两队绑定。"""

    # 【通用】记录雷电实例管理工具路径。
    ldconsole_path: Path
    # 【通用】记录 ADB 工具路径。
    adb_path: Path
    # 【通用】固定保存两支队伍的配置。
    teams: tuple[TeamConfig, TeamConfig]


# 【通用】列出常见雷电 9 安装目录以支持自动探测。
_COMMON_LD_DIRS = (
    # 【通用】雷电官网下载版本常见目录。
    Path("C:/LDPlayer/LDPlayer9"),
    # 【通用】Program Files 下可能存在的安装目录。
    Path("C:/Program Files/LDPlayer/LDPlayer9"),
    # 【通用】Program Files (x86) 下可能存在的安装目录。
    Path("C:/Program Files (x86)/LDPlayer/LDPlayer9"),
)


# 【通用】自动寻找同一目录中的 ldconsole 与 ADB。
def discover_ldplayer_tools() -> tuple[Path, Path] | None:
    """【通用】返回首个有效雷电工具目录，未找到时返回空值。"""

    # 【通用】依次检查常见安装目录。
    for directory in _COMMON_LD_DIRS:
        # 【通用】构造雷电控制台文件路径。
        ldconsole = directory / "ldconsole.exe"
        # 【通用】构造雷电自带 ADB 文件路径。
        adb = directory / "adb.exe"
        # 【通用】只有两个工具都存在时才采用该目录。
        if ldconsole.is_file() and adb.is_file():
            # 【通用】返回可直接使用的工具组合。
            return ldconsole, adb
    # 【通用】未探测到雷电时交由配置文件或界面选择。
    return None


# 【通用】读取 JSON 配置并构造经过结构校验的数据模型。
def load_settings(path: Path) -> AppSettings:
    """【通用】加载两队八窗口配置，缺少文件时使用默认索引。"""

    # 【通用】配置不存在时尝试自动探测雷电路径。
    discovered = discover_ldplayer_tools()
    # 【通用】选择探测路径或空占位路径以便界面提示。
    default_ldconsole, default_adb = discovered or (Path("ldconsole.exe"), Path("adb.exe"))
    # 【通用】存在本机配置时读取 JSON 数据。
    if path.is_file():
        # 【通用】使用 UTF-8 支持中文角色名。
        raw = json.loads(path.read_text(encoding="utf-8"))
    # 【通用】没有配置文件时建立 0 至 7 的默认实例映射。
    else:
        # 【通用】生成两队默认工具路径和实例索引。
        raw = {"ldconsole_path": str(default_ldconsole), "adb_path": str(default_adb), "teams": [{"team_id": team_id, "instances": {role.value: (team_id - 1) * 4 + offset for offset, role in enumerate(Role)}} for team_id in (1, 2)]}
    # 【通用】准备保存经过校验的两支队伍。
    teams: list[TeamConfig] = []
    # 【通用】逐队解析角色与实例绑定。
    for team_raw in raw["teams"]:
        # 【通用】读取并标准化队伍编号。
        team_id = int(team_raw["team_id"])
        # 【通用】为四个固定角色建立绑定，队员2/3共用同一模型。
        bindings = {role: DeviceBinding(team_id, role, int(team_raw["instances"][role.value])) for role in Role}
        # 【通用】建立单支队伍配置对象。
        team = TeamConfig(team_id, bindings)
        # 【通用】立即验证角色完整性，避免错误进入界面。
        team.validate()
        # 【通用】保存有效队伍。
        teams.append(team)
    # 【通用】强制要求恰好两支队伍。
    if len(teams) != 2 or {team.team_id for team in teams} != {1, 2}:
        # 【通用】拒绝缺队或重复队号配置。
        raise ValueError("配置必须且只能包含第 1 队和第 2 队")
    # 【通用】按队号排序后返回不可变应用配置。
    ordered = tuple(sorted(teams, key=lambda team: team.team_id))
    # 【通用】类型已由长度检查保证为两个元素。
    return AppSettings(Path(raw["ldconsole_path"]), Path(raw["adb_path"]), ordered)  # type: ignore[arg-type]
