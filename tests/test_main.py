"""【通用】验证源码和独立 EXE 使用正确的配置目录。"""

# 【通用】导入系统模块以模拟 PyInstaller 独立运行环境。
import sys
# 【通用】导入路径类型验证目录结果。
from pathlib import Path
# 【通用】导入应用目录解析函数。
from monsterbox.main import get_application_directory


# 【通用】验证独立 EXE 将配置放在自身旁边。
def test_frozen_application_uses_executable_directory(monkeypatch, tmp_path: Path) -> None:
    """【通用】目标电脑从任意位置启动时均可找到自己的配置。"""

    # 【通用】模拟 PyInstaller 设置的 frozen 标志。
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    # 【通用】模拟成品 EXE 位于独立发布资料夹。
    monkeypatch.setattr(sys, "executable", str(tmp_path / "MonsterBox.exe"))
    # 【通用】应用目录必须等于 EXE 所在资料夹。
    assert get_application_directory() == tmp_path


# 【通用】验证开发环境仍使用项目当前工作目录。
def test_source_application_uses_current_directory(monkeypatch, tmp_path: Path) -> None:
    """【通用】源码运行保持现有配置读取方式。"""

    # 【通用】确保测试环境不带 PyInstaller frozen 标志。
    monkeypatch.delattr(sys, "frozen", raising=False)
    # 【通用】切换到隔离的测试工作目录。
    monkeypatch.chdir(tmp_path)
    # 【通用】源码应用目录必须等于当前项目目录。
    assert get_application_directory() == tmp_path
