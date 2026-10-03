"""【通用】提供不受 Windows BAT 中文编码影响的一键 EXE 编译流程。"""

# 【通用】导入操作系统模块以识别 Windows 编译环境。
import os
# 【通用】导入子进程模块以安全调用 pip、pytest 和 PyInstaller。
import subprocess
# 【通用】导入系统模块以复用当前 Python 解释器并检查版本。
import sys
# 【通用】导入路径类型以固定项目目录和验证编译成品。
from pathlib import Path


# 【通用】取得本编译脚本所在的项目根目录。
PROJECT_ROOT = Path(__file__).resolve().parent
# 【通用】定义独立 EXE 的预期输出位置。
OUTPUT_EXE = PROJECT_ROOT / "dist" / "MonsterBox.exe"


# 【通用】检查是否有旧版 MonsterBox 正在运行并锁定编译成品。
def is_monsterbox_running() -> bool:
    """【通用】在 Windows 静默查询进程，其他系统直接返回未运行。"""

    # 【通用】非 Windows 系统不使用 tasklist，也没有当前覆盖锁定问题。
    if os.name != "nt":
        # 【通用】返回未发现 Windows 成品进程。
        return False
    # 【通用】建立隐藏 tasklist 子进程窗口的启动信息。
    startup_info = subprocess.STARTUPINFO()
    # 【通用】要求 Windows 使用隐藏窗口设置。
    startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    # 【通用】明确将 tasklist 窗口设为隐藏。
    startup_info.wShowWindow = subprocess.SW_HIDE
    # 【通用】静默查询同名成品进程，不经过 Shell。
    result = subprocess.run(
        # 【通用】只查询 MonsterBox.exe，避免扫描或结束无关进程。
        ["tasklist.exe", "/FI", "IMAGENAME eq MonsterBox.exe", "/NH"],
        # 【通用】捕获查询输出供本函数判断。
        capture_output=True,
        # 【通用】以文本方式读取 Windows 命令输出。
        text=True,
        # 【通用】使用系统默认编码并容忍无法解码字符。
        errors="replace",
        # 【通用】限制进程查询时间，避免编译入口卡住。
        timeout=10,
        # 【通用】禁止 Shell 二次解析参数。
        shell=False,
        # 【通用】查询失败时由返回码和空输出自然判定为未发现。
        check=False,
        # 【通用】禁止查询命令弹出 CMD 视窗。
        creationflags=subprocess.CREATE_NO_WINDOW,
        # 【通用】补充隐藏启动信息兼容旧版 Windows。
        startupinfo=startup_info,
    )
    # 【通用】输出中存在进程名称时表示成品仍在运行。
    return result.returncode == 0 and "monsterbox.exe" in result.stdout.lower()


# 【通用】在耗时安装和测试前确认成品可以安全覆盖。
def ensure_output_is_available() -> None:
    """【通用】旧版程序运行时给出明确提示，不强制结束用户进程。"""

    # 【通用】只有成品存在且同名进程运行时才阻止重新打包。
    if OUTPUT_EXE.is_file() and is_monsterbox_running():
        # 【通用】说明解决方式，避免最后阶段只显示 WinError 5。
        raise RuntimeError(
            "MonsterBox.exe 正在运行，Windows 不允许覆盖 dist\\MonsterBox.exe。"
            "请先关闭全部 MonsterBox 窗口；若仍失败，请在任务管理器结束 MonsterBox.exe 后重新打包。"
        )


# 【通用】使用参数列表执行编译命令，禁止经过 Shell 字符串解析。
def run_step(description: str, arguments: list[str]) -> None:
    """【通用】显示步骤名称并在命令失败时立即终止后续编译。"""

    # 【通用】在控制台显示当前编译阶段。
    print(f"\n{description}...")
    # 【通用】使用项目根目录运行命令以保证相对路径稳定。
    subprocess.run(arguments, cwd=PROJECT_ROOT, check=True, shell=False)


