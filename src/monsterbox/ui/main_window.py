"""【通用】实现两队八窗口的 PySide6 可视化中控台。"""

# 【通用】导入可调用类型以描述后台任务。
from collections.abc import Callable
# 【通用】导入数据类替换工具以更新不可变应用配置。
from dataclasses import replace
# 【通用】导入路径类型以保存本机配置位置。
from pathlib import Path
# 【通用】导入 PySide6 核心信号和线程池组件。
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal
# 【通用】导入菜单动作与状态颜色，供列表右键指定队伍身份使用。
from PySide6.QtGui import QAction, QColor
# 【通用】导入中控台所需界面控件，新增右键菜单和身份栏位。
from PySide6.QtWidgets import QFileDialog, QHeaderView, QHBoxLayout, QLabel, QMainWindow, QMenu, QMessageBox, QPushButton, QPlainTextEdit, QComboBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
# 【通用】导入应用配置、资料夹搜索和持久化函数。
from monsterbox.config import AppSettings, find_ldplayer_tools, save_settings
# 【通用】导入固定角色定义和右键分配身份所需的队伍操作函数。
from monsterbox.models import DeviceBinding, DeviceStatus, Role, TeamConfig, clear_instance_assignment, find_assignment, reassign_instance
# 【通用】导入统一ADB服务。
from monsterbox.services.adb import AdbService
# 【通用】导入静默执行状态说明，启动时提示用户当前版本的静默策略。
from monsterbox.services.command import silent_execution_description
# 【通用】导入雷电生命周期服务和实例表格模型。
from monsterbox.services.ldplayer import LdPlayerInstance, LdPlayerService
# 【通用】导入团队中控编排器。
from monsterbox.services.orchestrator import TeamOrchestrator
# 【通用】导入规则加载功能。
from monsterbox.services.rule_loader import TaskRule, create_example_rule, load_task_rule, scan_rule_directory


# 【通用】定义设备状态在列表中的显示颜色，便于一眼区分在线情况。
_DEVICE_STATUS_COLORS: dict[DeviceStatus, str] = {
    # 【通用】尚未检查的设备使用灰色提示。
    DeviceStatus.UNKNOWN: "#808080",
    # 【通用】在线设备使用绿色表示可以执行任务。
    DeviceStatus.ONLINE: "#008000",
    # 【通用】离线设备使用灰色表示未启动或未连接。
    DeviceStatus.OFFLINE: "#808080",
    # 【通用】异常设备使用红色提醒用户排查。
    DeviceStatus.ERROR: "#c00000",
}

# 【通用】定义未指定身份的窗口文字颜色，提示用户需要右键设置。
_UNASSIGNED_TEXT_COLOR = "#808080"


# 【通用】定义后台任务完成和失败信号，防止工作阻塞界面线程。
class WorkerSignals(QObject):
    """【通用】将后台任务结果安全传回 Qt 主线程。"""

    # 【通用】任务成功时发送描述文本。
    succeeded = Signal(str)
    # 【通用】任务失败时发送错误文本。
    failed = Signal(str)
    # 【通用】任务成功时传回服务层的结构化结果。
    result = Signal(object)
    # 【通用】任务处理完毕时发出，用于释放主窗口持有的任务引用。
    finished = Signal()


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
                # 【通用】先传回结构化结果供表格等界面更新。
                self.signals.result.emit(result)
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
        # 【通用】无论成功或失败都通知主线程，便于释放任务引用。
        finally:
            # 【通用】排在结果和日志信号之后发出，保证投递顺序。
            self.signals.finished.emit()


