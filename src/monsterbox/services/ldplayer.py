"""【通用】封装雷电模拟器 ldconsole 实例生命周期操作。"""

# 【通用】导入数据类以描述雷电实例列表记录。
from dataclasses import dataclass
# 【通用】导入路径类型以保存 ldconsole 安装位置。
from pathlib import Path
# 【通用】导入安全命令执行器。
from monsterbox.services.command import CommandResult, run_command


# 【通用】保存 ldconsole list2 返回的单个模拟器资料。
@dataclass(frozen=True, slots=True)
class LdPlayerInstance:
    """【通用】提供中控台表格显示所需的实例状态。"""

    # 【通用】保存雷电实例索引。
    index: int
    # 【通用】保存雷电实例名称。
    name: str
    # 【通用】保存安卓系统是否已经启动。
    android_started: bool
    # 【通用】保存雷电模拟器进程编号。
    process_id: int


# 【通用】解析 ldconsole list2 的多行文字输出。
def parse_instance_list(output: str) -> list[LdPlayerInstance]:
    """【通用】将雷电实例文字转换为可排序的表格记录。"""

    # 【通用】准备保存所有格式正确的模拟器记录。
    instances: list[LdPlayerInstance] = []
    # 【通用】逐行解析雷电返回内容。
    for line in output.splitlines():
        # 【通用】跳过空白行，避免产生无效实例。
        if not line.strip():
            # 【通用】继续处理下一条记录。
            continue
        # 【通用】按雷电 list2 的逗号格式拆分字段。
        fields = [field.strip() for field in line.split(",")]
        # 【通用】字段不足时拒绝不完整记录。
        if len(fields) < 7:
            # 【通用】向上层报告雷电输出格式异常。
            raise ValueError(f"无法解析雷电实例资料：{line}")
        # 【通用】转换索引、启动标志和进程编号。
        try:
            # 【通用】建立不可变实例记录供界面安全使用。
            instance = LdPlayerInstance(
                # 【通用】第一个字段是实例索引。
                index=int(fields[0]),
                # 【通用】第二个字段是用户设置的实例名称。
                name=fields[1],
                # 【通用】第五个字段以 1 表示安卓已经启动。
                android_started=fields[4] == "1",
                # 【通用】第六个字段是模拟器进程编号。
                process_id=int(fields[5]),
            )
        # 【通用】数字字段异常时转换为明确的格式错误。
        except ValueError as error:
            # 【通用】保留原始记录便于用户排查雷电版本差异。
            raise ValueError(f"无法解析雷电实例资料：{line}") from error
        # 【通用】加入有效实例记录。
        instances.append(instance)
    # 【通用】按实例索引排序，保证表格顺序稳定。
    return sorted(instances, key=lambda item: item.index)


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

    # 【通用】查询指定实例的 ADB 设备序列号。
    def get_adb_serial(self, instance_index: int) -> str:
        """【通用】通过 ldconsole adb --index 获取实例连接地址。"""

        # 【通用】调用雷电官方 adb 命令查询调试地址。
        result = run_command(self._executable, ["adb", "--index", str(instance_index), "--command", "get-serialno"], 10)
        # 【通用】命令失败时向上层报告错误，避免返回空序列号。
        if not result.succeeded:
            # 【通用】提取错误信息供日志显示。
            raise RuntimeError(result.stderr or f"无法取得实例 {instance_index} 的 ADB 序列号")
        # 【通用】雷电返回 emulator-5554 或 127.0.0.1:5555 格式。
        serial = result.stdout.strip()
        # 【通用】空结果视为实例未启动或ADB未就绪。
        if not serial:
            # 【通用】向上层明确说明序列号缺失原因。
            raise RuntimeError(f"实例 {instance_index} 未启动或 ADB 未就绪")
        # 【通用】返回标准化设备序列号供 ADB -s 参数使用。
        return serial

    # 【通用】查询全部实例文本信息供配置和状态解析使用。
    def list_instances(self) -> CommandResult:
        """【通用】返回 ldconsole list2 的原始实例列表。"""

        # 【通用】调用 list2 获取实例索引、名称和运行状态。
        return run_command(self._executable, ["list2"])

    # 【通用】查询并解析可供多选表格显示的全部实例。
    def get_instances(self) -> list[LdPlayerInstance]:
        """【通用】返回按索引排序的雷电模拟器记录。"""

        # 【通用】通过现有服务方法取得原始命令结果。
        result = self.list_instances()
        # 【通用】命令失败时不使用可能不完整的标准输出。
        if not result.succeeded:
            # 【通用】向界面返回雷电工具提供的错误原因。
            raise RuntimeError(result.stderr or "无法取得雷电模拟器列表")
        # 【通用】解析有效输出并返回结构化实例清单。
        return parse_instance_list(result.stdout)
