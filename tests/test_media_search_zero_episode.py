from app.chain.media import MediaChain


def test_search_preserves_zero_episode_keyword():
    """搜索第 0 集特别篇时不能把集号当作缺失值丢弃。"""
    chain = object.__new__(MediaChain)
    captured = {}

    def fake_search_medias(meta, source=None):
        captured["meta"] = meta
        captured["source"] = source
        return []

    chain.search_medias = fake_search_medias

    meta, medias = chain.search("测试剧 第0集")

    assert medias == []
    assert captured["source"] is None
    assert meta.begin_episode == 0
    assert meta.begin_season == 1
