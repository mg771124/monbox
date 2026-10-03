"""【通用】编排队长操作同步、队员策略与设备状态检查。"""

# 【通用】导入队伍和角色模型。
from monsterbox.models import DeviceStatus, Role, TeamConfig
# 【通用】导入统一 ADB 服务。
from monsterbox.services.adb import AdbService


# 【通用】协调一支队伍的四个设备，避免界面直接调用命令。
class TeamOrchestrator:
    """【通用】负责状态检查及队长向三个队员同步操作。"""

    # 【通用】保存 ADB 服务和两支队伍配置。
    def __init__(self, adb: AdbService, teams: tuple[TeamConfig, TeamConfig]) -> None:
        """【通用】初始化两队编排器。"""

        # 【通用】保存统一 ADB 服务供所有角色复用。
        self._adb = adb
        # 【通用】按队伍编号建立快速索引。
        self._teams = {team.team_id: team for team in teams}

    # 【通用】刷新指定队伍全部角色的在线状态。
    def refresh_statuses(self, team_id: int) -> dict[Role, DeviceStatus]:
        """【通用】逐个检查设备，单一失败不阻塞其他角色。"""

        # 【通用】读取目标队伍配置。
        team = self._teams[team_id]
        # 【通用】准备返回每个角色的最新状态。
        statuses: dict[Role, DeviceStatus] = {}
        # 【通用】依次检查四个角色，队员2与3走同一逻辑。
        for role, binding in team.bindings.items():
            # 【通用】未绑定序列号时标记离线，不误发命令。
            if not binding.adb_serial:
                # 【通用】保存离线状态。
                binding.status = DeviceStatus.OFFLINE
            # 【通用】已绑定设备时执行 ADB 状态查询。
            else:
                # 【通用】捕获单设备错误，保证其他设备仍能更新。
                try:
                    # 【通用】只有返回 device 才认定在线。
                    binding.status = DeviceStatus.ONLINE if self._adb.get_state(binding.adb_serial).stdout == "device" else DeviceStatus.OFFLINE
                # 【通用】外部工具或设备异常统一标记错误。
                except (OSError, ValueError, RuntimeError):
                    # 【通用】记录异常状态并继续下一角色。
                    binding.status = DeviceStatus.ERROR
            # 【通用】将角色状态加入结果。
            statuses[role] = binding.status
        # 【通用】返回完整四角色状态映射。
        return statuses

    # 【队长】将队长坐标点击同步到所有在线队员。
    def sync_leader_tap(self, team_id: int, x: int, y: int) -> dict[Role, bool]:
        """【队长】向队员1、队员2和队员3发送相同点击。"""

        # 【队长】读取队长所在队伍配置。
        team = self._teams[team_id]
        # 【队长】准备记录每位队员的独立执行结果。
        results: dict[Role, bool] = {}
        # 【队员】遍历除队长外的角色，队员2与3自然复用同一分支。
        for role in (Role.MEMBER_1, Role.MEMBER_2, Role.MEMBER_3):
            # 【队员】取得目标队员设备绑定。
            binding = team.bindings[role]
            # 【队员】仅向状态在线且存在序列号的设备发送操作。
            if binding.status is not DeviceStatus.ONLINE or not binding.adb_serial:
                # 【队员】记录跳过结果，不阻塞其他队员。
                results[role] = False
                # 【队员】继续处理下一台设备。
                continue
            # 【队员】执行点击并独立记录成功状态。
            try:
                # 【队员】零退出码代表本次同步成功。
                results[role] = self._adb.tap(binding.adb_serial, x, y).succeeded
            # 【队员】单设备异常只影响当前结果。
            except (OSError, ValueError, RuntimeError):
                # 【队员】记录失败后继续同步剩余设备。
                results[role] = False
        # 【队长】返回三个队员的独立同步结果。
        return results
