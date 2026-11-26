"""Bangumi API客户端边界测试。"""

import asyncio
from unittest.mock import AsyncMock, Mock

from app.modules.bangumi.bangumi import BangumiApi


def _json_response(payload: dict) -> Mock:
    """构造Bangumi JSON响应对象。"""
    response = Mock()
    response.status_code = 200
    response.json.return_value = payload
    return response


def test_bangumi_search_encodes_keyword_and_filters_anime() -> None:
    """Bangumi搜索应编码路径关键词，并只查询动漫条目。"""
    api = BangumiApi()
    api.clear_cache()
    api._req.get_res = Mock(return_value=_json_response({"list": [{"id": 1}]}))

    result = api.search("Fate/stay night 测试")

    assert result == [{"id": 1}]
    request_kwargs = api._req.get_res.call_args.kwargs
    assert request_kwargs["url"].endswith(
        "/search/subject/Fate%2Fstay%20night%20%E6%B5%8B%E8%AF%95"
    )
    assert request_kwargs["params"]["type"] == 2


def test_async_bangumi_search_encodes_keyword_and_filters_anime() -> None:
    """Bangumi异步搜索应保持相同的路径编码与条目过滤。"""
    api = BangumiApi()
    api._async_req.get_res = AsyncMock(return_value=_json_response({"list": [{"id": 2}]}))

    result = asyncio.run(api.async_search("Fate/zero 第一季"))

    assert result == [{"id": 2}]
    request_kwargs = api._async_req.get_res.call_args.kwargs
    assert request_kwargs["url"].endswith(
        "/search/subject/Fate%2Fzero%20%E7%AC%AC%E4%B8%80%E5%AD%A3"
    )
    assert request_kwargs["params"]["type"] == 2