# 【通用】验证编译成品属于图形子系统，双击运行时不会弹出 CMD 视窗。
def verify_windowed_executable(executable: Path) -> None:
    """【通用】读取 PE 头部 Subsystem 字段，2 为图形界面，3 为控制台。"""

    # 【通用】打开成品文件读取头部资料。
    with executable.open("rb") as stream:
        # 【通用】先读取 DOS 头与其中的 PE 标头位置指针。
        dos_header = stream.read(0x40)
        # 【通用】成品过短说明文件不完整。
        if len(dos_header) < 0x40:
            # 【通用】向上层报告损坏的成品文件。
            raise RuntimeError(f"成品文件不完整：{executable}")
        # 【通用】读取 PE 标头偏移量。
        pe_offset = int.from_bytes(dos_header[0x3C:0x40], "little")
        # 【通用】定位到 PE 标头。
        stream.seek(pe_offset)
        # 【通用】读取 PE 签名、COFF 头以及可选头中的子系统字段。
        pe_header = stream.read(4 + 20 + 70)
    # 【通用】校验 PE 签名，避免把非 Windows 可执行文件当成成品。
    if pe_header[:4] != b"PE\0\0":
        # 【通用】提示用户编译平台不支持生成 Windows 可执行文件。
        raise RuntimeError(f"成品不是有效的 Windows 可执行文件：{executable}")
    # 【通用】读取可选头类型标识，PE32 为 0x10B，PE32+ 为 0x20B。
    optional_magic = int.from_bytes(pe_header[4 + 20:4 + 22], "little")
    # 【通用】无法识别可选头时只提示警告，避免因格式差异误判而中断编译。
    if optional_magic not in (0x10B, 0x20B):
        # 【通用】说明本次静默校验已被跳过。
        print("警告：无法识别成品 PE 可选头，已跳过无控制台校验。")
        # 【通用】结束校验流程。
        return
    # 【通用】两种可选头格式的子系统字段都位于第 68 字节。
    subsystem_offset = 4 + 20 + 68
    # 【通用】读取两字节的子系统编号。
    subsystem = int.from_bytes(pe_header[subsystem_offset:subsystem_offset + 2], "little")
    # 【通用】2 表示 Windows 图形程序，启动时不会出现 CMD 视窗。
    if subsystem != 2:
        # 【通用】拒绝发布会弹出 CMD 视窗的控制台版本。
        raise RuntimeError(f"成品子系统为 {subsystem}，不是图形程序（2），会弹出 CMD 视窗；请确认编译参数保留 --windowed")


