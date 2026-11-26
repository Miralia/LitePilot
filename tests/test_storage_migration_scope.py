"""存储初始化迁移的活动能力边界回归测试。"""

import importlib


def test_initial_storage_seed_only_contains_local_storage() -> None:
    """全新安装只应初始化仍受支持的本地存储。"""
    migration = importlib.import_module("database.versions.294b007932ef_2_0_0")

    assert [storage["type"] for storage in migration.initial_storage_configs()] == ["local"]


def test_legacy_alist_seed_migration_is_retired() -> None:
    """历史 AList 初始化迁移只保留版本链，不再写入存储配置。"""
    migration = importlib.import_module("database.versions.a295e41830a6_2_0_6")

    assert not hasattr(migration, "SystemConfigOper")
    assert migration.upgrade() is None
