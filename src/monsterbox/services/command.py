"""【通用】提供安全、可超时、静默且不经过 Shell 的外部命令执行器。"""

# 【通用】导入操作系统模块以识别 Windows 平台。
import os
# 【通用】导入子进程模块以调用 ldconsole 和 ADB。
import subprocess
# 【通用】导入数据类以返回结构化命令结果。
from dataclasses import dataclass
# 【通用】导入路径类型以兼容 Windows 可执行文件路径。
from pathlib import Path


# 【通用】建立隐藏子进程控制台窗口的执行参数。
def silent_process_options() -> dict:
    """【通用】返回 Windows 下不弹出 CMD 视窗的 subprocess 参数，其他系统返回空字典。"""

    # 【通用】非 Windows 平台不存在控制台窗口闪烁问题，直接返回空参数。
    if os.name != "nt":
        # 【通用】空字典展开后不会改变原有调用行为。
        return {}
    # 【通用】建立 Windows 专用启动信息对象。
    startup_info = subprocess.STARTUPINFO()
    # 【通用】要求系统采用下面设置的窗口显示方式。
    startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    # 【通用】把窗口显示方式设置为隐藏，兼容不支持 CREATE_NO_WINDOW 的旧系统。
    startup_info.wShowWindow = subprocess.SW_HIDE
    # 【通用】返回静默执行所需的完整参数。
    return {
        # 【通用】CREATE_NO_WINDOW 让 ldconsole、ADB 等控制台程序在后台运行，不弹出 CMD 视窗。
        "creationflags": subprocess.CREATE_NO_WINDOW,
        # 【通用】同时提供隐藏窗口的启动信息作为双保险。
        "startupinfo": startup_info,
    }


# 【通用】返回静默执行状态说明，供界面日志确认当前版本是否已启用静默。
def silent_execution_description() -> str:
    """【通用】用一行中文说明外部命令的静默策略，便于用户确认没有运行旧版本。"""

    # 【通用】非 Windows 系统本身不会弹出 CMD 视窗。
    if os.name != "nt":
        # 【通用】说明当前系统不需要额外处理。
        return "静默执行：不需要（当前系统不会弹出 CMD 视窗）"
    # 【通用】Windows 下所有外部命令都带上不创建控制台窗口的参数。
    return "静默执行：已启用（Windows 下启动模拟器、ADB、截图等操作均不弹出 CMD 视窗）"


# 【通用】保存外部命令的标准化执行结果。
@dataclass(frozen=True, slots=True)
class CommandResult:
    """【通用】封装退出码、标准输出和错误输出。"""

    # 【通用】记录进程退出码。
    return_code: int
    # 【通用】记录去除首尾空白后的标准输出。
    stdout: str
    # 【通用】记录去除首尾空白后的错误输出。
    stderr: str

    # 【通用】提供命令是否成功的统一判断。
    @property
    def succeeded(self) -> bool:
        """【通用】返回外部命令是否以零退出码结束。"""

        # 【通用】零退出码代表命令执行成功。
        return self.return_code == 0


# 【通用】以参数列表安全执行外部程序。
def run_command(executable: Path, arguments: list[str], timeout_seconds: float = 15) -> CommandResult:
    """【通用】静默执行命令并在超时后终止，禁止拼接 Shell 字符串。"""

    # 【通用】校验可执行文件存在，提前提供清晰错误。
    if not executable.is_file():
        # 【通用】抛出文件错误供界面配置提示使用。
        raise FileNotFoundError(f"找不到可执行文件：{executable}")
    # 【通用】通过参数数组启动程序，避免命令注入。
    process = subprocess.run(
        # 【通用】将可执行文件与参数组合为独立元素。
        [str(executable), *arguments],
        # 【通用】捕获文本输出用于状态和日志显示。
        capture_output=True,
        # 【通用】以文本方式解码输出。
        text=True,
        # 【通用】雷电与 ADB 命令统一使用 UTF-8 输出中文实例名称。
        encoding="utf-8",
        # 【通用】容忍外部工具偶发的异常字符。
        errors="replace",
        # 【通用】限制命令最长运行时间，避免界面任务永久等待。
        timeout=timeout_seconds,
        # 【通用】不启用 Shell，确保参数不会被二次解析。
        shell=False,
        # 【通用】不自动抛出非零退出码，交由服务层解释。
        check=False,
        # 【通用】应用 Windows 静默参数，启动模拟器等操作不会跳出 CMD 视窗。
        **silent_process_options(),
    )
    # 【通用】转换为不可变结果对象供上层处理。
    return CommandResult(process.returncode, process.stdout.strip(), process.stderr.strip())
