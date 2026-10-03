"""【通用】验证 ADB 服务在静默前提下解析设备与截图结果。"""

# 【通用】导入简化命名空间对象以模拟子进程返回值。
from types import SimpleNamespace
# 【通用】导入路径类型建立测试用工具路径。
from pathlib import Path
# 【通用】导入 pytest 验证断言与异常。
import pytest
# 【通用】导入 ADB 服务和待检查的执行器模块。
from monsterbox.services import adb as adb_module
from monsterbox.services.adb import AdbService
from monsterbox.services import command


# 【通用】验证设备清单解析只保留在线设备。
def test_list_devices_returns_online_serials(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """【通用】offline 与未授权设备不得进入可用序列号清单。"""

    # 【通用】建立占位 ADB 文件以通过存在性校验。
    executable = tmp_path / "adb.exe"
    # 【通用】写入最小内容使其成为普通文件。
    executable.write_bytes(b"stub")
    # 【通用】准备收集静默参数。
    captured: dict = {}

    # 【通用】模拟 adb devices 输出。
    def fake_run(arguments: list, **kwargs: object) -> SimpleNamespace:
        # 【通用】保存子进程参数供静默检查。
        captured.update(kwargs)
        # 【通用】返回包含在线、离线与异常行的设备清单。
        return SimpleNamespace(
            returncode=0,
            stdout="List of devices attached\nemulator-5554\tdevice\nemulator-5556\toffline\n",
            stderr="",
        )

    # 【通用】替换统一执行器使用的子进程模块。
    monkeypatch.setattr(command, "subprocess", SimpleNamespace(run=fake_run))
    # 【通用】用哨兵值确认静默参数被传入。
    monkeypatch.setattr(command, "silent_process_options", lambda: {"creationflags": 456})
    # 【通用】执行设备清单查询。
    devices = AdbService(executable).list_devices()
    # 【通用】只返回状态为 device 的序列号。
    assert devices == ["emulator-5554"]
    # 【通用】设备查询同样必须保持静默。
    assert captured["creationflags"] == 456


# 【通用】验证截图命令携带静默参数。
def test_screenshot_png_is_silent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """【通用】识图点击的截图过程不得弹出 CMD 视窗。"""

    # 【通用】准备收集子进程参数。
    captured: dict = {}

    # 【通用】模拟二进制截图输出。
    def fake_run(arguments: list, **kwargs: object) -> SimpleNamespace:
        # 【通用】保存关键字参数供静默检查。
        captured.update(kwargs)
        # 【通用】返回 PNG 二进制数据。
        return SimpleNamespace(returncode=0, stdout=b"PNGDATA", stderr=b"")

    # 【通用】替换 ADB 服务模块中的子进程执行函数。
    monkeypatch.setattr(adb_module.subprocess, "run", fake_run)
    # 【通用】用哨兵值确认静默参数被传入。
    monkeypatch.setattr(adb_module, "silent_process_options", lambda: {"creationflags": 789})
    # 【通用】执行截图。
    png = AdbService(tmp_path / "adb.exe").screenshot_png("emulator-5554")
    # 【通用】截图数据必须原样返回。
    assert png == b"PNGDATA"
    # 【通用】截图命令必须携带静默参数。
    assert captured["creationflags"] == 789
