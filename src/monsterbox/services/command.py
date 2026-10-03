"""【通用】提供安全、可超时且不经过 Shell 的外部命令执行器。"""

# 【通用】导入子进程模块以调用 ldconsole 和 ADB。
import subprocess
# 【通用】导入数据类以返回结构化命令结果。
from dataclasses import dataclass
# 【通用】导入路径类型以兼容 Windows 可执行文件路径。
from pathlib import Path


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
    """【通用】执行命令并在超时后终止，禁止拼接 Shell 字符串。"""

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
        # 【通用】使用系统区域设置并容忍工具的异常字符。
        errors="replace",
        # 【通用】限制命令最长运行时间，避免界面任务永久等待。
        timeout=timeout_seconds,
        # 【通用】不启用 Shell，确保参数不会被二次解析。
        shell=False,
        # 【通用】不自动抛出非零退出码，交由服务层解释。
        check=False,
    )
    # 【通用】转换为不可变结果对象供上层处理。
    return CommandResult(process.returncode, process.stdout.strip(), process.stderr.strip())
