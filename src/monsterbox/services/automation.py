"""【通用】实现可停止、可重试且支持识图点击的自动化任务流程。"""

# 【通用】导入线程事件以支持安全停止任务。
from threading import Event
# 【通用】导入休眠函数以实现可中断等待。
from time import sleep
# 【通用】导入数据类定义稳定任务步骤。
from dataclasses import dataclass
# 【通用】导入枚举限制步骤类型。
from enum import StrEnum
# 【通用】导入统一 ADB 服务。
from monsterbox.services.adb import AdbService
# 【通用】导入内存模板匹配函数。
from monsterbox.services.image_matcher import find_template


# 【通用】定义首版自动化支持的步骤类型。
class StepType(StrEnum):
    """【通用】限制任务脚本只能执行经过审核的动作。"""

    # 【队长/队员】执行固定坐标点击。
    TAP = "点击"
    # 【队长/队员】识别模板后点击模板中心。
    FIND_AND_TAP = "识图点击"
    # 【通用】在步骤间执行可停止等待。
    WAIT = "等待"


# 【通用】保存一个可验证的任务步骤。
@dataclass(frozen=True, slots=True)
class AutomationStep:
    """【通用】描述点击、识图点击或等待动作。"""

    # 【通用】指定当前步骤类型。
    step_type: StepType
    # 【队长/队员】保存点击横坐标。
    x: int = 0
    # 【队长/队员】保存点击纵坐标。
    y: int = 0
    # 【通用】保存等待秒数。
    wait_seconds: float = 0
    # 【队长/队员】保存识图模板 PNG 字节。
    template_png: bytes = b""
    # 【队长/队员】保存识图最低置信度。
    threshold: float = 0.85
    # 【通用】保存步骤失败后的最大重试次数。
    retries: int = 1


# 【通用】按顺序执行单个设备的自动化步骤。
class AutomationRunner:
    """【通用】为队长、队员1和共享逻辑队员2/3执行同一任务引擎。"""

    # 【通用】保存 ADB 服务并建立停止事件。
    def __init__(self, adb: AdbService) -> None:
        """【通用】初始化可停止任务执行器。"""

        # 【通用】保存统一设备服务。
        self._adb = adb
        # 【通用】建立线程安全停止标志。
        self._stop_event = Event()

    # 【通用】请求当前自动化任务尽快停止。
    def stop(self) -> None:
        """【通用】设置停止标志，不强制破坏正在运行的外部命令。"""

        # 【通用】通知步骤循环和等待操作退出。
        self._stop_event.set()

    # 【通用】执行一组有界任务步骤。
    def run(self, serial: str, steps: list[AutomationStep]) -> bool:
        """【通用】返回任务是否完整成功，停止或失败时返回假值。"""

        # 【通用】每次新任务开始前清除上次停止状态。
        self._stop_event.clear()
        # 【通用】按脚本顺序执行步骤。
        for step in steps:
            # 【通用】收到停止请求时立即结束后续动作。
            if self._stop_event.is_set():
                # 【通用】返回未完成状态。
                return False
            # 【通用】等待步骤使用事件等待以支持即时停止。
            if step.step_type is StepType.WAIT:
                # 【通用】事件在等待期间被设置时任务停止。
                if self._stop_event.wait(max(0, step.wait_seconds)):
                    # 【通用】返回未完成状态。
                    return False
                # 【通用】等待完成后继续下一步骤。
                continue
            # 【通用】至少尝试一次，并限制配置中的重试次数。
            attempts = max(1, step.retries + 1)
            # 【通用】记录当前步骤是否成功。
            step_succeeded = False
            # 【通用】按上限重试，不使用无限循环。
            for attempt in range(attempts):
                # 【通用】重试前检查停止请求。
                if self._stop_event.is_set():
                    # 【通用】停止后不再向设备发送操作。
                    return False
                # 【通用】执行当前步骤并记录结果。
                step_succeeded = self._run_step(serial, step)
                # 【通用】成功后结束当前步骤重试。
                if step_succeeded:
                    # 【通用】退出有限重试循环。
                    break
                # 【通用】失败且仍可重试时短暂等待，避免高频调用设备。
                if attempt + 1 < attempts:
                    # 【通用】固定短等待不会形成无界阻塞。
                    sleep(0.2)
            # 【通用】全部尝试失败后终止任务并返回失败。
            if not step_succeeded:
                # 【通用】避免错误状态下继续点击后续坐标。
                return False
        # 【通用】全部步骤完成后返回成功。
        return True

    # 【通用】执行单个非等待步骤。
    def _run_step(self, serial: str, step: AutomationStep) -> bool:
        """【通用】复用统一动作逻辑，队员2与3不建立独立分支。"""

        # 【队长/队员】固定点击直接调用 ADB 服务。
        if step.step_type is StepType.TAP:
            # 【队长/队员】返回点击命令退出状态。
            return self._adb.tap(serial, step.x, step.y).succeeded
        # 【队长/队员】识图点击先取得内存截图。
        if step.step_type is StepType.FIND_AND_TAP:
            # 【队长/队员】获取目标设备当前 PNG 截图。
            screenshot = self._adb.screenshot_png(serial)
            # 【队长/队员】在当前画面搜索模板中心。
            point = find_template(screenshot, step.template_png, step.threshold)
            # 【队长/队员】未找到模板时让有限重试机制接管。
            if point is None:
                # 【队长/队员】返回本次尝试失败。
                return False
            # 【队长/队员】对匹配中心执行设备点击。
            return self._adb.tap(serial, *point).succeeded
        # 【通用】拒绝未受支持的任务类型，避免静默跳过。
        raise ValueError(f"不支持的自动化步骤：{step.step_type}")
