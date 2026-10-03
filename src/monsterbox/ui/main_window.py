"""【通用】实现两队八窗口的 PySide6 可视化中控台。"""

# 【通用】导入可调用类型以描述后台任务。
from collections.abc import Callable
# 【通用】导入 PySide6 核心信号和线程池组件。
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
# 【通用】导入中控台所需界面控件。
from PySide6.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QPushButton, QPlainTextEdit, QVBoxLayout, QWidget
# 【通用】导入应用配置模型。
from monsterbox.config import AppSettings
# 【通用】导入固定角色定义。
from monsterbox.models import Role
# 【通用】导入雷电生命周期服务。
from monsterbox.services.ldplayer import LdPlayerService


# 【通用】定义后台任务完成和失败信号，防止工作阻塞界面线程。
class WorkerSignals(QObject):
    """【通用】将后台任务结果安全传回 Qt 主线程。"""

    # 【通用】任务成功时发送描述文本。
    succeeded = Signal(str)
    # 【通用】任务失败时发送错误文本。
    failed = Signal(str)


# 【通用】在线程池执行单个可停止边界明确的控制命令。
class CommandWorker(QRunnable):
    """【通用】执行由服务层封装的短时外部命令。"""

    # 【通用】保存任务说明和无参数任务函数。
    def __init__(self, description: str, operation: Callable[[], object]) -> None:
        """【通用】初始化后台命令任务。"""

        # 【通用】完成 Qt 工作任务基类初始化。
        super().__init__()
        # 【通用】保存用于日志显示的任务说明。
        self._description = description
        # 【通用】保存服务层操作，界面不直接执行外部命令。
        self._operation = operation
        # 【通用】建立跨线程结果信号。
        self.signals = WorkerSignals()

    # 【通用】由 Qt 线程池调用任务入口。
    def run(self) -> None:
        """【通用】执行服务操作并发送结果。"""

        # 【通用】捕获外部工具和配置异常，避免线程静默退出。
        try:
            # 【通用】调用已经封装超时的服务层操作。
            result = self._operation()
            # 【通用】读取服务结果的成功属性，不依赖具体结果类型。
            succeeded = bool(getattr(result, "succeeded", True))
            # 【通用】成功时向主线程发送完成日志。
            if succeeded:
                # 【通用】说明任务已正常完成。
                self.signals.succeeded.emit(f"{self._description}：成功")
            # 【通用】非零退出结果作为失败处理。
            else:
                # 【通用】提取错误输出供用户排查。
                error = getattr(result, "stderr", "命令执行失败")
                # 【通用】发送失败详情到主线程。
                self.signals.failed.emit(f"{self._description}：{error}")
        # 【通用】统一处理系统命令和配置层可预期异常。
        except (OSError, ValueError, RuntimeError) as error:
            # 【通用】将异常转换为中文日志而不终止应用。
            self.signals.failed.emit(f"{self._description}：{error}")


