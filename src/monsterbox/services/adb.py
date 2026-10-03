"""【通用】封装队长、队员1及队员2/3共用的 ADB 操作。"""

# 【通用】导入路径类型以保存 ADB 程序位置。
from pathlib import Path
# 【通用】导入安全命令执行器和结果类型。
from monsterbox.services.command import CommandResult, run_command


# 【通用】为所有队伍角色提供统一安卓控制能力。
class AdbService:
    """【通用】通过设备序列号执行状态、点击、滑动和截图命令。"""

    # 【通用】保存 ADB 可执行文件路径。
    def __init__(self, executable: Path) -> None:
        """【通用】初始化 ADB 服务。"""

        # 【通用】记录 ADB 路径供后续命令复用。
        self._executable = executable

    # 【通用】执行绑定到某个设备序列号的 ADB 子命令。
    def _device_command(self, serial: str, arguments: list[str]) -> CommandResult:
        """【通用】将设备参数与业务命令安全组合。"""

        # 【通用】拒绝空设备号，避免命令误发至默认设备。
        if not serial.strip():
            # 【通用】向编排层报告设备尚未绑定。
            raise ValueError("ADB 设备序列号不能为空")
        # 【通用】显式指定目标设备以防两队窗口串线。
        return run_command(self._executable, ["-s", serial, *arguments])

    # 【通用】检查角色绑定设备是否已在线。
    def get_state(self, serial: str) -> CommandResult:
        """【通用】查询单个设备连接状态。"""

        # 【通用】调用 get-state 获取 online/offline 状态。
        return self._device_command(serial, ["get-state"])

    # 【队长/队员】在目标安卓窗口执行坐标点击。
    def tap(self, serial: str, x: int, y: int) -> CommandResult:
        """【通用】向指定设备发送触摸点击。"""

        # 【通用】通过 input tap 执行经过坐标换算的点击。
        return self._device_command(serial, ["shell", "input", "tap", str(x), str(y)])

    # 【队长/队员】在目标安卓窗口执行滑动。
    def swipe(self, serial: str, start: tuple[int, int], end: tuple[int, int], duration_ms: int) -> CommandResult:
        """【通用】向指定设备发送带时长的滑动操作。"""

        # 【通用】拆分起点坐标以构造 ADB 参数。
        start_x, start_y = start
        # 【通用】拆分终点坐标以构造 ADB 参数。
        end_x, end_y = end
        # 【通用】发送滑动命令，队员2与3直接复用本实现。
        return self._device_command(serial, ["shell", "input", "swipe", str(start_x), str(start_y), str(end_x), str(end_y), str(duration_ms)])

    # 【通用】获取当前所有在线ADB设备序列号列表。
    def list_devices(self) -> list[str]:
        """【通用】通过 adb devices 获取所有在线设备序列号（备用方案，当雷电自动获取失败时使用）。"""

        import subprocess
        # 【通用】执行 adb devices -l 列出所有连接设备。
        process = subprocess.run(
            [str(self._executable), "devices"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            shell=False,
            check=False,
        )
        # 【通用】解析输出，跳过第一行"List of devices attached"。
        devices = []
        for line in process.stdout.strip().splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices

    # 【通用】抓取设备当前画面供图像识别使用。
    def screenshot_png(self, serial: str) -> bytes:
        """【通用】直接返回 PNG 字节，不在项目目录留下临时截图。"""

        # 【通用】单独执行二进制命令以避免文本解码破坏 PNG。
        import subprocess
        # 【通用】启动 exec-out screencap 并限制最长等待时间。
        process = subprocess.run([str(self._executable), "-s", serial, "exec-out", "screencap", "-p"], capture_output=True, timeout=15, shell=False, check=False)
        # 【通用】非零退出码表示截图失败。
        if process.returncode != 0:
            # 【通用】将 ADB 错误转为可读异常供任务日志展示。
            raise RuntimeError(process.stderr.decode(errors="replace").strip() or "ADB 截图失败")
        # 【通用】返回内存中的截图数据，避免生成待清理文件。
        return process.stdout
