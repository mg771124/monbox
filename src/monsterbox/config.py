"""【通用】加载本机工具路径和两队八窗口绑定配置。"""

# 【通用】导入 JSON 以读取用户可编辑配置。
import json
# 【通用】导入数据类以保存应用设置。
from dataclasses import dataclass
# 【通用】导入目录遍历工具以在用户选择的资料夹内寻找雷电程序。
from os import walk
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


# 【通用】在指定资料夹及其子目录中寻找 ldconsole 与 ADB。
def find_ldplayer_tools(directory: Path) -> tuple[Path, Path] | None:
    """【通用】自动寻找工具文件，优先选择位于同一目录的组合。"""

    # 【通用】资料夹不存在时直接返回未找到。
    if not directory.is_dir():
        # 【通用】避免对错误路径执行目录遍历。
        return None
    # 【通用】准备收集所有匹配的控制台路径。
    consoles: list[Path] = []
    # 【通用】准备收集所有匹配的 ADB 路径。
    adb_files: list[Path] = []
    # 【通用】递归遍历用户选择的资料夹并忽略无权限子目录。
    for root, _directories, files in walk(directory, onerror=lambda _error: None):
        # 【通用】建立不区分大小写的文件名映射以兼容 Windows。
        names = {name.lower(): name for name in files}
        # 【通用】发现 ldconsole 时记录其完整路径。
        if "ldconsole.exe" in names:
            # 【通用】保留实际文件名大小写并加入候选清单。
            consoles.append(Path(root) / names["ldconsole.exe"])
        # 【通用】发现 ADB 时记录其完整路径。
        if "adb.exe" in names:
            # 【通用】保留实际文件名大小写并加入候选清单。
            adb_files.append(Path(root) / names["adb.exe"])
    # 【通用】优先寻找和 ldconsole 位于同一目录的 ADB。
    for console in consoles:
        # 【通用】逐个比较 ADB 父目录，避免配对到其他安卓工具。
        for adb in adb_files:
            # 【通用】同目录组合最可能属于同一套雷电安装。
            if console.parent == adb.parent:
                # 【通用】返回可信度最高的工具组合。
                return console, adb
    # 【通用】没有同目录 ADB 时允许使用所选资料夹内第一个 ADB。
    if consoles and adb_files:
        # 【通用】返回找到的首个控制台和 ADB 供用户使用。
        return consoles[0], adb_files[0]
    # 【通用】缺少任一必要工具时返回未找到。
    return None


# 【通用】自动寻找常见安装目录中的 ldconsole 与 ADB。
def discover_ldplayer_tools() -> tuple[Path, Path] | None:
    """【通用】返回首个有效雷电工具组合，未找到时返回空值。"""

    # 【通用】依次检查常见安装目录。
    for directory in _COMMON_LD_DIRS:
        # 【通用】复用资料夹搜索逻辑，确保手动和自动选择行为一致。
        tools = find_ldplayer_tools(directory)
        # 【通用】找到完整工具组合时立即返回。
        if tools is not None:
            # 【通用】将有效路径交给配置加载流程。
            return tools
    # 【通用】未探测到雷电时交由界面让用户选择资料夹。
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


# 【通用】将用户选择的雷电工具路径持久化到本机配置。
def save_settings(path: Path, settings: AppSettings) -> None:
    """【通用】保存工具路径和两队实例映射，不写入任何敏感信息。"""

    # 【通用】建立与加载函数兼容的 JSON 数据结构。
    raw = {
        # 【通用】保存自动找到的 ldconsole 完整路径。
        "ldconsole_path": str(settings.ldconsole_path),
        # 【通用】保存自动找到的 ADB 完整路径。
        "adb_path": str(settings.adb_path),
        # 【通用】保存两支队伍的角色实例索引。
        "teams": [
            # 【通用】为当前队伍建立可序列化结构。
            {
                # 【通用】保存固定队伍编号。
                "team_id": team.team_id,
                # 【通用】按中文角色名保存实例索引。
                "instances": {
                    # 【通用】队员2与3仍由同一个枚举循环处理。
                    role.value: team.bindings[role].instance_index
                    # 【通用】遍历固定四角色。
                    for role in Role
                },
            }
            # 【通用】依次保存第 1 队和第 2 队。
            for team in settings.teams
        ],
    }
    # 【通用】确保本机配置目录存在。
    path.parent.mkdir(parents=True, exist_ok=True)
    # 【通用】以 UTF-8 和易读缩进保存中文配置。
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
