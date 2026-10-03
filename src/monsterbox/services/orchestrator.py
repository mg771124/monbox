"""【通用】编排队长操作同步、队员策略与设备状态检查，参考主流中控框架的并行执行模式。"""

# 【通用】导入线程池以并行控制多台设备（参考网上批量ADB集群方案）。
from concurrent.futures import ThreadPoolExecutor, as_completed
# 【通用】导入队伍和角色模型。
from monsterbox.models import DeviceStatus, Role, TeamConfig
# 【通用】导入统一 ADB 服务。
from monsterbox.services.adb import AdbService
# 【通用】导入自动化运行器以执行规则步骤。
from monsterbox.services.automation import AutomationRunner, AutomationStep
# 【通用】导入雷电服务以自动获取ADB序列号。
from monsterbox.services.ldplayer import LdPlayerService


# 【通用】协调一支队伍的四个设备，避免界面直接调用命令。
class TeamOrchestrator:
    """【通用】负责状态检查、ADB地址自动发现、队长同步操作及多设备并行任务执行。"""

    # 【通用】保存 ADB 服务和两支队伍配置。
    def __init__(self, adb: AdbService, ldplayer: LdPlayerService, teams: tuple[TeamConfig, TeamConfig], max_workers: int = 8) -> None:
        """【通用】初始化两队编排器，支持并行执行。"""

        # 【通用】保存统一 ADB 服务供所有角色复用。
        self._adb = adb
        # 【通用】保存雷电服务用于自动查询ADB序列号。
        self._ldplayer = ldplayer
        # 【通用】按队伍编号建立快速索引。
        self._teams = {team.team_id: team for team in teams}
        # 【通用】线程池用于并行向多台设备发送命令（参考集群方案ThreadPoolExecutor）。
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="orchestrator")
        # 【通用】为每个角色建立独立自动化运行器。
        self._automation_runners: dict[tuple[int, Role], AutomationRunner] = {}
        # 【通用】为两队所有角色初始化自动化运行器。
        for team in teams:
            for role in Role:
                self._automation_runners[(team.team_id, role)] = AutomationRunner(adb)

    # 【通用】刷新指定队伍全部角色的在线状态，自动获取ADB序列号。
    def refresh_statuses(self, team_id: int) -> dict[Role, DeviceStatus]:
        """【通用】逐个检查设备并自动获取ADB序列号，单一失败不阻塞其他角色。"""

        # 【通用】读取目标队伍配置。
        team = self._teams[team_id]
        # 【通用】准备返回每个角色的最新状态。
        statuses: dict[Role, DeviceStatus] = {}

        # 【通用】先从雷电查询运行中实例的ADB地址建立缓存。
        running_serials: dict[int, str] = {}
        try:
            # 【通用】获取所有实例列表，找出运行中的实例。
            instances = self._ldplayer.get_instances()
            running_instances = [inst for inst in instances if inst.android_started]
            # 【通用】并行获取所有运行中实例的ADB序列号（雷电专用命令）。
            futures = {}
            for inst in running_instances:
                future = self._executor.submit(self._safe_get_serial, inst.index)
                futures[future] = inst.index
            # 【通用】收集查询结果。
            for future in as_completed(futures, timeout=10):
                inst_index = futures[future]
                serial = future.result()
                if serial:
                    running_serials[inst_index] = serial
            # 【通用】备用方案：雷电查询失败时，通过雷电默认端口规则猜测序列号。
            # 雷电实例index对应的ADB端口通常是 5555 + index*2（索引0->5555, 索引1->5557...）
            if not running_serials:
                for inst in running_instances:
                    port = 5555 + inst.index * 2
                    running_serials[inst.index] = f"emulator-{port}"
            # 【通用】备用方案2：获取系统ADB设备列表尝试匹配。
            adb_devices = self._adb.list_devices()
        except Exception:
            # 【通用】雷电列表查询失败时继续使用原有绑定逐个检查。
            adb_devices = []
            pass

        # 【通用】依次检查四个角色，队员2与3走同一逻辑。
        for role, binding in team.bindings.items():
            # 【通用】空位身份没有模拟器，直接标记离线，避免发送无效命令。
            if not binding.is_assigned:
                # 【通用】空位不参与任务执行，也不显示为异常。
                binding.status = DeviceStatus.OFFLINE
                # 【通用】记录空位状态并继续检查下一个身份。
                statuses[role] = binding.status
                # 【通用】跳过该身份后续的序列号查询。
                continue
            # 【通用】如果还没有序列号，尝试从运行中实例缓存获取。
            if not binding.adb_serial and binding.instance_index in running_serials:
                binding.adb_serial = running_serials[binding.instance_index]
            # 【通用】未绑定序列号且无法自动获取时标记离线，不误发命令。
            if not binding.adb_serial:
                binding.status = DeviceStatus.OFFLINE
            # 【通用】已绑定设备时执行 ADB 状态查询。
            else:
                # 【通用】捕获单设备错误，保证其他设备仍能更新。
                try:
                    # 【通用】只有返回 device 才认定在线。
                    state_result = self._adb.get_state(binding.adb_serial)
                    binding.status = DeviceStatus.ONLINE if state_result.stdout == "device" else DeviceStatus.OFFLINE
                    # 【通用】离线状态清空序列号下次重连时重新获取。
                    if binding.status is DeviceStatus.OFFLINE and binding.instance_index not in running_serials:
                        # 【通用】实例未运行时保留序列号可能导致误判，清空等待下次刷新。
                        pass
                # 【通用】外部工具或设备异常统一标记错误。
                except (OSError, ValueError, RuntimeError):
                    binding.status = DeviceStatus.ERROR
            # 【通用】将角色状态加入结果。
            statuses[role] = binding.status
        # 【通用】返回完整四角色状态映射。
        return statuses

    # 【通用】安全获取实例ADB序列号，失败返回None。
    def _safe_get_serial(self, instance_index: int) -> str | None:
        """【通用】内部方法：捕获异常，避免单个实例查询失败影响整体。"""
        try:
            return self._ldplayer.get_adb_serial(instance_index)
        except Exception:
            return None

    # 【队长】将队长坐标点击同步到所有在线队员（并行发送，参考集群方案）。
    def sync_leader_tap(self, team_id: int, x: int, y: int) -> dict[Role, bool]:
        """【队长】并行向队员1、队员2和队员3发送相同点击。"""

        # 【队长】读取队长所在队伍配置。
        team = self._teams[team_id]
        # 【队员】遍历除队长外的角色，并行执行点击。
        member_roles = [Role.MEMBER_1, Role.MEMBER_2, Role.MEMBER_3]

        # 【通用】使用并行方式发送命令，减少多设备延迟（参考网上ThreadPoolExecutor方案）。
        results: dict[Role, bool] = {}
        futures = {}
        for role in member_roles:
            binding = team.bindings[role]
            # 【队员】仅向状态在线且存在序列号的设备发送操作。
            if binding.status is DeviceStatus.ONLINE and binding.adb_serial:
                serial = binding.adb_serial
                future = self._executor.submit(self._safe_tap, serial, x, y)
                futures[future] = role
            else:
                results[role] = False
        # 【通用】收集并行执行结果。
        for future in as_completed(futures, timeout=10):
            role = futures[future]
            try:
                results[role] = future.result()
            except Exception:
                results[role] = False
        return results

    # 【通用】安全执行点击，捕获所有异常。
    def _safe_tap(self, serial: str, x: int, y: int) -> bool:
        """【通用】内部方法：线程池中安全执行点击。"""
        try:
            return self._adb.tap(serial, x, y).succeeded
        except Exception:
            return False

    # 【队长】将队长滑动同步到所有在线队员。
    def sync_leader_swipe(self, team_id: int, start: tuple[int, int], end: tuple[int, int], duration_ms: int) -> dict[Role, bool]:
        """【队长】并行向所有队员发送相同滑动操作。"""

        team = self._teams[team_id]
        member_roles = [Role.MEMBER_1, Role.MEMBER_2, Role.MEMBER_3]
        results: dict[Role, bool] = {}
        futures = {}
        for role in member_roles:
            binding = team.bindings[role]
            if binding.status is DeviceStatus.ONLINE and binding.adb_serial:
                serial = binding.adb_serial
                future = self._executor.submit(self._safe_swipe, serial, start, end, duration_ms)
                futures[future] = role
            else:
                results[role] = False
        for future in as_completed(futures, timeout=15):
            role = futures[future]
            try:
                results[role] = future.result()
            except Exception:
                results[role] = False
        return results

    # 【通用】安全执行滑动。
    def _safe_swipe(self, serial: str, start: tuple[int, int], end: tuple[int, int], duration_ms: int) -> bool:
        """【通用】内部方法：线程池中安全执行滑动。"""
        try:
            return self._adb.swipe(serial, start, end, duration_ms).succeeded
        except Exception:
            return False

    # 【通用】按角色分配步骤并并行执行自动化任务。
    def run_team_automation(self, team_id: int, leader_steps: list[AutomationStep], member1_steps: list[AutomationStep], shared_member_steps: list[AutomationStep]) -> dict[Role, bool]:
        """【通用】队长执行leader_steps，队员1执行专属步骤，队员2/3执行共享步骤，全部并行。"""

        team = self._teams[team_id]
        results: dict[Role, bool] = {}

        # 【通用】停止之前可能在运行的任务。
        for role in Role:
            runner = self._automation_runners[(team_id, role)]
            runner.stop()

        # 【通用】定义角色与对应步骤的映射。
        role_tasks = {
            Role.LEADER: leader_steps,
            Role.MEMBER_1: member1_steps,
            Role.MEMBER_2: shared_member_steps,
            Role.MEMBER_3: shared_member_steps,
        }

        # 【通用】并行启动各角色任务。
        futures = {}
        for role, steps in role_tasks.items():
            binding = team.bindings[role]
            runner = self._automation_runners[(team_id, role)]
            # 【通用】只有在线设备才执行任务。
            if binding.status is DeviceStatus.ONLINE and binding.adb_serial and steps:
                serial = binding.adb_serial
                future = self._executor.submit(runner.run, serial, steps)
                futures[future] = role
            else:
                results[role] = False

        # 【通用】收集各角色执行结果。
        for future in as_completed(futures, timeout=300):
            role = futures[future]
            try:
                results[role] = future.result()
            except Exception:
                results[role] = False
        return results

    # 【通用】停止队伍中所有正在运行的自动化任务。
    def stop_team_automation(self, team_id: int) -> None:
        """【通用】请求所有角色的自动化运行器尽快停止。"""
        for role in Role:
            runner = self._automation_runners[(team_id, role)]
            runner.stop()

    # 【通用】手动更新指定角色绑定的ADB序列号（用于用户手动配置）。
    def update_binding_serial(self, team_id: int, role: Role, adb_serial: str) -> None:
        """【通用】更新设备绑定序列号，通常在自动获取失败后手动指定。"""
        team = self._teams[team_id]
        team.bindings[role].adb_serial = adb_serial

    # 【通用】用户通过右键菜单调整队伍身份后同步最新绑定。
    def apply_teams(self, teams: tuple[TeamConfig, ...]) -> None:
        """【通用】只替换队伍配置，保留线程池和各角色运行器，避免打断正在运行的任务。"""

        # 【通用】按队伍编号重新建立快速索引。
        self._teams = {team.team_id: team for team in teams}

    # 【通用】关闭编排器，释放线程池资源。
    def shutdown(self) -> None:
        """【通用】停止所有任务并关闭线程池。"""
        for team_id in self._teams:
            self.stop_team_automation(team_id)
        self._executor.shutdown(wait=False, cancel_futures=True)
