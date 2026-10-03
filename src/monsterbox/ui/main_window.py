"""【通用】实现两队八窗口的 PySide6 可视化中控台。"""

# 【通用】导入可调用类型以描述后台任务。
from collections.abc import Callable
# 【通用】导入数据类替换工具以更新不可变应用配置。
from dataclasses import replace
# 【通用】导入路径类型以保存本机配置位置。
from pathlib import Path
# 【通用】导入 PySide6 核心信号和线程池组件。
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal
# 【通用】导入中控台所需界面控件，新增下拉框选择规则。
from PySide6.QtWidgets import QFileDialog, QGridLayout, QGroupBox, QHeaderView, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton, QPlainTextEdit, QComboBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
# 【通用】导入应用配置、资料夹搜索和持久化函数。
from monsterbox.config import AppSettings, find_ldplayer_tools, save_settings
# 【通用】导入固定角色定义。
from monsterbox.models import DeviceStatus, Role
# 【通用】导入统一ADB服务。
from monsterbox.services.adb import AdbService
# 【通用】导入雷电生命周期服务和实例表格模型。
from monsterbox.services.ldplayer import LdPlayerInstance, LdPlayerService
# 【通用】导入团队中控编排器。
from monsterbox.services.orchestrator import TeamOrchestrator
# 【通用】导入规则加载功能。
from monsterbox.services.rule_loader import TaskRule, create_example_rule, load_task_rule, scan_rule_directory


# 【通用】定义后台任务完成和失败信号，防止工作阻塞界面线程。
class WorkerSignals(QObject):
    """【通用】将后台任务结果安全传回 Qt 主线程。"""

    # 【通用】任务成功时发送描述文本。
    succeeded = Signal(str)
    # 【通用】任务失败时发送错误文本。
    failed = Signal(str)
    # 【通用】任务成功时传回服务层的结构化结果。
    result = Signal(object)


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
        # 【通用】保存各角色状态标签引用，供刷新时更新。
        self._status_labels: dict[tuple[int, Role], QLabel] = {}
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
        # 【通用】创建雷电模拟器多选表格作为主要操作入口。
        self._instance_table = QTableWidget(0, 6)
        # 【通用】设置多选框、索引、名称、状态、队伍和角色栏位。
        self._instance_table.setHorizontalHeaderLabels(["选择", "索引", "模拟器名称", "状态", "队伍", "角色"])
        # 【通用】禁止直接编辑雷电实例资料。
        self._instance_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # 【通用】让模拟器名称栏自动占用剩余宽度。
        self._instance_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
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
        # 【通用】先显示表格，再显示固定两队角色面板。
        layout.addWidget(self._instance_table, 1)
        # 【通用】将表格操作按钮放在表格下方。
        layout.addLayout(table_actions)
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
        # 【通用】启动时加载规则目录中的任务规则。
        self._load_rules_from_directory()
        # 【通用】工具路径有效时在启动后自动载入模拟器表格和设备状态。
        if settings.ldconsole_path.is_file():
            # 【通用】通过后台线程读取清单，避免启动时冻结界面。
            self._refresh_instance_table()
            # 【通用】自动刷新所有设备状态（自动获取ADB序列号）。
            self._refresh_all_statuses()

    # 【通用】刷新两队所有角色设备状态并更新UI。
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
            # 【通用】更新界面上的状态标签。
            for team_id, statuses in result.items():
                for role, status in statuses.items():
                    label = self._status_labels.get((team_id, role))
                    if label is not None:
                        label.setText(f"状态：{status.value}")
                        # 【通用】根据状态设置文字颜色提示。
                        if status is DeviceStatus.ONLINE:
                            label.setStyleSheet("color: green; font-weight: bold;")
                        elif status is DeviceStatus.OFFLINE:
                            label.setStyleSheet("color: gray;")
                        else:
                            label.setStyleSheet("color: red;")
            self._append_log("设备状态刷新完成")

        self._run_command("刷新设备状态", _do_refresh, _handle_result)

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
        # 【通用】保留刷新前已经勾选的实例索引。
        selected_before = set(self._selected_instance_indexes())
        # 【通用】移除旧行并按最新清单重新建立表格。
        self._instance_table.setRowCount(0)
        # 【通用】逐个显示所有雷电模拟器实例。
        for instance in result:
            # 【通用】忽略非预期实例类型，避免后台错误污染界面。
            if not isinstance(instance, LdPlayerInstance):
                # 【通用】继续处理下一条有效记录。
                continue
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
            # 【通用】根据安卓启动标志显示运行状态。
            status_text = "运行中" if instance.android_started else "未启动"
            # 【通用】将状态写入表格。
            self._instance_table.setItem(row, 3, QTableWidgetItem(status_text))
            # 【通用】查找当前实例是否已经绑定固定队伍角色。
            assignment = self._find_instance_assignment(instance.index)
            # 【通用】显示绑定队伍或未分配。
            self._instance_table.setItem(row, 4, QTableWidgetItem(str(assignment[0]) if assignment else "未分配"))
            # 【通用】显示绑定角色或未分配。
            self._instance_table.setItem(row, 5, QTableWidgetItem(assignment[1].value if assignment else "未分配"))

    # 【通用】查找实例索引对应的固定队伍与角色。
    def _find_instance_assignment(self, instance_index: int) -> tuple[int, Role] | None:
        """【通用】返回实例所属队伍角色，未绑定时返回空值。"""

        # 【通用】依次检查两支队伍。
        for team in self._settings.teams:
            # 【通用】依次检查队长、队员1及共享逻辑队员2/3。
            for role, binding in team.bindings.items():
                # 【通用】实例索引一致时返回对应关系。
                if binding.instance_index == instance_index:
                    # 【通用】返回固定队伍编号和角色。
                    return team.team_id, role
        # 【通用】没有任何绑定时返回空值。
        return None

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

    # 【通用】为指定队伍建立四角色控制面板。
    def _build_team_panel(self, team_id: int) -> QGroupBox:
        """【通用】返回包含队长、队员1、队员2、队员3的面板，显示实时状态。"""

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
            # 【通用】显示设备状态标签，后续可动态更新。
            status_label = QLabel(f"状态：{binding.status.value}")
            card_layout.addWidget(status_label)
            # 【通用】保存状态标签引用供刷新使用。
            self._status_labels[(team_id, role)] = status_label
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
    def _run_command(self, description: str, operation: Callable[[], object], result_handler: Callable[[object], None] | None = None) -> None:
        """【通用】在 Qt 线程池运行服务方法并按需处理结构化结果。"""

        # 【通用】创建一次性命令任务。
        worker = CommandWorker(description, operation)
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
