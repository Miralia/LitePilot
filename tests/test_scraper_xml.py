from xml.etree import ElementTree as ET

from app.core.context import MediaInfo
from app.helper.scraper import MediaScraperHelper
from app.schemas.types import MediaType


def test_metadata_nfo_preserves_cdata_terminator_and_strips_invalid_control_chars():
    """外部简介中的 CDATA 终止符与控制字符不得破坏 NFO XML。"""
    media = MediaInfo(type=MediaType.MOVIE)
    media.title = "Sh\x02ow"
    media.overview = "before]]>middle\x01after"

    content = MediaScraperHelper.get_metadata_nfo(media)

    root = ET.fromstring(content)
    assert root.findtext("title") == "Show"
    assert root.findtext("plot").strip() == "before]]>middleafter"
