from app.chain.tmdb import TmdbChain


def test_wallpaper_chain_method_uses_correct_spelling():
    """壁纸 Chain 公共方法不应保留 wallpager 拼写错误。"""
    assert hasattr(TmdbChain, "get_random_wallpaper")
    assert not hasattr(TmdbChain, "get_random_wallpager")


def test_wallpaper_scheduler_job_uses_correct_spelling():
    """调度任务源码不应注册或展示 random_wallpager。"""
    from pathlib import Path

    scheduler_source = Path("app/scheduler.py").read_text(encoding="utf-8")
    assert "random_wallpaper" in scheduler_source
    assert "random_wallpager" not in scheduler_source
