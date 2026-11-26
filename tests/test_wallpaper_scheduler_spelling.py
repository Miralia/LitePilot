def test_wallpaper_scheduler_job_uses_correct_spelling():
    """调度任务源码不应注册或展示 random_wallpager。"""
    from pathlib import Path

    scheduler_source = Path("app/scheduler.py").read_text(encoding="utf-8")
    assert "random_wallpaper" in scheduler_source
    assert "random_wallpager" not in scheduler_source