# 【通用】展示两队八窗口并提供实例启动、关闭和日志反馈。
class MainWindow(QMainWindow):
    """【通用】MonsterBox 雷电模拟器可视化中控台主窗口。"""

    # 【通用】接收已加载配置和雷电服务。
    def __init__(self, settings: AppSettings, ldplayer: LdPlayerService) -> None:
        """【通用】建立固定两队四角色界面。"""

        # 【通用】初始化 Qt 主窗口。
        super().__init__()
        # 【通用】保存配置供按钮闭包读取实例索引。
        self._settings = settings
        # 【通用】保存雷电服务，界面仅调用服务方法。
        self._ldplayer = ldplayer
        # 【通用】使用全局线程池执行外部命令。
        self._thread_pool = QThreadPool.globalInstance()
        # 【通用】设置包含项目版本职责的窗口标题。
        self.setWindowTitle("MonsterBox - 雷电模拟器两队中控台")
        # 【通用】设置适合展示八张角色卡片的初始尺寸。
        self.resize(1100, 720)
        # 【通用】创建中央容器承载队伍和日志区域。
        central = QWidget(self)
        # 【通用】创建垂直主布局。
        layout = QVBoxLayout(central)
        # 【通用】建立两队横向排列区域。
        teams_layout = QHBoxLayout()
        # 【通用】为第 1 队和第 2 队分别建立角色面板。
        for team in self._settings.teams:
            # 【通用】将队伍面板加入横向布局。
            teams_layout.addWidget(self._build_team_panel(team.team_id))
        # 【通用】将两队区域加入主布局并占主要空间。
        layout.addLayout(teams_layout, 1)
        # 【通用】创建只读日志区域反馈后台任务状态。
        self._log = QPlainTextEdit()
        # 【通用】禁止用户误改运行日志。
        self._log.setReadOnly(True)
        # 【通用】限制日志高度以保留角色卡片空间。
        self._log.setMaximumBlockCount(500)
        # 【通用】将日志区加入主布局。
        layout.addWidget(self._log)
        # 【通用】设置完成的中央容器。
        self.setCentralWidget(central)
        # 【通用】提示用户当前工具配置路径。
        self._append_log(f"ldconsole：{settings.ldconsole_path}")
        # 【通用】提示用户当前 ADB 配置路径。
        self._append_log(f"ADB：{settings.adb_path}")

    # 【通用】为指定队伍建立四角色控制面板。
    def _build_team_panel(self, team_id: int) -> QGroupBox:
        """【通用】返回包含队长、队员1、队员2、队员3的面板。"""

        # 【通用】读取目标队伍配置。
        team = next(item for item in self._settings.teams if item.team_id == team_id)
        # 【通用】创建带队号标题的分组框。
        panel = QGroupBox(f"第 {team_id} 队")
        # 【通用】使用两行两列展示四个角色。
        grid = QGridLayout(panel)
        # 【通用】按固定枚举顺序生成角色卡片。
        for position, role in enumerate(Role):
            # 【通用】取得角色绑定的雷电实例索引。
            binding = team.bindings[role]
            # 【通用】创建当前角色卡片容器。
            card = QGroupBox(role.value)
            # 【通用】建立卡片垂直布局。
            card_layout = QVBoxLayout(card)
            # 【通用】显示角色对应实例索引。
            card_layout.addWidget(QLabel(f"实例索引：{binding.instance_index}"))
            # 【通用】显示队员2与3共用策略说明。
            strategy = "共享成员逻辑" if role.uses_shared_member_logic else "独立角色逻辑"
            # 【通用】将策略说明加入卡片。
            card_layout.addWidget(QLabel(f"策略：{strategy}"))
            # 【通用】创建启动按钮。
            launch_button = QPushButton("启动窗口")
            # 【通用】绑定实例索引并将启动任务送入后台线程。
            launch_button.clicked.connect(lambda _checked=False, index=binding.instance_index, label=f"第 {team_id} 队 {role.value}": self._run_command(f"{label} 启动", lambda: self._ldplayer.launch(index)))
            # 【通用】将启动按钮加入卡片。
            card_layout.addWidget(launch_button)
            # 【通用】创建关闭按钮。
            quit_button = QPushButton("关闭窗口")
            # 【通用】绑定实例索引并将关闭任务送入后台线程。
            quit_button.clicked.connect(lambda _checked=False, index=binding.instance_index, label=f"第 {team_id} 队 {role.value}": self._run_command(f"{label} 关闭", lambda: self._ldplayer.quit(index)))
            # 【通用】将关闭按钮加入卡片。
            card_layout.addWidget(quit_button)
            # 【通用】按两列位置加入队伍网格。
            grid.addWidget(card, position // 2, position % 2)
        # 【通用】返回完整队伍面板。
        return panel

    # 【通用】提交后台控制任务并连接日志信号。
    def _run_command(self, description: str, operation: Callable[[], object]) -> None:
        """【通用】在 Qt 线程池运行服务方法。"""

        # 【通用】创建一次性命令任务。
        worker = CommandWorker(description, operation)
        # 【通用】将成功消息连接至日志区域。
        worker.signals.succeeded.connect(self._append_log)
        # 【通用】将失败消息连接至日志区域。
        worker.signals.failed.connect(self._append_log)
        # 【通用】开始后台任务，保持主界面可响应。
        self._thread_pool.start(worker)

    # 【通用】将带时间顺序的文本追加到可视化日志。
    def _append_log(self, message: str) -> None:
        """【通用】显示任务状态，且不记录任何敏感信息。"""

        # 【通用】以纯文本追加日志，避免解释外部工具输出中的 HTML。
        self._log.appendPlainText(message)
