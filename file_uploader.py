import shutil
import uuid
from os import path, remove

import magic
from django.conf import settings
from django.core.exceptions import ValidationError

from archive_reader import ArchiveReader
from validators import VectorValidator, KMZValidator, \
    KMLValidator, GeoJSONValidator, ShapeValidator, AOI_TEMP_ROOT
from osgeo import ogr

MAX_VECTOR_FILE_SIZE = getattr(settings, 'MAX_VECTOR_FILE_SIZE')


class VectorFileUploader:
    """
    Supported formats:
    * .geojson
    * .kml
    * .kmz
    * .zip
    * .tar.gz
    * .tar.xz
    """

    FILE_TYPES = ['application/xml', 'text/plain', 'text/html']

    ARCHIVE_TYPES = ['application/zip', 'application/x-bzip2',
                     'application/x-tar', 'application/gzip',
                     'application/x-xz', 'application/zip',
                     'application/x-7z-compressed']
    TEMP_FOLDER = None
    OUTPUT_DATASOURCE = None

    def __init__(self, file_path):
        self.file = file_path
        mime = magic.Magic(mime=True)
        self.mime_type = mime.from_file(file_path)
        if path.getsize(self.file) >= MAX_VECTOR_FILE_SIZE:
            raise ValidationError(
                'File size more than {}'.format(MAX_VECTOR_FILE_SIZE))

        if (self.mime_type not in self.FILE_TYPES) and \
                (self.mime_type not in self.ARCHIVE_TYPES):
            raise TypeError('{} not supported by this class. '
                            'Supported file types: {} '
                            'and archive types: {}'.format(self.mime_type,
                                                           self.FILE_TYPES,
                                                           self.ARCHIVE_TYPES))

    @staticmethod
    def __get_vector_files_from_archive(files_from_archive: list) -> list:
        """
        Getting all supporting Shape vector files from archive file
        :param files_from_archive: file_paths from archive
        :return: list of vector files from archive
        """
        vector_files = []
        for file in files_from_archive:
            if file.lower().endswith('kml') or file.lower().endswith(
                    'geojson') or file.lower().endswith('shp'):
                vector_files.append(file)
        return vector_files

    def __get_driver_for_file(self) -> VectorValidator:
        """
        Method for getting driver for one file [.geojson, .kml]
        :param file: uploaded file
        :return: Vector file driver instance
        """
        if KMZValidator().driver_validation(self.file):
            return KMZValidator()
        elif KMLValidator.driver_validation(self.file):
            return KMLValidator()
        elif GeoJSONValidator.driver_validation(self.file):
            return GeoJSONValidator()

    def __write_geometry_by_type(self, geom_types):
        """
        Method for writing geometry by type to data_source
        :param geom_types: list of geometry_types
        :return: None
        """
        files = list()
        shp_files = list()
        archive_reader = None
        if self.mime_type in self.FILE_TYPES:
            files.append(self.file)
        else:
            archive_reader = ArchiveReader(self.file)
            files, self.TEMP_FOLDER = archive_reader.get_files()

        self.file = files.pop()
        while self.file:
            driver = self.__get_driver_for_file()
            if driver:
                driver.write_geometry_to_data_source(self.OUTPUT_DATASOURCE,
                                                     self.file,
                                                     types=geom_types)
            else:
                shp_files.append(self.file)
            self.file = files.pop() if files else None

        if shp_files:
            ShapeValidator().get_geometry_from_shp_files(
                self.OUTPUT_DATASOURCE, extracted_files=shp_files,
                types=geom_types)
        if archive_reader:
            shutil.rmtree(archive_reader.return_temp_dir(),
                          ignore_errors=True)
        self.OUTPUT_DATASOURCE = None

    def create_output_data_source(self, types: list() = list()):
        """
        Method for creating a new DataSource
        :param types: geom types [POLYGON, LINESTRING, POINT, etc.]
        :return: new DataSource's name
        """
        name = path.join(AOI_TEMP_ROOT, str(uuid.uuid4()) + '.geojson')
        outdriver = ogr.GetDriverByName('GeoJson')
        self.OUTPUT_DATASOURCE = outdriver.CreateDataSource(name)
        try:
            self.__write_geometry_by_type(types)
        except Exception as e:
            if self.TEMP_FOLDER:
                shutil.rmtree(self.TEMP_FOLDER, ignore_errors=True)
            remove(name)
            raise e
        return name
