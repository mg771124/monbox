"""【通用】验证外部命令执行器的静默执行参数和结果处理。"""

# 【通用】导入简化命名空间对象以模拟 Windows 专用子进程参数。
from types import SimpleNamespace
# 【通用】导入 pytest 验证异常和断言。
import pytest
# 【通用】导入待测试的执行器与静默参数函数。
from monsterbox.services import command
from monsterbox.services.command import run_command, silent_process_options


# 【通用】模拟 Windows 的 STARTUPINFO，避免测试机器限制。
class _FakeStartupInfo:
    """【通用】仅保存静默执行需要设置的两个字段。"""

    # 【通用】初始化启动信息字段为默认值。
    def __init__(self) -> None:
        # 【通用】保存启动信息标志位。
        self.dwFlags = 0
        # 【通用】保存窗口显示方式。
        self.wShowWindow = None


# 【通用】验证非 Windows 平台不附加任何平台专用参数。
def test_silent_process_options_empty_on_other_platforms(monkeypatch: pytest.MonkeyPatch) -> None:
    """【通用】Linux 与 macOS 上必须返回空参数，保持原有行为。"""

    # 【通用】把执行器看到的系统名称替换为 posix。
    monkeypatch.setattr(command, "os", SimpleNamespace(name="posix"))
    # 【通用】非 Windows 平台不应包含 creationflags 等参数。
    assert silent_process_options() == {}


# 【通用】验证 Windows 平台会隐藏子进程控制台窗口。
def test_silent_process_options_hides_console_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """【通用】启动模拟器、ADB 等控制台程序时不得弹出 CMD 视窗。"""

    # 【通用】建立模拟的 Windows 子进程模块。
    fake_subprocess = SimpleNamespace(
        # 【通用】提供启动信息类型。
        STARTUPINFO=_FakeStartupInfo,
        # 【通用】提供显示窗口标志位常量。
        STARTF_USESHOWWINDOW=1,
        # 【通用】提供隐藏窗口常量。
        SW_HIDE=0,
        # 【通用】提供不创建控制台窗口常量。
        CREATE_NO_WINDOW=0x08000000,
    )
    # 【通用】把执行器看到的系统名称替换为 Windows。
    monkeypatch.setattr(command, "os", SimpleNamespace(name="nt"))
    # 【通用】替换子进程模块为模拟实现。
    monkeypatch.setattr(command, "subprocess", fake_subprocess)
    # 【通用】取得静默参数。
    options = silent_process_options()
    # 【通用】必须带上不创建控制台窗口的标记。
    assert options["creationflags"] == 0x08000000
    # 【通用】启动信息必须要求隐藏窗口。
    assert options["startupinfo"].dwFlags & 1
    # 【通用】窗口显示方式必须为隐藏，兼容旧版 Windows。
    assert options["startupinfo"].wShowWindow == 0


# 【通用】验证执行器会把静默参数传给子进程调用。
def test_run_command_forwards_silent_options(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """【通用】任何外部命令都必须经过静默参数，避免漏掉某个动作。"""

    # 【通用】建立占位可执行文件以通过存在性校验。
    executable = tmp_path / "ldconsole.exe"
    # 【通用】写入最小内容使其成为普通文件。
    executable.write_bytes(b"stub")
    # 【通用】准备收集传给子进程的关键字参数。
    captured: dict = {}

    # 【通用】模拟子进程执行并返回成功结果。
    def fake_run(arguments: list, **kwargs: object) -> SimpleNamespace:
        # 【通用】保存完整参数列表供断言使用。
        captured["arguments"] = arguments
        # 【通用】保存全部关键字参数。
        captured.update(kwargs)
        # 【通用】返回带输出的成功结果。
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    # 【通用】替换执行器使用的子进程模块。
    monkeypatch.setattr(command, "subprocess", SimpleNamespace(run=fake_run))
    # 【通用】用哨兵值确认静默参数确实被展开传入。
    monkeypatch.setattr(command, "silent_process_options", lambda: {"creationflags": 123})
    # 【通用】执行一条查询命令。
    result = run_command(executable, ["list2"], 5)
    # 【通用】命令结果应判定为成功并去除首尾空白。
    assert result.succeeded
    # 【通用】标准输出必须被正确保留。
    assert result.stdout == "ok"
    # 【通用】静默参数必须出现在子进程调用中。
    assert captured["creationflags"] == 123
    # 【通用】超时参数必须按调用方要求传入。
    assert captured["timeout"] == 5
    # 【通用】必须始终禁用 Shell。
    assert captured["shell"] is False
    # 【通用】可执行文件与参数必须保持独立元素。
    assert captured["arguments"] == [str(executable), "list2"]


# 【通用】验证缺失可执行文件时给出明确错误。
def test_run_command_rejects_missing_executable(tmp_path) -> None:
    """【通用】找不到 ldconsole 或 ADB 时必须提示用户检查资料夹设置。"""

    # 【通用】不存在的工具路径必须抛出文件错误。
    with pytest.raises(FileNotFoundError, match="找不到可执行文件"):
        # 【通用】传入不存在的可执行文件。
        run_command(tmp_path / "missing.exe", ["list2"])
