"""测试辅助工具。

汇集主程序测试共用的测试 harness，仅供测试使用、不参与运行时逻辑：

- :mod:`app.testing.bootstrap`：隔离 CONFIG_DIR、建表与退出清理等引导逻辑；
- :mod:`app.testing.network_guard`：autouse 拦截测试期对非本地主机的真实出站。

子模块按需 import，避免 ``import app.testing`` 引入 pytest 等测试期依赖。
"""
