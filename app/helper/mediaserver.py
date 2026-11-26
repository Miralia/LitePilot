from app.helper.service import ServiceBaseHelper
from app.schemas import MediaServerConf
from app.schemas.types import SystemConfigKey, ModuleType


class MediaServerHelper(ServiceBaseHelper[MediaServerConf]):
    """
    媒体服务器帮助类
    """

    def __init__(self):
        super().__init__(
            config_key=SystemConfigKey.MediaServers,
            conf_type=MediaServerConf,
            module_type=ModuleType.MediaServer
        )
