"""【通用】提供不落地临时截图的 OpenCV 模板匹配能力。"""

# 【通用】导入 OpenCV 处理截图和模板。
import cv2
# 【通用】导入 NumPy 将 PNG 字节转换为图像数组。
import numpy as np


# 【通用】在设备截图中搜索指定模板。
def find_template(screenshot_png: bytes, template_png: bytes, threshold: float = 0.85) -> tuple[int, int] | None:
    """【通用】返回匹配区域中心坐标，未达到阈值时返回空值。"""

    # 【通用】校验置信度范围，避免错误配置造成永久误点。
    if not 0 < threshold <= 1:
        # 【通用】向任务配置层报告阈值错误。
        raise ValueError("图像匹配阈值必须大于 0 且不超过 1")
    # 【通用】将截图字节解码为灰度图以降低计算成本。
    screenshot = cv2.imdecode(np.frombuffer(screenshot_png, np.uint8), cv2.IMREAD_GRAYSCALE)
    # 【通用】将模板字节解码为灰度图。
    template = cv2.imdecode(np.frombuffer(template_png, np.uint8), cv2.IMREAD_GRAYSCALE)
    # 【通用】拒绝无法解码的输入数据。
    if screenshot is None or template is None:
        # 【通用】提示调用方检查截图或模板格式。
        raise ValueError("截图或模板不是有效的 PNG 图像")
    # 【通用】拒绝比截图更大的模板，避免 OpenCV 断言失败。
    if template.shape[0] > screenshot.shape[0] or template.shape[1] > screenshot.shape[1]:
        # 【通用】大模板不可能命中，因此直接返回未匹配。
        return None
    # 【通用】计算标准化相关系数匹配结果。
    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    # 【通用】取得全图最高置信度及其左上角位置。
    _, confidence, _, location = cv2.minMaxLoc(result)
    # 【通用】低于任务阈值时不执行任何点击。
    if confidence < threshold:
        # 【通用】返回空值表示当前画面未找到目标。
        return None
    # 【通用】计算模板宽度和高度以定位中心点。
    height, width = template.shape
    # 【通用】返回适合 ADB 点击的模板中心坐标。
    return location[0] + width // 2, location[1] + height // 2
