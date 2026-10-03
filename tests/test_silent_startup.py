"""【通用】验证无控制台启动与成品 EXE 的图形子系统校验。"""

# 【通用】导入动态加载工具以在测试中载入项目根目录的编译脚本。
import importlib.util
# 【通用】导入路径类型定位编译脚本与测试成品。
from pathlib import Path
# 【通用】导入系统模块以注入模拟的 ctypes。
import sys
# 【通用】导入简化命名空间对象以模拟 Windows 接口。
from types import SimpleNamespace
# 【通用】导入 pytest 验证异常和断言。
import pytest
# 【通用】导入应用入口中待测试的隐藏控制台函数。
from monsterbox.main import hide_own_console_window

# 【通用】记录项目根目录以便载入编译脚本。
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# 【通用】按文件位置载入编译脚本，避免依赖测试执行目录。
def _load_build_exe():
    """【通用】返回可调用的 build_exe 模块对象。"""

    # 【通用】建立模块加载规格。
    spec = importlib.util.spec_from_file_location("monsterbox_build_exe", PROJECT_ROOT / "build_exe.py")
    # 【通用】模块规格缺失时直接报错。
    assert spec is not None and spec.loader is not None
    # 【通用】建立空模块对象。
    module = importlib.util.module_from_spec(spec)
    # 【通用】执行脚本内容以取得函数定义。
    spec.loader.exec_module(module)
    # 【通用】返回载入完成的模块。
    return module


# 【通用】建立指定子系统和可选头类型的伪 PE 文件内容。
def _fake_pe(subsystem: int, optional_magic: int = 0x20B) -> bytes:
    """【通用】生成仅包含头部的最小 PE 资料供解析测试。"""

    # 【通用】建立 64 字节 DOS 头，并在 0x3C 处写入 PE 标头偏移量。
    dos_header = bytearray(0x40)
    # 【通用】把 PE 标头放在 DOS 头之后。
    dos_header[0x3C:0x40] = (0x40).to_bytes(4, "little")
    # 【通用】建立 PE 签名、COFF 头与可选头。
    pe_header = bytearray(4 + 20 + 70)
    # 【通用】写入 PE 签名。
    pe_header[0:4] = b"PE\0\0"
    # 【通用】写入可选头类型标识，模拟 PE32+ 或 PE32。
    pe_header[4 + 20:4 + 22] = optional_magic.to_bytes(2, "little")
    # 【通用】在可选头第 68 字节处写入子系统编号。
    pe_header[4 + 20 + 68:4 + 20 + 70] = subsystem.to_bytes(2, "little")
    # 【通用】返回完整的最小 PE 文件内容。
    return bytes(dos_header) + bytes(pe_header)


# 【通用】模拟 ctypes 的数组构造，便于替代真实 Windows 类型。
class _FakeUintArray:
    """【通用】支持“类型 * 长度”写法并返回可调用的构造器。"""

    # 【通用】返回一个生成占位数组的可调用对象。
    def __mul__(self, count: int):
        # 【通用】忽略真实类型，仅返回可调用对象。
        return lambda: [0] * count

    # 【通用】兼容“长度 * 类型”的写法。
    __rmul__ = __mul__


# 【通用】构造模拟的 ctypes 模块，记录被隐藏的窗口句柄。
def _build_fake_ctypes(console_handle: int, process_count: int, hidden: list[tuple[int, int]]):
    """【通用】返回带内核与窗口接口的伪模块。"""

    # 【通用】返回可在测试中注入 sys.modules 的伪模块。
    return SimpleNamespace(
        # 【通用】提供支持数组乘法的伪无符号整数类型。
        c_uint=_FakeUintArray(),
        # 【通用】提供内核与窗口接口。
        windll=SimpleNamespace(
            # 【通用】内核接口返回控制台句柄与进程数量。
            kernel32=SimpleNamespace(
                GetConsoleWindow=lambda: console_handle,
                GetConsoleProcessList=lambda *_args: process_count,
            ),
            # 【通用】窗口接口记录隐藏调用。
            user32=SimpleNamespace(ShowWindow=lambda handle, command: hidden.append((handle, command))),
        ),
    )


# 【通用】验证非 Windows 平台不做任何控制台处理。
def test_hide_own_console_window_skips_other_platforms(monkeypatch: pytest.MonkeyPatch) -> None:
    """【通用】Linux 与 macOS 上必须直接返回未处理。"""

    # 【通用】模拟 posix 平台。
    monkeypatch.setattr("monsterbox.main.os", SimpleNamespace(name="posix"))
    # 【通用】非 Windows 平台返回未处理状态。
    assert hide_own_console_window() is False


# 【通用】验证没有控制台的进程不做处理。
def test_hide_own_console_window_without_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """【通用】图形版 EXE 本身没有控制台窗口，应安全返回。"""

    # 【通用】建立返回空句柄的模拟内核接口。
    fake_ctypes = _build_fake_ctypes(0, 1, [])
    # 【通用】模拟 Windows 平台并注入模拟 ctypes。
    monkeypatch.setattr("monsterbox.main.os", SimpleNamespace(name="nt"))
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)
    # 【通用】没有控制台时返回未处理状态。
    assert hide_own_console_window() is False


# 【通用】验证独占控制台时隐藏窗口。
def test_hide_own_console_window_hides_owned_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """【通用】双击启动且控制台只属于本进程时应隐藏视窗。"""

    # 【通用】准备记录被隐藏的窗口句柄。
    hidden: list[tuple[int, int]] = []
    # 【通用】模拟 Windows 平台并注入模拟 ctypes。
    monkeypatch.setattr("monsterbox.main.os", SimpleNamespace(name="nt"))
    monkeypatch.setitem(sys.modules, "ctypes", _build_fake_ctypes(4242, 1, hidden))
    # 【通用】隐藏操作必须成功。
    assert hide_own_console_window() is True
    # 【通用】必须使用 SW_HIDE 隐藏该句柄。
    assert hidden == [(4242, 0)]


