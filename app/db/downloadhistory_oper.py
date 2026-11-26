from typing import List, Optional

from app.db import DbOper
from app.db.models.downloadhistory import DownloadHistory, DownloadFiles


class DownloadHistoryOper(DbOper):
    """
    下载历史管理
    """

    def get_by_path(self, path: str) -> DownloadHistory:
        """
        按路径查询下载记录
        :param path: 数据key
        """
        return DownloadHistory.get_by_path(self._db, path)

    def get_by_hash(self, download_hash: str) -> DownloadHistory:
        """
        按Hash查询下载记录
        :param download_hash: 数据key
        """
        return DownloadHistory.get_by_hash(self._db, download_hash)

    def add(self, **kwargs):
        """
        新增下载历史
        """
        DownloadHistory(**kwargs).create(self._db)

    def add_files(self, file_items: List[dict]):
        """
        新增下载历史文件
        """
        for file_item in file_items:
            downloadfile = DownloadFiles(**file_item)
            downloadfile.create(self._db)

    def get_files_by_hash(self, download_hash: str, state: Optional[int] = None) -> List[DownloadFiles]:
        """
        按Hash查询下载文件记录
        :param download_hash: 数据key
        :param state: 删除状态
        """
        return DownloadFiles.get_by_hash(self._db, download_hash, state)

    def get_file_by_fullpath(self, fullpath: str) -> DownloadFiles:
        """
        按fullpath查询下载文件记录
        :param fullpath: 数据key
        """
        return DownloadFiles.get_by_fullpath(self._db, fullpath=fullpath, all_files=False)

    def get_files_by_savepath(self, fullpath: str) -> List[DownloadFiles]:
        """
        按savepath查询下载文件记录
        :param fullpath: 数据key
        """
        return DownloadFiles.get_by_savepath(self._db, fullpath)

    def delete_file_by_fullpath(self, fullpath: str, download_hash: Optional[str] = None):
        """
        按fullpath删除下载文件记录
        :param fullpath: 数据key
        :param download_hash: 限定所属种子，兼容存量的相对路径记录
        """
        return DownloadFiles.delete_by_fullpath(self._db, fullpath, download_hash)

    def backfill_savepath(self, download_hash: str, save_path: str) -> int:
        """
        回填种子的保存根目录并补齐相对路径记录
        :param download_hash: 种子 Hash
        :param save_path: 保存根目录
        """
        return DownloadFiles.backfill_savepath(self._db, download_hash, save_path)
