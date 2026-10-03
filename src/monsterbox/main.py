"""【通用】启动 MonsterBox 两队八窗口可视化中控台。"""

# 【通用】导入系统参数供 Qt 应用初始化。
import sys
# 【通用】导入路径工具定位本机配置文件。
from pathlib import Path
# 【通用】导入 PySide6 应用对象。
from PySide6.QtWidgets import QApplication, QMessageBox
# 【通用】导入配置加载函数。
from monsterbox.config import load_settings
# 【通用】导入雷电生命周期服务。
from monsterbox.services.ldplayer import LdPlayerService
# 【通用】导入主窗口。
from monsterbox.ui.main_window import MainWindow


# 【通用】取得源码运行或独立 EXE 对应的应用目录。
def get_application_directory() -> Path:
    """【通用】确保配置始终保存在 EXE 旁，而不是不确定的工作目录。"""

    # 【通用】PyInstaller 独立程序会设置 frozen 标记。
    if getattr(sys, "frozen", False):
        # 【通用】独立 EXE 使用可执行文件所在资料夹作为应用目录。
        return Path(sys.executable).resolve().parent
    # 【通用】源码运行时使用当前项目工作目录保持既有开发行为。
    return Path.cwd()


# 【通用】建立并运行桌面应用。
def main() -> int:
    """【通用】加载配置、建立服务并进入 Qt 事件循环。"""

    # 【通用】创建 Qt 应用并传入系统启动参数。
    application = QApplication(sys.argv)
    # 【通用】定位源码目录或 EXE 旁的本机配置文件。
    settings_path = get_application_directory() / "config" / "settings.json"
    # 【通用】捕获配置错误并以图形方式提示用户。
    try:
        # 【通用】读取两队八窗口设置。
        settings = load_settings(settings_path)
    # 【通用】处理文件、JSON 和结构校验异常。
    except (OSError, ValueError, KeyError, TypeError) as error:
        # 【通用】显示配置错误而不产生无界面崩溃。
        QMessageBox.critical(None, "配置错误", str(error))
        # 【通用】返回失败退出码供脚本或 IDE 识别。
        return 1
    # 【通用】使用配置路径建立雷电服务。
    ldplayer = LdPlayerService(settings.ldconsole_path)
    # 【通用】建立可视化中控台主窗口并提供本机配置保存位置。
    window = MainWindow(settings, ldplayer, settings_path)
    # 【通用】显示主窗口。
    window.show()
    # 【通用】进入 Qt 事件循环并返回最终退出码。
    return application.exec()


# 【通用】支持直接运行模块启动应用。
if __name__ == "__main__":
    # 【通用】将应用退出码传给操作系统。
    raise SystemExit(main())
