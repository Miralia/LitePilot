from typing import List, Optional

from app.db import DbOper, SessionFactory
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
        if not file_items:
            return
        db = self._db or SessionFactory()
        close_db = self._db is None
        try:
            # create() 每行都会独立提交；大型种子一次可能包含数百个文件，
            # 批量插入必须共享一个事务以避免 SQLite 写放大。
            db.add_all([DownloadFiles(**file_item) for file_item in file_items])
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            if close_db:
                db.close()

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

    def delete_files_missing_for_downloader(
        self,
        downloader: str,
        active_hashes: set[str],
    ) -> int:
        """
        删除指定下载器中已不再存在的种子文件记录。

        :param downloader: 已成功列出任务的下载器名称
        :param active_hashes: 当前仍存在于该下载器中的种子 Hash
        :return: 删除的文件记录数
        """
        return DownloadFiles.delete_missing_for_downloader(
            self._db,
            downloader=downloader,
            active_hashes=active_hashes,
        )

    def backfill_savepath(self, download_hash: str, save_path: str) -> int:
        """
        回填种子的保存根目录并补齐相对路径记录
        :param download_hash: 种子 Hash
        :param save_path: 保存根目录
        """
        return DownloadFiles.backfill_savepath(self._db, download_hash, save_path)
