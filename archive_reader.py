import subprocess
import tarfile
import uuid
import zipfile
from os import chdir, walk, mkdir, remove
from os import curdir, path
from os.path import abspath

import magic
from django.conf import settings
from django.core.exceptions import ValidationError


class ArchiveReader:
    """
    Support formats:
        * .tar.gz
        * .tar
        * .zip
        * .rar
        * .7zip
    """
    TAR_ARCHIVES_MIME_TYPES = ['application/x-bzip2',
                               'application/x-tar', 'application/gzip',
                               'application/x-xz']
    ZIP_FILE_MIME_TYPES = ['application/zip']
    SEVEN_ZIP_MIME_TYPES = ['application/x-7z-compressed']

    def __init__(self, file_path: str):
        """
        Method for initializing an archive reader. Create a temp folder
        if archive format is supporting by it
        :param file_path: archive path
        """
        mime = magic.Magic(mime=True)
        self.mime_type = mime.from_file(file_path)
        if (self.mime_type in self.TAR_ARCHIVES_MIME_TYPES) or \
                (self.mime_type in self.ZIP_FILE_MIME_TYPES) or \
                (self.mime_type in self.SEVEN_ZIP_MIME_TYPES):
            self.file = file_path
            self.tmp_folder = path.join(settings.AOI_TEMP_ROOT, str(uuid.uuid4()))
            mkdir(self.tmp_folder)
        else:
            raise ValidationError(
                'Incorrect MIME_TYPE. {} does not support'.format(
                    self.mime_type))

    @staticmethod
    def __absolute_file_paths(directory: str) -> list:
        """
        Method for getting all absolute file paths in archive.
        Example: archive/file.txt; archive/folder/file2.txt
        :param directory: path to directory
        :return: list of all abs_paths
        """
        absolute_file_paths = list()
        for dirpath, _, filenames in walk(directory):
            for f in filenames:
                absolute_file_paths.append(abspath(path.join(dirpath, f)))
        return absolute_file_paths

    def __read_from_zip(self) -> list:
        """
        Read files from zip archive
        :return: list of all files in archive
        """
        zipfile.ZipFile(self.file).extractall(self.tmp_folder)
        remove(self.file)
        return self.__absolute_file_paths(self.tmp_folder)

    def __read_from_tar(self) -> list:
        """
        Read files from tar archive
        :return: list of all files in archive
        """
        with tarfile.open(self.file) as tar:
            
            import os
            
            def is_within_directory(directory, target):
                
                abs_directory = os.path.abspath(directory)
                abs_target = os.path.abspath(target)
            
                prefix = os.path.commonprefix([abs_directory, abs_target])
                
                return prefix == abs_directory
            
            def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
            
                for member in tar.getmembers():
                    member_path = os.path.join(path, member.name)
                    if not is_within_directory(path, member_path):
                        raise Exception("Attempted Path Traversal in Tar File")
            
                tar.extractall(path, members, numeric_owner=numeric_owner) 
                
            
            safe_extract(tar, self.tmp_folder)
        remove(self.file)
        return self.__absolute_file_paths(self.tmp_folder)

    def __read_from_7z(self) -> list:
        """
        Read files from 7z archive
        :return: list of all files in archive
        """
        current_directory = path.abspath(curdir)
        chdir(self.tmp_folder)
        command = ["7z", "x", '%s' % self.file]
        subprocess.call(command)
        chdir(current_directory)
        remove(self.file)
        return self.__absolute_file_paths(self.tmp_folder)

    def get_files(self) -> tuple:
        """
        Method for reading from archive
        :return: tuple (list of files from archive, temp_folder)
        """
        if self.mime_type in self.ZIP_FILE_MIME_TYPES:
            return self.__read_from_zip(), self.tmp_folder
        elif self.mime_type in self.TAR_ARCHIVES_MIME_TYPES:
            return self.__read_from_tar(), self.tmp_folder
        elif self.mime_type in self.SEVEN_ZIP_MIME_TYPES:
            return self.__read_from_7z(), self.tmp_folder

    def return_temp_dir(self):
        return self.tmp_folder