# 【通用】执行测试和单文件 EXE 打包。
def build() -> None:
    """【通用】把 Python、PySide6、OpenCV 和 NumPy 封装进独立 EXE。"""

    # 【通用】先检查旧版成品是否运行，避免耗时步骤完成后才因文件锁失败。
    ensure_output_is_available()
    # 【通用】拒绝不符合项目最低要求的 Python 版本。
    if sys.version_info < (3, 11):  # noqa: UP036
        # 【通用】提供明确的编译环境版本提示。
        raise RuntimeError("编译电脑必须安装 Python 3.11 或更新版本")
    # 【通用】安装项目运行依赖、测试工具和 PyInstaller。
    run_step(
        # 【通用】显示依赖安装阶段说明。
        "正在安装编译依赖",
        # 【通用】始终使用启动本脚本的同一个 Python 环境。
        [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
    )
    # 【通用】编译前运行全部测试，避免发布已知损坏版本。
    run_step(
        # 【通用】显示自动测试阶段说明。
        "正在执行自动测试",
        # 【通用】以模块方式调用 pytest，避免 PATH 缺少脚本目录。
        [sys.executable, "-m", "pytest", "-q"],
    )
    # 【通用】建立包含所有当前与后续自动化模块的 PyInstaller 参数。
    pyinstaller_arguments = [
        # 【通用】使用当前 Python 环境中的 PyInstaller。
        sys.executable,
        # 【通用】以模块方式启动 PyInstaller。
        "-m",
        # 【通用】指定编译器模块名称。
        "PyInstaller",
        # 【通用】允许覆盖上一次由本脚本生成的编译产物。
        "--noconfirm",
        # 【通用】清除 PyInstaller 分析缓存，避免旧依赖残留。
        "--clean",
        # 【通用】将全部运行文件封装成单一 EXE。
        "--onefile",
        # 【通用】生成无黑色控制台窗口的桌面程序。
        "--windowed",
        # 【通用】停用 UPX，降低目标电脑安全软件误报和兼容风险。
        "--noupx",
        # 【通用】设置最终成品名称。
        "--name",
        # 【通用】指定固定产品名称。
        "MonsterBox",
        # 【通用】让 PyInstaller 可以定位 src 布局的软件包。
        "--paths",
        # 【通用】加入项目源码目录。
        "src",
        # 【通用】强制收录尚未由界面直接调用的自动化与 OpenCV 模块。
        "--hidden-import",
        # 【通用】指定自动化任务模块。
        "monsterbox.services.automation",
        # 【通用】强制收录队伍编排模块。
        "--hidden-import",
        # 【通用】指定队伍编排模块。
        "monsterbox.services.orchestrator",
        # 【通用】指定桌面应用入口文件。
        "src/monsterbox/main.py",
    ]
    # 【通用】执行独立 EXE 编译。
    run_step("正在编译独立 EXE", pyinstaller_arguments)
    # 【通用】确认编译器实际生成目标文件。
    if not OUTPUT_EXE.is_file():
        # 【通用】缺少成品时报告明确错误而不是显示假成功。
        raise RuntimeError(f"编译结束但找不到成品：{OUTPUT_EXE}")
    # 【通用】确认成品是图形子系统程序，双击运行不会弹出 CMD 视窗。
    verify_windowed_executable(OUTPUT_EXE)
    # 【通用】显示静默校验结果。
    print("已确认成品为图形程序：启动模拟器等操作不会出现 CMD 视窗。")
    # 【通用】显示最终可复制到其他电脑的成品位置。
    print(f"\n编译完成：{OUTPUT_EXE}")
    # 【通用】说明目标电脑不需要安装 Python 依赖。
    print("目标电脑不需要安装 Python、PySide6、OpenCV 或 NumPy。")


# 【通用】执行编译并确保双击窗口在成功或失败后都不会闪退。
def main() -> int:
    """【通用】返回适合 BAT 判断的编译退出码。"""

    # 【通用】捕获命令失败和编译环境错误并显示原因。
    try:
        # 【通用】开始完整编译流程。
        build()
    # 【通用】处理外部命令非零退出和本脚本主动校验错误。
    except (subprocess.CalledProcessError, OSError, RuntimeError) as error:
        # 【通用】显示失败原因并保留上方命令输出。
        print(f"\n编译失败：{error}")
        # 【通用】设置失败退出码供自动化环境识别。
        exit_code = 1
    # 【通用】全部步骤成功时设置零退出码。
    else:
        # 【通用】零表示编译完成。
        exit_code = 0
    # 【通用】双击运行时等待用户按 Enter，防止窗口立即关闭。
    try:
        # 【通用】无论成功或失败都提供查看信息的时间。
        input("\n按 Enter 键关闭窗口...")
    # 【通用】持续集成或重定向输入时可能没有可读取的控制台。
    except EOFError:
        # 【通用】无交互输入时直接返回，不把它视为编译失败。
        pass
    # 【通用】返回最终编译状态。
    return exit_code


# 【通用】支持由 BAT 或命令行直接启动本脚本。
if __name__ == "__main__":
    # 【通用】将编译结果传给 Windows 命令处理器。
    raise SystemExit(main())
