"""0.1.0
删除站点、订阅、智能体与工作流数据表

Revision ID: b1f7c3d9e5a2
Revises: a8c4e2f6b1d9
Create Date: 2026-10-18

本迁移对应精简分支：站点、订阅、插件、智能体与工作流能力已从代码中删除，
对应的数据表不再有模型与读写方。升级时直接删表释放空间；降级只能重建空表结构，
业务数据无法恢复，因此降级前必须先完整备份数据库。
"""

from alembic import op
import sqlalchemy as sa


revision = "b1f7c3d9e5a2"
down_revision = "a8c4e2f6b1d9"
branch_labels = None
depends_on = None

# 已删除能力对应的数据表
_DROPPED_TABLES = (
    "site",
    "siteicon",
    "sitestatistic",
    "siteuserdata",
    "subscribe",
    "subscribehistory",
    "plugindata",
    "agentchat",
    "agenttask",
    "workflow",
    "userrequest",
)


def _existing_tables() -> set:
    """获取当前数据库已有的数据表名。"""
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    """删除已下线能力的数据表。"""
    existing = _existing_tables()
    for table_name in _DROPPED_TABLES:
        if table_name in existing:
            op.drop_table(table_name)


def downgrade() -> None:
    """
    重建空表结构。

    表内业务数据在升级时已随表删除，降级只能恢复结构；如需保留历史数据，
    请在升级前完成数据库备份。
    """
    existing = _existing_tables()
    # 站点表
    if "site" not in existing:
        op.create_table(
            "site",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String()),
            sa.Column("domain", sa.String()),
            sa.Column("url", sa.String()),
            sa.Column("pri", sa.Integer()),
            sa.Column("rss", sa.String()),
            sa.Column("cookie", sa.String()),
            sa.Column("ua", sa.String()),
            sa.Column("apikey", sa.String()),
            sa.Column("token", sa.String()),
            sa.Column("proxy", sa.Integer()),
            sa.Column("filter", sa.String()),
            sa.Column("render", sa.Integer()),
            sa.Column("public", sa.Integer()),
            sa.Column("note", sa.JSON()),
            sa.Column("limit_interval", sa.Integer()),
            sa.Column("limit_count", sa.Integer()),
            sa.Column("limit_seconds", sa.Integer()),
            sa.Column("timeout", sa.Integer()),
            sa.Column("is_active", sa.Boolean()),
            sa.Column("lst_mod_date", sa.String()),
            sa.Column("downloader", sa.String()),
        )
    if "siteicon" not in existing:
        op.create_table(
            "siteicon",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String()),
            sa.Column("domain", sa.String()),
            sa.Column("url", sa.String()),
            sa.Column("base64", sa.String()),
        )
    if "sitestatistic" not in existing:
        op.create_table(
            "sitestatistic",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("domain", sa.String()),
            sa.Column("success", sa.Integer()),
            sa.Column("fail", sa.Integer()),
            sa.Column("seconds", sa.Integer()),
            sa.Column("lst_state", sa.Integer()),
            sa.Column("lst_mod_date", sa.String()),
            sa.Column("note", sa.JSON()),
        )
    if "siteuserdata" not in existing:
        op.create_table(
            "siteuserdata",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("domain", sa.String()),
            sa.Column("name", sa.String()),
            sa.Column("username", sa.String()),
            sa.Column("userid", sa.Integer()),
            sa.Column("user_level", sa.String()),
            sa.Column("join_at", sa.String()),
            sa.Column("bonus", sa.Float()),
            sa.Column("upload", sa.Float()),
            sa.Column("download", sa.Float()),
            sa.Column("ratio", sa.Float()),
            sa.Column("seeding", sa.Float()),
            sa.Column("leeching", sa.Float()),
            sa.Column("seeding_size", sa.Float()),
            sa.Column("leeching_size", sa.Float()),
            sa.Column("seeding_info", sa.JSON()),
            sa.Column("message_unread", sa.Integer()),
            sa.Column("message_unread_contents", sa.JSON()),
            sa.Column("err_msg", sa.String()),
            sa.Column("updated_day", sa.String()),
            sa.Column("updated_time", sa.String()),
        )
    # 订阅表
    if "subscribe" not in existing:
        op.create_table(
            "subscribe",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String()),
            sa.Column("year", sa.String()),
            sa.Column("type", sa.String()),
            sa.Column("keyword", sa.String()),
            sa.Column("tmdbid", sa.Integer()),
            sa.Column("imdbid", sa.String()),
            sa.Column("tvdbid", sa.Integer()),
            sa.Column("doubanid", sa.String()),
            sa.Column("bangumiid", sa.Integer()),
            sa.Column("mediaid", sa.String()),
            sa.Column("season", sa.Integer()),
            sa.Column("poster", sa.String()),
            sa.Column("backdrop", sa.String()),
            sa.Column("vote", sa.Float()),
            sa.Column("description", sa.String()),
            sa.Column("filter", sa.String()),
            sa.Column("include", sa.String()),
            sa.Column("exclude", sa.String()),
            sa.Column("quality", sa.String()),
            sa.Column("resolution", sa.String()),
            sa.Column("effect", sa.String()),
            sa.Column("total_episode", sa.Integer()),
            sa.Column("start_episode", sa.Integer()),
            sa.Column("lack_episode", sa.Integer()),
            sa.Column("note", sa.JSON()),
            sa.Column("state", sa.String()),
            sa.Column("last_update", sa.String()),
            sa.Column("date", sa.String()),
            sa.Column("username", sa.String()),
            sa.Column("sites", sa.JSON()),
            sa.Column("downloader", sa.String()),
            sa.Column("best_version", sa.Integer()),
            sa.Column("current_priority", sa.Integer()),
            sa.Column("save_path", sa.String()),
            sa.Column("search_imdbid", sa.Integer()),
            sa.Column("manual_total_episode", sa.Integer()),
            sa.Column("custom_words", sa.String()),
            sa.Column("media_category", sa.String()),
            sa.Column("filter_groups", sa.JSON()),
            sa.Column("episode_group", sa.String()),
            sa.Column("episode_priority", sa.JSON()),
            sa.Column("best_version_full", sa.Integer(), server_default='0'),
            sa.Column("anilistid", sa.Integer()),
            sa.Column("media_source", sa.String()),
            sa.Column("media_id", sa.String()),
        )
    if "subscribehistory" not in existing:
        op.create_table(
            "subscribehistory",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String()),
            sa.Column("year", sa.String()),
            sa.Column("type", sa.String()),
            sa.Column("keyword", sa.String()),
            sa.Column("tmdbid", sa.Integer()),
            sa.Column("imdbid", sa.String()),
            sa.Column("tvdbid", sa.Integer()),
            sa.Column("doubanid", sa.String()),
            sa.Column("bangumiid", sa.Integer()),
            sa.Column("mediaid", sa.String()),
            sa.Column("season", sa.Integer()),
            sa.Column("poster", sa.String()),
            sa.Column("backdrop", sa.String()),
            sa.Column("vote", sa.Float()),
            sa.Column("description", sa.String()),
            sa.Column("filter", sa.String()),
            sa.Column("include", sa.String()),
            sa.Column("exclude", sa.String()),
            sa.Column("quality", sa.String()),
            sa.Column("resolution", sa.String()),
            sa.Column("effect", sa.String()),
            sa.Column("total_episode", sa.Integer()),
            sa.Column("start_episode", sa.Integer()),
            sa.Column("date", sa.String()),
            sa.Column("username", sa.String()),
            sa.Column("sites", sa.JSON()),
            sa.Column("best_version", sa.Integer()),
            sa.Column("save_path", sa.String()),
            sa.Column("search_imdbid", sa.Integer()),
            sa.Column("custom_words", sa.String()),
            sa.Column("media_category", sa.String()),
            sa.Column("filter_groups", sa.JSON()),
            sa.Column("episode_group", sa.String()),
            sa.Column("episode_priority", sa.JSON()),
            sa.Column("best_version_full", sa.Integer(), server_default='0'),
            sa.Column("anilistid", sa.Integer()),
            sa.Column("media_source", sa.String()),
            sa.Column("media_id", sa.String()),
        )
    # 插件数据表
    if "plugindata" not in existing:
        op.create_table(
            "plugindata",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("plugin_id", sa.String()),
            sa.Column("key", sa.String()),
            sa.Column("value", sa.JSON()),
        )
    # 智能体会话表
    if "agentchat" not in existing:
        op.create_table(
            "agentchat",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.String()),
            sa.Column("client_session_id", sa.String()),
            sa.Column("user_id", sa.String()),
            sa.Column("username", sa.String()),
            sa.Column("channel", sa.String()),
            sa.Column("source", sa.String()),
            sa.Column("original_chat_id", sa.String()),
            sa.Column("title", sa.String()),
            sa.Column("preview", sa.String()),
            sa.Column("agent_messages", sa.JSON()),
            sa.Column("display_messages", sa.JSON()),
            sa.Column("message_count", sa.Integer()),
            sa.Column("created_at", sa.String()),
            sa.Column("updated_at", sa.String()),
        )
    if "agenttask" not in existing:
        op.create_table(
            "agenttask",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String()),
            sa.Column("content", sa.Text()),
            sa.Column("trigger_type", sa.String()),
            sa.Column("cron_expression", sa.String()),
            sa.Column("run_at", sa.String()),
            sa.Column("enabled", sa.Boolean()),
            sa.Column("user_id", sa.String()),
            sa.Column("username", sa.String()),
            sa.Column("session_id", sa.String()),
            sa.Column("channel", sa.String()),
            sa.Column("source", sa.String()),
            sa.Column("original_chat_id", sa.String()),
            sa.Column("last_status", sa.String()),
            sa.Column("last_run_at", sa.String()),
            sa.Column("last_result", sa.Text()),
            sa.Column("run_count", sa.Integer()),
            sa.Column("created_at", sa.String()),
            sa.Column("updated_at", sa.String()),
        )
    # 工作流表
    if "workflow" not in existing:
        op.create_table(
            "workflow",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String()),
            sa.Column("description", sa.String()),
            sa.Column("timer", sa.String()),
            sa.Column("state", sa.String()),
            sa.Column("current_action", sa.String()),
            sa.Column("result", sa.String()),
            sa.Column("run_count", sa.Integer()),
            sa.Column("actions", sa.JSON()),
            sa.Column("context", sa.JSON()),
            sa.Column("add_time", sa.String()),
            sa.Column("last_time", sa.String()),
            sa.Column("flows", sa.JSON()),
            sa.Column("trigger_type", sa.String()),
            sa.Column("event_type", sa.String()),
            sa.Column("event_conditions", sa.JSON()),
            sa.Column("execution_config", sa.JSON()),
            sa.Column("execution_state", sa.JSON()),
        )
    # 求片表
    if "userrequest" not in existing:
        op.create_table(
            "userrequest",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("req_user", sa.String()),
            sa.Column("req_time", sa.String()),
            sa.Column("req_remark", sa.String()),
            sa.Column("app_user", sa.String()),
            sa.Column("app_time", sa.String()),
            sa.Column("app_status", sa.Integer()),
            sa.Column("type", sa.String()),
            sa.Column("title", sa.String()),
            sa.Column("year", sa.String()),
            sa.Column("tmdbid", sa.Integer()),
            sa.Column("imdbid", sa.String()),
            sa.Column("tvdbid", sa.Integer()),
            sa.Column("doubanid", sa.String()),
            sa.Column("bangumiid", sa.Integer()),
            sa.Column("season", sa.Integer()),
            sa.Column("poster", sa.String()),
            sa.Column("backdrop", sa.String()),
            sa.Column("vote", sa.Float()),
            sa.Column("description", sa.String()),
        )
