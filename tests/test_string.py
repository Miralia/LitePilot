from app.utils.string import StringUtils


def test_is_media_title_like_true():
    assert StringUtils.is_media_title_like("盗梦空间")
    assert StringUtils.is_media_title_like("The Lord of the Rings")
    assert StringUtils.is_media_title_like("庆余年 第2季")
    assert StringUtils.is_media_title_like("The Office S01E01")
    assert StringUtils.is_media_title_like("权力的游戏 Game of Thrones")
    assert StringUtils.is_media_title_like("Spider-Man: No Way Home 2021")


def test_is_media_title_like_false():
    assert not StringUtils.is_media_title_like("")
    assert not StringUtils.is_media_title_like("   ")
    assert not StringUtils.is_media_title_like("a")
    assert not StringUtils.is_media_title_like("第2季")
    assert not StringUtils.is_media_title_like("S01E01")
    assert not StringUtils.is_media_title_like("#推荐电影")
    assert not StringUtils.is_media_title_like("请帮我推荐一部电影")
    assert not StringUtils.is_media_title_like("盗梦空间怎么样？")
    assert not StringUtils.is_media_title_like("我想看盗梦空间")
    assert not StringUtils.is_media_title_like("继续")
