"""【通用】验证雷电 list2 实例清单解析。"""

# 【通用】导入 pytest 验证异常格式。
import pytest
# 【通用】导入实例解析函数。
from monsterbox.services.ldplayer import parse_instance_list


# 【通用】验证雷电实例会按索引转换为表格记录。
def test_parse_instance_list_returns_sorted_records() -> None:
    """【通用】正确识别名称、启动状态和进程编号。"""

    # 【通用】建立顺序刻意打乱的雷电 list2 测试输出。
    output = "1,队员模拟器,100,200,0,0,0\n0,队长模拟器,101,201,1,4321,5000"
    # 【通用】解析两条模拟器记录。
    instances = parse_instance_list(output)
    # 【通用】实例必须按索引稳定排序。
    assert [instance.index for instance in instances] == [0, 1]
    # 【通用】确认中文实例名称正确保留。
    assert instances[0].name == "队长模拟器"
    # 【通用】确认安卓启动标志转换为布尔值。
    assert instances[0].android_started is True
    # 【通用】确认进程编号正确转换。
    assert instances[0].process_id == 4321
    # 【通用】确认未启动实例状态正确。
    assert instances[1].android_started is False


# 【通用】验证字段不足的雷电输出不会产生错误表格。
def test_parse_instance_list_rejects_invalid_record() -> None:
    """【通用】格式异常时提供明确错误。"""

    # 【通用】异常记录必须抛出解析错误。
    with pytest.raises(ValueError, match="无法解析"):
        # 【通用】传入字段不足的记录。
        parse_instance_list("0,不完整")
