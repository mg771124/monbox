"""【通用】封装雷电模拟器 ldconsole 实例生命周期操作。"""

# 【通用】导入路径类型以保存 ldconsole 安装位置。
from pathlib import Path
# 【通用】导入安全命令执行器。
from monsterbox.services.command import CommandResult, run_command


# 【通用】集中管理雷电模拟器实例。
class LdPlayerService:
    """【通用】通过 ldconsole 启动、停止和查询八个模拟器实例。"""

    # 【通用】保存经过配置层提供的 ldconsole 路径。
    def __init__(self, executable: Path) -> None:
        """【通用】初始化雷电命令服务。"""

        # 【通用】记录可执行文件路径供所有生命周期命令复用。
        self._executable = executable

    # 【通用】启动指定角色绑定的雷电实例。
    def launch(self, instance_index: int) -> CommandResult:
        """【通用】按照实例索引启动窗口。"""

        # 【通用】使用雷电官方 launch 命令启动实例。
        return run_command(self._executable, ["launch", "--index", str(instance_index)], 30)

    # 【通用】关闭指定角色绑定的雷电实例。
    def quit(self, instance_index: int) -> CommandResult:
        """【通用】按照实例索引正常关闭窗口。"""

        # 【通用】使用雷电官方 quit 命令关闭实例。
        return run_command(self._executable, ["quit", "--index", str(instance_index)], 30)

    # 【通用】查询全部实例文本信息供配置和状态解析使用。
    def list_instances(self) -> CommandResult:
        """【通用】返回 ldconsole list2 的原始实例列表。"""

        # 【通用】调用 list2 获取实例索引、名称和运行状态。
        return run_command(self._executable, ["list2"])
