"""【通用】验证图像模板匹配中心坐标与阈值保护。"""

# 【通用】导入 OpenCV 生成内存 PNG 测试图。
import cv2
# 【通用】导入 NumPy 建立测试像素数组。
import numpy as np
# 【通用】导入 pytest 验证错误阈值。
import pytest
# 【通用】导入待测试模板匹配函数。
from monsterbox.services.image_matcher import find_template


# 【通用】将 NumPy 图像编码为 PNG 字节。
def _png(image: np.ndarray) -> bytes:
    """【通用】生成不落地磁盘的测试图片。"""

    # 【通用】以内存方式编码 PNG。
    succeeded, encoded = cv2.imencode(".png", image)
    # 【通用】测试准备阶段必须编码成功。
    assert succeeded
    # 【通用】返回编码后的原始字节。
    return encoded.tobytes()


# 【通用】验证无纹理模板可能不稳定，因此使用明确随机纹理。
def test_find_template_returns_center() -> None:
    """【通用】命中模板时返回区域中心点。"""

    # 【通用】建立固定随机种子以确保测试可复现。
    generator = np.random.default_rng(7)
    # 【通用】建立 10 乘 12 的随机灰度模板。
    template = generator.integers(0, 255, (10, 12), dtype=np.uint8)
    # 【通用】建立足够大的黑色截图。
    screenshot = np.zeros((60, 80), dtype=np.uint8)
    # 【通用】将模板放在左上角坐标 20,15。
    screenshot[15:25, 20:32] = template
    # 【通用】匹配中心应为 26,20。
    assert find_template(_png(screenshot), _png(template), 0.99) == (26, 20)


# 【通用】验证置信度参数受到范围保护。
def test_find_template_rejects_invalid_threshold() -> None:
    """【通用】禁止错误阈值导致自动化误点击。"""

    # 【通用】使用空字节即可在解码前触发阈值校验。
    with pytest.raises(ValueError, match="阈值"):
        # 【通用】传入大于一的非法阈值。
        find_template(b"", b"", 1.1)