# 【通用】展示两队八窗口并提供实例启动、关闭和日志反馈。
class MainWindow(QMainWindow):
    """【通用】MonsterBox 雷电模拟器可视化中控台主窗口。"""

    # 【通用】接收已加载配置、雷电服务和本机配置位置。
    def __init__(self, settings: AppSettings, ldplayer: LdPlayerService, settings_path: Path = Path("config/settings.json")) -> None:
        """【通用】建立固定两队四角色界面、中控同步功能和规则选择器。"""

        # 【通用】初始化 Qt 主窗口。
        super().__init__()
        # 【通用】保存配置供按钮闭包读取实例索引。
        self._settings = settings
        # 【通用】保存雷电服务，界面仅调用服务方法。
        self._ldplayer = ldplayer
        # 【通用】建立ADB服务供中控同步使用。
        self._adb = AdbService(settings.adb_path)
        # 【通用】建立团队编排器（中控核心）。
        self._orchestrator = TeamOrchestrator(self._adb, ldplayer, settings.teams)
        # 【通用】保存本机配置位置以持久化用户选择结果。
        self._settings_path = settings_path
        # 【通用】规则目录位于config/rules。
        self._rules_directory = settings_path.parent / "rules"
        # 【通用】缓存已加载规则，按名称索引。
        self._loaded_rules: dict[str, TaskRule] = {}
        # 【通用】当前选中的规则名称。
        self._selected_rule_name: str = ""
        # 【通用】缓存每个实例最近的 ADB 设备状态，供列表“设备状态”栏显示。
        self._device_statuses: dict[int, DeviceStatus] = {}
        # 【通用】缓存最近一次读取到的模拟器清单，右键分配身份后无需再次查询雷电。
        self._instances: list[LdPlayerInstance] = []
        # 【通用】持有正在运行的后台任务引用，避免任务对象被回收导致结果信号无法送达界面。
        self._active_workers: set[CommandWorker] = set()
        # 【通用】使用全局线程池执行外部命令。
        self._thread_pool = QThreadPool.globalInstance()
        # 【通用】设置包含项目版本职责的窗口标题。
        self.setWindowTitle("MonsterBox - 雷电模拟器两队中控台")
        # 【通用】设置适合展示八张角色卡片的初始尺寸。
        self.resize(1200, 800)
        # 【通用】创建中央容器承载队伍和日志区域。
        central = QWidget(self)
        # 【通用】创建垂直主布局。
        layout = QVBoxLayout(central)
        # 【通用】建立雷电安装资料夹选择区域。
        tools_layout = QHBoxLayout()
        # 【通用】建立当前 ldconsole 路径显示标签。
        self._tools_path_label = QLabel(f"ldconsole：{settings.ldconsole_path}")
        # 【通用】允许路径较长时选取复制完整内容。
        self._tools_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # 【通用】将路径显示加入工具区域并占用剩余宽度。
        tools_layout.addWidget(self._tools_path_label, 1)
        # 【通用】创建雷电安装资料夹浏览按钮。
        browse_button = QPushButton("选择雷电资料夹")
        # 【通用】点击后打开系统原生资料夹浏览框。
        browse_button.clicked.connect(self._choose_ldplayer_folder)
        # 【通用】将浏览按钮加入工具区域。
        tools_layout.addWidget(browse_button)
        # 【通用】将工具路径区域放在两队面板上方。
        layout.addLayout(tools_layout)
        # 【通用】建立中控操作区域：状态刷新、规则选择、任务启动。
        control_layout = QHBoxLayout()
        # 【通用】刷新设备状态按钮。
        refresh_status_button = QPushButton("刷新设备状态")
        refresh_status_button.clicked.connect(self._refresh_all_statuses)
        control_layout.addWidget(refresh_status_button)
        # 【通用】规则选择下拉框。
        control_layout.addWidget(QLabel("任务规则："))
        self._rule_combo = QComboBox()
        self._rule_combo.setMinimumWidth(200)
        control_layout.addWidget(self._rule_combo, 1)
        # 【通用】刷新规则列表按钮。
        refresh_rules_button = QPushButton("刷新规则")
        refresh_rules_button.clicked.connect(self._load_rules_from_directory)
        control_layout.addWidget(refresh_rules_button)
        # 【通用】生成示例规则按钮。
        example_rule_button = QPushButton("生成示例规则")
        example_rule_button.clicked.connect(self._create_example_rule_file)
        control_layout.addWidget(example_rule_button)
        # 【通用】启动任务按钮（对两队执行选中规则）。
        self._run_task_button = QPushButton("启动任务")
        self._run_task_button.clicked.connect(self._run_selected_task)
        control_layout.addWidget(self._run_task_button)
        # 【通用】停止任务按钮。
        stop_task_button = QPushButton("停止任务")
        stop_task_button.clicked.connect(self._stop_all_tasks)
        control_layout.addWidget(stop_task_button)
        # 【通用】将中控区域加入主布局。
        layout.addLayout(control_layout)
        # 【通用】创建雷电模拟器多选表格，作为启动窗口和指定身份的唯一入口。
        self._instance_table = QTableWidget(0, 7)
        # 【通用】设置多选框、索引、名称、运行状态、设备状态、队伍和身份栏位。
        self._instance_table.setHorizontalHeaderLabels(["选择", "索引", "模拟器名称", "运行状态", "设备状态", "队伍", "身份"])
        # 【通用】禁止直接编辑雷电实例资料。
        self._instance_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # 【通用】让模拟器名称栏自动占用剩余宽度。
        self._instance_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        # 【通用】启用自定义右键菜单，用于指定该窗口是第几队以及什么身份。
        self._instance_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # 【通用】把右键事件连接到菜单方法，界面层只组装菜单不执行外部命令。
        self._instance_table.customContextMenuRequested.connect(self._show_instance_context_menu)
        # 【通用】建立表格批量操作按钮区域。
        table_actions = QHBoxLayout()
        # 【通用】创建重新读取雷电模拟器清单按钮。
        refresh_button = QPushButton("刷新模拟器列表")
        # 【通用】点击后通过后台服务读取 list2。
        refresh_button.clicked.connect(self._refresh_instance_table)
        # 【通用】将刷新按钮加入批量操作区。
        table_actions.addWidget(refresh_button)
        # 【通用】创建启动所有勾选模拟器按钮。
        launch_selected_button = QPushButton("启动已选择")
        # 【通用】点击后仅启动复选框已勾选的实例。
        launch_selected_button.clicked.connect(lambda: self._run_selected_action("启动", self._ldplayer.launch))
        # 【通用】将批量启动按钮加入操作区。
        table_actions.addWidget(launch_selected_button)
        # 【通用】创建关闭所有勾选模拟器按钮。
        quit_selected_button = QPushButton("关闭已选择")
        # 【通用】点击后仅关闭复选框已勾选的实例。
        quit_selected_button.clicked.connect(lambda: self._run_selected_action("关闭", self._ldplayer.quit))
        # 【通用】将批量关闭按钮加入操作区。
        table_actions.addWidget(quit_selected_button)
        # 【通用】将剩余空间放在按钮右侧。
        table_actions.addStretch(1)
        # 【通用】显示操作说明，告诉用户如何指定每个窗口的队伍与身份。
        hint_label = QLabel("提示：在列表中右键某一行的模拟器，即可指定它属于第 1 队或第 2 队，身份可选择队长、队员1、队员2、队员3；四个身份的游戏逻辑各不相同，未指定身份的窗口不会执行任务。")
        # 【通用】允许提示文字自动换行以适配窄窗口。
        hint_label.setWordWrap(True)
        # 【通用】将提示放在表格上方。
        layout.addWidget(hint_label)
        # 【通用】把模拟器列表作为唯一窗口操作区域并占用主要空间。
        layout.addWidget(self._instance_table, 1)
        # 【通用】将表格操作按钮放在表格下方。
        layout.addLayout(table_actions)
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
        # 【通用】提示当前版本的静默执行状态，若看不到此行说明运行的是旧版本。
        self._append_log(silent_execution_description())
        # 【通用】启动时加载规则目录中的任务规则。
        self._load_rules_from_directory()
        # 【通用】工具路径有效时在启动后自动载入模拟器表格和设备状态。
        if settings.ldconsole_path.is_file():
            # 【通用】通过后台线程读取清单，避免启动时冻结界面。
            self._refresh_instance_table()
            # 【通用】自动刷新所有设备状态（自动获取ADB序列号）。
            self._refresh_all_statuses()

    # 【通用】刷新两队所有角色设备状态并更新列表。
    def _refresh_all_statuses(self) -> None:
        """【通用】通过中控编排器刷新8个设备的在线状态，自动获取ADB序列号。"""

        def _do_refresh() -> dict:
            # 【通用】依次刷新两队状态。
            results = {}
            for team_id in (1, 2):
                results[team_id] = self._orchestrator.refresh_statuses(team_id)
            return results

        def _handle_result(result: object) -> None:
            if not isinstance(result, dict):
                return
            # 【通用】把每个身份的设备状态按实例索引写入界面缓存。
            for team_id, statuses in result.items():
                for role, status in statuses.items():
                    # 【通用】查找该队伍身份当前的绑定。
                    binding = self._find_binding(team_id, role)
                    # 【通用】空位身份没有实例可以显示，直接跳过。
                    if binding is None or not binding.is_assigned:
                        continue
                    # 【通用】记录实例的最新状态供列表显示。
                    self._device_statuses[binding.instance_index] = status
            # 【通用】把最新状态刷新到列表的设备状态栏。
            self._apply_device_statuses_to_table()
            self._append_log("设备状态刷新完成")

        self._run_command("刷新设备状态", _do_refresh, _handle_result)

    # 【通用】查找指定队伍身份当前的绑定配置。
    def _find_binding(self, team_id: int, role: Role) -> DeviceBinding | None:
        """【通用】返回绑定对象供状态显示和右键菜单使用，队伍不存在时返回空值。"""

        # 【通用】依次查找队伍编号一致的分组。
        for team in self._settings.teams:
            # 【通用】命中队伍后返回该身份对应的绑定。
            if team.team_id == team_id:
                # 【通用】返回绑定对象，可能处于空位状态。
                return team.bindings[role]
        # 【通用】配置中不存在该队伍时返回空值。
        return None

    # 【通用】从规则目录加载所有任务规则到下拉框。
    def _load_rules_from_directory(self) -> None:
        """【通用】扫描config/rules目录，加载所有JSON规则文件。"""

        self._rule_combo.clear()
        self._loaded_rules.clear()
        # 【通用】确保规则目录存在。
        self._rules_directory.mkdir(parents=True, exist_ok=True)
        # 【通用】扫描目录中的JSON规则文件。
        rule_files = scan_rule_directory(self._rules_directory)
        if not rule_files:
            self._rule_combo.addItem("（无可用规则，请先生成或导入）")
            self._append_log(f"规则目录 {self._rules_directory} 中未找到任务规则")
            return
        # 【通用】逐个加载规则文件。
        loaded_count = 0
        for rule_file in rule_files:
            try:
                rule = load_task_rule(rule_file)
                self._loaded_rules[rule.name] = rule
                self._rule_combo.addItem(rule.name)
                loaded_count += 1
            except (OSError, ValueError, KeyError, TypeError) as error:
                self._append_log(f"加载规则 {rule_file.name} 失败：{error}")
        self._append_log(f"已加载 {loaded_count} 条任务规则")
        # 【通用】默认选中第一条规则。
        if self._rule_combo.count() > 0:
            self._selected_rule_name = self._rule_combo.itemText(0)

    # 【通用】在规则目录生成示例规则文件。
    def _create_example_rule_file(self) -> None:
        """【通用】生成示例任务规则供用户参考编辑。"""

        example_path = self._rules_directory / "示例任务.json"
        try:
            create_example_rule(example_path)
            self._append_log(f"已生成示例规则：{example_path}")
            # 【通用】重新加载规则列表。
            self._load_rules_from_directory()
        except OSError as error:
            QMessageBox.critical(self, "生成示例规则失败", str(error))

    # 【通用】获取当前下拉框选中的规则。
    def _get_selected_rule(self) -> TaskRule | None:
        """【通用】返回用户当前选择的任务规则。"""

        rule_name = self._rule_combo.currentText()
        return self._loaded_rules.get(rule_name)

    # 【通用】对两队执行当前选中的自动化任务。
    def _run_selected_task(self) -> None:
        """【通用】并行启动两队所有在线设备的自动化任务。"""

        rule = self._get_selected_rule()
        if rule is None:
            QMessageBox.information(self, "提示", "请先选择有效的任务规则")
            return
        # 【通用】先刷新一次状态确保ADB连接有效。
        def _do_run() -> dict:
            results = {}
            for team_id in (1, 2):
                # 【通用】执行前先刷新状态确保序列号有效。
                self._orchestrator.refresh_statuses(team_id)
                # 【通用】启动该队伍自动化。
                results[team_id] = self._orchestrator.run_team_automation(
                    team_id,
                    rule.leader_steps,
                    rule.member1_steps,
                    rule.shared_member_steps,
                )
            return results

        def _handle_result(result: object) -> None:
            if not isinstance(result, dict):
                return
            self._append_log(f"任务 [{rule.name}] 执行完成")
            for team_id, role_results in result.items():
                for role, success in role_results.items():
                    status = "成功" if success else "失败/跳过"
                    self._append_log(f"  第{team_id}队 {role.value}: {status}")
            # 【通用】刷新状态显示。
            self._refresh_all_statuses()

        self._append_log(f"开始执行任务：{rule.name} - {rule.description}")
        self._run_command(f"执行任务 {rule.name}", _do_run, _handle_result)

    # 【通用】停止所有正在运行的任务。
    def _stop_all_tasks(self) -> None:
        """【通用】请求两队所有自动化运行器停止。"""

        for team_id in (1, 2):
            self._orchestrator.stop_team_automation(team_id)
        self._append_log("已发送停止信号，正在终止所有运行中任务...")

    # 【通用】窗口关闭时清理中控资源。
    def closeEvent(self, event) -> None:
        """【通用】确保窗口关闭时停止所有后台任务。"""
        self._orchestrator.shutdown()
        super().closeEvent(event)

    # 【通用】打开资料夹浏览框并自动寻找雷电控制工具。
    def _choose_ldplayer_folder(self) -> None:
        """【通用】选择安装资料夹、自动寻找工具并保存配置。"""

        # 【通用】存在当前工具目录时将其作为浏览框起点。
        current_directory = self._settings.ldconsole_path.parent
        # 【通用】无有效当前目录时从用户主资料夹开始选择。
        initial_directory = current_directory if current_directory.is_dir() else Path.home()
        # 【通用】打开系统原生资料夹选择框，让用户只需选择雷电目录。
        selected = QFileDialog.getExistingDirectory(
            # 【通用】将主窗口设置为对话框父对象。
            self,
            # 【通用】显示清晰的中文选择提示。
            "选择雷电模拟器安装资料夹",
            # 【通用】传入建议的初始浏览位置。
            str(initial_directory),
        )
        # 【通用】用户取消选择时不修改任何现有配置。
        if not selected:
            # 【通用】直接结束本次选择流程。
            return
        # 【通用】在所选资料夹和子目录内自动搜索 ldconsole 与 ADB。
        tools = find_ldplayer_tools(Path(selected))
        # 【通用】缺少任一工具时保留旧配置并提示重新选择。
        if tools is None:
            # 【通用】以警告框说明所需文件名称。
            QMessageBox.warning(
                # 【通用】将主窗口设置为提示框父对象。
                self,
                # 【通用】设置简短警告标题。
                "没有找到雷电工具",
                # 【通用】说明程序已经搜索所选资料夹及其子目录。
                "所选资料夹内找不到 ldconsole.exe 和 adb.exe，请选择雷电模拟器安装资料夹。",
            )
            # 【通用】停止后续路径更新和持久化。
            return
        # 【通用】拆分自动找到的控制台与 ADB 路径。
        ldconsole_path, adb_path = tools
        # 【通用】保留两队配置，仅替换外部工具路径。
        updated_settings = replace(
            # 【通用】以当前配置作为不可变替换来源。
            self._settings,
            # 【通用】写入自动发现的控制台路径。
            ldconsole_path=ldconsole_path,
            # 【通用】写入自动发现的 ADB 路径。
            adb_path=adb_path,
        )
        # 【通用】捕获配置保存错误，避免显示已应用但实际未保存。
        try:
            # 【通用】将选择结果写入忽略版本控制的本机配置。
            save_settings(self._settings_path, updated_settings)
        # 【通用】处理目录权限或磁盘写入异常。
        except OSError as error:
            # 【通用】向用户显示保存失败原因。
            QMessageBox.critical(self, "保存配置失败", str(error))
            # 【通用】保存失败时不替换当前运行配置。
            return
        # 【通用】更新主窗口持有的应用配置。
        self._settings = updated_settings
        # 【通用】关闭旧编排器释放资源。
        self._orchestrator.shutdown()
        # 【通用】使用新路径重建雷电服务供后续按钮调用。
        self._ldplayer = LdPlayerService(ldconsole_path)
        # 【通用】重建ADB服务使用新路径。
        self._adb = AdbService(adb_path)
        # 【通用】重建团队编排器。
        self._orchestrator = TeamOrchestrator(self._adb, self._ldplayer, updated_settings.teams)
        # 【通用】更新界面上的控制台路径文字。
        self._tools_path_label.setText(f"ldconsole：{ldconsole_path}")
        # 【通用】将自动发现结果写入可视化日志。
        self._append_log(f"已自动找到 ldconsole：{ldconsole_path}")
        # 【通用】将自动发现的 ADB 路径写入日志。
        self._append_log(f"已自动找到 ADB：{adb_path}")
        # 【通用】新路径应用后立即读取可勾选模拟器清单和设备状态。
        self._refresh_instance_table()
        self._refresh_all_statuses()

    # 【通用】通过后台服务刷新模拟器多选表格。
    def _refresh_instance_table(self) -> None:
        """【通用】读取 ldconsole list2 并更新可勾选实例。"""

        # 【通用】将服务查询送入线程池，结果交给表格填充方法。
        self._run_command("刷新模拟器列表", self._ldplayer.get_instances, self._populate_instance_table)

    # 【通用】使用结构化雷电实例资料填充多选表格。
    def _populate_instance_table(self, result: object) -> None:
        """【通用】显示实例名称、运行状态及已配置的队伍角色。"""

        # 【通用】只接受服务层返回的实例清单。
        if not isinstance(result, list):
            # 【通用】非清单结果不修改当前表格。
            return
        # 【通用】过滤非预期实例类型，避免后台错误污染界面。
        instances = [instance for instance in result if isinstance(instance, LdPlayerInstance)]
        # 【通用】缓存清单，右键指定身份后可直接重建表格而无需重新查询雷电。
        self._instances = instances
        # 【通用】保留刷新前已经勾选的实例索引。
        selected_before = set(self._selected_instance_indexes())
        # 【通用】移除旧行并按最新清单重新建立表格。
        self._instance_table.setRowCount(0)
        # 【通用】逐个显示所有雷电模拟器实例。
        for instance in instances:
            # 【通用】在表格尾端新增一行。
            row = self._instance_table.rowCount()
            # 【通用】扩大表格行数以容纳当前实例。
            self._instance_table.insertRow(row)
            # 【通用】建立可勾选但不可编辑的选择项目。
            selection_item = QTableWidgetItem()
            # 【通用】启用复选框和选择功能。
            selection_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            # 【通用】刷新时恢复该实例原来的勾选状态。
            selection_item.setCheckState(Qt.CheckState.Checked if instance.index in selected_before else Qt.CheckState.Unchecked)
            # 【通用】把实例索引保存到项目数据，避免依赖显示文字解析。
            selection_item.setData(Qt.ItemDataRole.UserRole, instance.index)
            # 【通用】将多选框加入第一栏。
            self._instance_table.setItem(row, 0, selection_item)
            # 【通用】显示雷电实例索引。
            self._instance_table.setItem(row, 1, QTableWidgetItem(str(instance.index)))
            # 【通用】显示用户设置的模拟器名称。
            self._instance_table.setItem(row, 2, QTableWidgetItem(instance.name))
            # 【通用】根据安卓启动标志显示窗口运行状态。
            running_text = "运行中" if instance.android_started else "未启动"
            # 【通用】将运行状态写入表格。
            self._instance_table.setItem(row, 3, QTableWidgetItem(running_text))
            # 【通用】显示该实例最近一次 ADB 设备状态，默认未知。
            self._instance_table.setItem(row, 4, self._build_device_status_item(instance.index))
            # 【通用】查找当前实例被分配到的队伍与身份。
            assignment = find_assignment(self._settings.teams, instance.index)
            # 【通用】显示所属队伍，未指定身份时提示用户右键设置。
            team_item = QTableWidgetItem(f"第 {assignment[0]} 队" if assignment else "未分配")
            # 【通用】未分配窗口使用灰色文字提示需要右键指定身份。
            if assignment is None:
                # 【通用】设置提示颜色。
                team_item.setForeground(QColor(_UNASSIGNED_TEXT_COLOR))
                # 【通用】说明未分配窗口不会执行任务。
                team_item.setToolTip("右键该行可以指定队伍与身份，未指定身份的窗口不会执行任务")
            # 【通用】将队伍写入表格。
            self._instance_table.setItem(row, 5, team_item)
            # 【通用】显示身份，未分配时同样提示。
            role_item = QTableWidgetItem(assignment[1].value if assignment else "未分配")
            # 【通用】在身份栏显示该身份对应的游戏逻辑说明。
            if assignment is not None:
                # 【通用】说明不同身份的游戏逻辑差异。
                role_item.setToolTip(assignment[1].logic_description)
            # 【通用】将身份写入表格。
            self._instance_table.setItem(row, 6, role_item)

    # 【通用】建立显示设备状态的表格项目。
    def _build_device_status_item(self, instance_index: int) -> QTableWidgetItem:
        """【通用】读取状态缓存并套用颜色，供表格和状态刷新共同使用。"""

        # 【通用】没有检查记录时显示未知状态。
        status = self._device_statuses.get(instance_index, DeviceStatus.UNKNOWN)
        # 【通用】建立状态文字项目。
        item = QTableWidgetItem(status.value)
        # 【通用】按在线情况设置文字颜色。
        item.setForeground(QColor(_DEVICE_STATUS_COLORS[status]))
        # 【通用】返回可直接加入表格的项目。
        return item

    # 【通用】把设备状态缓存刷新到列表的设备状态栏。
    def _apply_device_statuses_to_table(self) -> None:
        """【通用】状态刷新完成后调用，只更新文字不重建整张表格。"""

        # 【通用】逐行读取实例索引。
        for row in range(self._instance_table.rowCount()):
            # 【通用】从选择项目读取真实实例索引。
            instance_index = self._instance_index_at_row(row)
            # 【通用】索引缺失时跳过该行。
            if instance_index is None:
                # 【通用】继续处理下一行。
                continue
            # 【通用】用最新状态替换当前单元格。
            self._instance_table.setItem(row, 4, self._build_device_status_item(instance_index))

    # 【通用】读取表格某一行保存的雷电实例索引。
    def _instance_index_at_row(self, row: int) -> int | None:
        """【通用】右键菜单和状态刷新都依赖该索引，避免解析显示文字。"""

        # 【通用】读取第一栏保存实例索引的选择项目。
        item = self._instance_table.item(row, 0)
        # 【通用】该行缺少选择项目时返回空值。
        if item is None:
            # 【通用】向上层报告无法识别的行。
            return None
        # 【通用】读取选择项目中保存的实例索引。
        data = item.data(Qt.ItemDataRole.UserRole)
        # 【通用】项目数据缺失时同样视为无法识别。
        if data is None:
            # 【通用】向上层报告缺少实例索引的行。
            return None
        # 【通用】把项目数据转换为整数索引。
        return int(data)

    # 【通用】在列表行上弹出右键菜单，用于指定队伍与身份。
    def _show_instance_context_menu(self, position) -> None:
        """【通用】菜单结构为“第 1 队/第 2 队 → 队长/队员1/队员2/队员3”。"""

        # 【通用】定位用户点击的表格行。
        row = self._instance_table.rowAt(position.y())
        # 【通用】点击表格空白区域时不显示菜单。
        if row < 0:
            # 【通用】直接结束本次右键操作。
            return
        # 【通用】读取该行对应的雷电实例索引。
        instance_index = self._instance_index_at_row(row)
        # 【通用】无法识别实例时终止，避免误分配给其他窗口。
        if instance_index is None:
            # 【通用】直接结束本次右键操作。
            return
        # 【通用】读取实例名称用于菜单标题。
        name_item = self._instance_table.item(row, 2)
        # 【通用】名称缺失时使用空文字兜底。
        instance_name = name_item.text() if name_item is not None else ""
        # 【通用】建立右键菜单。
        menu = QMenu(self)
        # 【通用】标题行只显示当前实例，不允许点击。
        title_action = QAction(f"实例 {instance_index}：{instance_name}", self)
        # 【通用】禁用标题避免被误当成可执行操作。
        title_action.setEnabled(False)
        # 【通用】把标题加入菜单。
        menu.addAction(title_action)
        # 【通用】在标题和身份选项之间加分隔线。
        menu.addSeparator()
        # 【通用】查询该实例当前的身份，用于在菜单中打勾。
        current = find_assignment(self._settings.teams, instance_index)
        # 【通用】两支队伍分别建立身份子菜单，身份决定游戏逻辑。
        for team_id in (1, 2):
            # 【通用】建立队伍子菜单。
            team_menu = menu.addMenu(f"第 {team_id} 队")
            # 【通用】四种身份的游戏逻辑互不相同，逐个列出。
            for role in Role:
                # 【通用】读取该身份当前占用的实例，用于显示空位或已占用实例。
                binding = self._find_binding(team_id, role)
                # 【通用】空位显示“空位”，已占用显示实例编号便于换位。
                occupied = binding.instance_index if binding is not None and binding.is_assigned else None
                # 【通用】组装子菜单文字。
                label = f"{role.value}（实例 {occupied}）" if occupied is not None else f"{role.value}（空位）"
                # 【通用】建立可选择身份的动作。
                role_action = QAction(label, self)
                # 【通用】允许打勾显示该实例当前身份。
                role_action.setCheckable(True)
                # 【通用】当前身份与菜单项一致时打勾。
                role_action.setChecked(current == (team_id, role))
                # 【通用】在悬停提示中说明该身份的游戏逻辑。
                role_action.setToolTip(role.logic_description)
                # 【通用】点击后把实例分配到该队伍身份。
                role_action.triggered.connect(lambda _checked=False, tid=team_id, selected_role=role: self._assign_instance(instance_index, tid, selected_role))
                # 【通用】把身份选项加入队伍子菜单。
                team_menu.addAction(role_action)
        # 【通用】在身份选项后加分隔线。
        menu.addSeparator()
        # 【通用】提供单个窗口的启动操作，替代原先的八格卡片按钮。
        launch_action = QAction("启动窗口", self)
        # 【通用】通过后台线程调用雷电服务启动该实例。
        launch_action.triggered.connect(lambda _checked=False, index=instance_index: self._run_command(f"实例 {index} 启动", lambda: self._ldplayer.launch(index)))
        # 【通用】把启动操作加入菜单。
        menu.addAction(launch_action)
        # 【通用】提供单个窗口的关闭操作。
        quit_action = QAction("关闭窗口", self)
        # 【通用】通过后台线程调用雷电服务关闭该实例。
        quit_action.triggered.connect(lambda _checked=False, index=instance_index: self._run_command(f"实例 {index} 关闭", lambda: self._ldplayer.quit(index)))
        # 【通用】把关闭操作加入菜单。
        menu.addAction(quit_action)
        # 【通用】已分配身份的实例才提供取消分配。
        if current is not None:
            # 【通用】在操作区前加分隔线。
            menu.addSeparator()
            # 【通用】建立取消分配动作。
            unassign_action = QAction("取消分配身份", self)
            # 【通用】点击后清空该实例占用的身份。
            unassign_action.triggered.connect(lambda _checked=False, index=instance_index: self._clear_instance_assignment(index))
            # 【通用】把取消分配加入菜单。
            menu.addAction(unassign_action)
        # 【通用】在鼠标位置弹出菜单。
        menu.exec(self._instance_table.viewport().mapToGlobal(position))

    # 【通用】把实例分配到指定队伍身份并持久化。
    def _assign_instance(self, instance_index: int, team_id: int, role: Role) -> None:
        """【通用】目标身份已占用时与占用者互换，空位时直接填入。"""

        # 【通用】查询该实例当前身份，避免重复操作。
        if find_assignment(self._settings.teams, instance_index) == (team_id, role):
            # 【通用】提示用户无需修改。
            self._append_log(f"实例 {instance_index} 已经是第 {team_id} 队 {role.value}")
            # 【通用】直接结束。
            return
        # 【通用】按游戏逻辑把实例分配到目标身份。
        try:
            # 【通用】队伍模型负责交换或填入空位。
            updated_teams = reassign_instance(self._settings.teams, instance_index, team_id, role)
        # 【通用】捕获参数错误并提示用户。
        except ValueError as error:
            # 【通用】显示明确错误而不修改配置。
            QMessageBox.warning(self, "指定身份失败", str(error))
            # 【通用】结束分配流程。
            return
        # 【通用】保存配置并刷新列表显示。
        self._apply_team_configuration(updated_teams, f"实例 {instance_index} 已指定为第 {team_id} 队 {role.value}（{role.logic_description}）")

    # 【通用】取消实例的队伍身份。
    def _clear_instance_assignment(self, instance_index: int) -> None:
        """【通用】取消后该实例不再属于任何队伍，任务不会在它上面执行。"""

        # 【通用】未分配身份的实例无需处理。
        if find_assignment(self._settings.teams, instance_index) is None:
            # 【通用】提示用户当前状态。
            self._append_log(f"实例 {instance_index} 尚未分配队伍身份")
            # 【通用】直接结束。
            return
        # 【通用】把该实例占用的身份全部置为空位。
        updated_teams = clear_instance_assignment(self._settings.teams, instance_index)
        # 【通用】保存配置并刷新列表显示。
        self._apply_team_configuration(updated_teams, f"实例 {instance_index} 已取消分配身份")

    # 【通用】保存调整后的队伍身份并同步给中控编排器。
    def _apply_team_configuration(self, updated_teams: tuple[TeamConfig, ...], message: str) -> None:
        """【通用】仅替换队伍绑定，保留工具路径和正在运行的任务。"""

        # 【通用】保留外部工具路径，只替换两队的角色绑定。
        updated_settings = replace(self._settings, teams=updated_teams)
        # 【通用】捕获配置写入错误，避免显示已生效但实际未保存。
        try:
            # 【通用】把右键选择结果写入本机配置。
            save_settings(self._settings_path, updated_settings)
        # 【通用】处理目录权限或磁盘写入异常。
        except OSError as error:
            # 【通用】向用户显示保存失败原因。
            QMessageBox.critical(self, "保存配置失败", str(error))
            # 【通用】保存失败时不应用本次调整。
            return
        # 【通用】更新主窗口持有的应用配置。
        self._settings = updated_settings
        # 【通用】把最新绑定同步给编排器，保留线程池和运行中的任务。
        self._orchestrator.apply_teams(updated_teams)
        # 【通用】在日志区记录本次身份调整。
        self._append_log(message)
        # 【通用】使用缓存的模拟器清单重建列表，立即显示最新队伍与身份。
        self._populate_instance_table(self._instances)

    # 【通用】取得表格中所有已勾选模拟器索引。
    def _selected_instance_indexes(self) -> list[int]:
        """【通用】按表格顺序返回多选框已勾选的实例。"""

        # 【通用】准备保存用户选择结果。
        selected: list[int] = []
        # 【通用】逐行检查第一栏复选框。
        for row in range(self._instance_table.rowCount()):
            # 【通用】读取当前行的选择项目。
            item = self._instance_table.item(row, 0)
            # 【通用】仅处理存在且已勾选的项目。
            if item is not None and item.checkState() is Qt.CheckState.Checked:
                # 【通用】读取项目中保存的真实实例索引。
                selected.append(int(item.data(Qt.ItemDataRole.UserRole)))
        # 【通用】返回全部勾选实例。
        return selected

    # 【通用】对所有勾选模拟器执行启动或关闭服务操作。
    def _run_selected_action(self, action_name: str, operation: Callable[[int], object]) -> None:
        """【通用】批量操作多选实例，单一失败不阻塞其他实例。"""

        # 【通用】读取用户当前勾选的全部实例。
        indexes = self._selected_instance_indexes()
        # 【通用】未勾选任何实例时提供明确提示。
        if not indexes:
            # 【通用】在日志区说明需要先勾选表格项目。
            self._append_log("请先在表格勾选至少一个模拟器")
            # 【通用】停止空批量操作。
            return
        # 【通用】为每个勾选实例建立独立后台任务。
        for instance_index in indexes:
            # 【通用】绑定当前索引，避免循环闭包引用最后一个值。
            self._run_command(
                # 【通用】提供包含实例索引的日志说明。
                f"实例 {instance_index} {action_name}",
                # 【通用】调用服务层启动或关闭函数。
                lambda index=instance_index: operation(index),
            )

    # 【通用】提交后台控制任务并连接日志信号。
    def _run_command(self, description: str, operation: Callable[[], object], result_handler: Callable[[object], None] | None = None) -> None:
        """【通用】在 Qt 线程池运行服务方法并按需处理结构化结果。"""

        # 【通用】创建一次性命令任务。
        worker = CommandWorker(description, operation)
        # 【通用】保存任务引用，防止任务在线程池执行期间被回收而丢失结果信号。
        self._active_workers.add(worker)
        # 【通用】任务收尾后释放引用，避免长期占用内存。
        worker.signals.finished.connect(lambda: self._active_workers.discard(worker))
        # 【通用】调用方提供结果处理器时连接结构化结果信号。
        if result_handler is not None:
            # 【通用】确保表格更新等操作回到 Qt 主线程执行。
            worker.signals.result.connect(result_handler)
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