# 【通用】验证共享控制台时保持不动。
def test_hide_own_console_window_keeps_shared_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """【通用】在用户自己的终端里运行时不得隐藏该终端。"""

    # 【通用】准备记录可能的隐藏调用。
    hidden: list[tuple[int, int]] = []
    # 【通用】模拟 Windows 平台并注入模拟 ctypes，控制台内存在终端与 Python 等进程。
    monkeypatch.setattr("monsterbox.main.os", SimpleNamespace(name="nt"))
    monkeypatch.setitem(sys.modules, "ctypes", _build_fake_ctypes(4242, 3, hidden))
    # 【通用】共享控制台时返回未处理状态。
    assert hide_own_console_window() is False
    # 【通用】必须没有调用隐藏接口。
    assert hidden == []


# 【通用】验证编译脚本接受图形子系统成品。
def test_verify_windowed_executable_accepts_gui(tmp_path: Path) -> None:
    """【通用】图形子系统成品必须通过静默校验。"""

    # 【通用】载入编译脚本。
    build_exe = _load_build_exe()
    # 【通用】建立图形子系统伪成品。
    executable = tmp_path / "MonsterBox.exe"
    # 【通用】写入伪 PE 头部。
    executable.write_bytes(_fake_pe(2))
    # 【通用】校验通过且不抛异常。
    build_exe.verify_windowed_executable(executable)


# 【通用】验证编译脚本拒绝控制台子系统成品。
def test_verify_windowed_executable_rejects_console(tmp_path: Path) -> None:
    """【通用】会弹出 CMD 视窗的控制台成品必须被拒绝。"""

    # 【通用】载入编译脚本。
    build_exe = _load_build_exe()
    # 【通用】建立控制台子系统伪成品。
    executable = tmp_path / "MonsterBox.exe"
    # 【通用】写入伪 PE 头部。
    executable.write_bytes(_fake_pe(3))
    # 【通用】控制台成品必须报告明确错误。
    with pytest.raises(RuntimeError, match="CMD"):
        # 【通用】执行静默校验。
        build_exe.verify_windowed_executable(executable)


# 【通用】验证 32 位图形成品同样通过校验。
def test_verify_windowed_executable_accepts_pe32_gui(tmp_path: Path) -> None:
    """【通用】PE32 与 PE32+ 两种头部的图形成品都必须通过。"""

    # 【通用】载入编译脚本。
    build_exe = _load_build_exe()
    # 【通用】建立 PE32 图形子系统伪成品。
    executable = tmp_path / "MonsterBox32.exe"
    # 【通用】写入伪 PE 头部。
    executable.write_bytes(_fake_pe(2, optional_magic=0x10B))
    # 【通用】校验通过且不抛异常。
    build_exe.verify_windowed_executable(executable)


# 【通用】验证无法识别可选头时只警告不中断编译。
def test_build_rejects_running_output_before_overwrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """【通用】成品运行时必须给出明确提示，不等待 PyInstaller 最后报存取拒绝。"""

    # 【通用】载入编译脚本。
    build_exe = _load_build_exe()
    # 【通用】建立模拟的现有成品文件。
    output = tmp_path / "MonsterBox.exe"
    # 【通用】写入占位内容使成品路径存在。
    output.write_bytes(b"running")
    # 【通用】把脚本输出位置切换到隔离测试文件。
    monkeypatch.setattr(build_exe, "OUTPUT_EXE", output)
    # 【通用】模拟 Windows 已发现运行中的 MonsterBox 进程。
    monkeypatch.setattr(build_exe, "is_monsterbox_running", lambda: True)
    # 【通用】预检查必须阻止覆盖并提示先关闭程序。
    with pytest.raises(RuntimeError, match="正在运行"):
        # 【通用】执行成品可用性检查。
        build_exe.ensure_output_is_available()


# 【通用】验证不存在旧成品时不会执行进程查询。
def test_build_allows_missing_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """【通用】首次打包不应被无关的同名进程检查阻止。"""

    # 【通用】载入编译脚本。
    build_exe = _load_build_exe()
    # 【通用】指定一个尚不存在的成品路径。
    monkeypatch.setattr(build_exe, "OUTPUT_EXE", tmp_path / "MonsterBox.exe")
    # 【通用】若错误调用进程查询就主动让测试失败。
    monkeypatch.setattr(build_exe, "is_monsterbox_running", lambda: pytest.fail("不应查询不存在的成品"))
    # 【通用】首次打包检查应直接通过。
    build_exe.ensure_output_is_available()


# 【通用】验证无法识别可选头时只警告不中断编译。
def test_verify_windowed_executable_warns_on_unknown_magic(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """【通用】格式差异不应误判为控制台程序而中断编译。"""

    # 【通用】载入编译脚本。
    build_exe = _load_build_exe()
    # 【通用】建立可选头类型无法识别的伪成品。
    executable = tmp_path / "Unknown.exe"
    # 【通用】写入伪 PE 头部。
    executable.write_bytes(_fake_pe(3, optional_magic=0))
    # 【通用】未知可选头只提示警告，不抛异常。
    build_exe.verify_windowed_executable(executable)
    # 【通用】标准输出必须包含跳过校验的警告。
    assert "跳过" in capsys.readouterr().out
