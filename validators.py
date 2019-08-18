import ast
import json
from os import path

import magic
from django.conf import settings
from django.contrib.gis.gdal.datasource import DataSource
from osgeo import ogr, osr

AOI_TEMP_ROOT = getattr(settings, 'AOI_TEMP_ROOT')


class VectorValidator:
    """
    Base vector validation class.
    Support vector formats:
     * .kml
     * .geojson / .json
     * .kmz
     * .shp
    """

    def __set_data_source(self, file_name: str):
        """
        Method for getting dataSource from file
        :param file_name: vector file name
        :return: DataSource
        """
        driver = ogr.GetDriverByName(self.driver_name)
        dataSource = driver.Open(file_name)
        for layer_index in range(0, dataSource.GetLayerCount()):
            ds_layer = dataSource.GetLayerByIndex(layer_index)
            if ds_layer.GetFeatureCount() == 0:
                dataSource = ogr.Open(file_name)
        self.DATA_SOURCE = dataSource

    def write_geometry_to_data_source(self, data_source, tmp_file_name: str,
                                      types: list = list()):
        """
        Method for getting geometries from file.
        :param tmp_file_name: file path
        :param types: list of types of geometry [POLYGON, LINESTRING]
        """
        self.__set_data_source(file_name=tmp_file_name)
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        index = 0
        for layer_index in range(0, self.DATA_SOURCE.GetLayerCount()):
            if not data_source.GetLayer():
                out_layer = data_source.CreateLayer(
                    name='layer_{}'.format(index + 1), srs=srs)
            else:
                out_layer = data_source.GetLayer()

            ds_layer = self.DATA_SOURCE.GetLayerByIndex(layer_index)
            feature = ds_layer.GetNextFeature()
            feature_defn = ds_layer.GetLayerDefn()
            while feature:
                out_feature = ogr.Feature(feature_defn)
                geom = feature.geometry()
                if (types and geom.GetGeometryName() in types) or not types:
                    cr_geom = ogr.CreateGeometryFromWkt(str(geom))
                    out_feature.SetGeometry(cr_geom)
                out_layer.CreateFeature(out_feature)
                feature = ds_layer.GetNextFeature()
            out_layer = None
        data_source = None


class ShapeValidator(VectorValidator):
    """
    Class for shp validator
    """
    SHP_SET = {'dbf', 'shp', 'shx', 'prj'}

    def __init__(self):
        self.driver_name = 'ESRI Shapefile'

    @staticmethod
    def driver_validation(files: list) -> bool:
        """
        Validate input SHP file
        """
        files_extension = []
        for el in files:
            if len(el.lower().rsplit('.', 1)) > 1:
                files_extension.append(el.rsplit('.', 1)[1])
            else:
                pass
        if ShapeValidator.SHP_SET.issubset(files_extension):
            return True
        else:
            return False

    def get_shp_files(self, extracted_files: list) -> list:
        """
        Method for getting only .shp files from list of files
        :param extracted_files:
        :return: list with shp files
        """
        shp_list = list()
        for file in extracted_files:
            if file.endswith('.shp'):
                shp_list.append(file)
        return shp_list

    def get_geometry_from_shp_files(self, data_source, extracted_files: list,
                                    types):
        """
        Method for merging shp files into one file.
        :param extracted_files: list of shp files.
        :return: new shp file and tmp dir where shp file with supported exist
        """
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        shp_files = self.get_shp_files(extracted_files)
        name = data_source.GetName()
        if len(shp_files) >= 1:
            for file in shp_files:
                if file.endswith('.shp'):
                    if data_source is None:
                        data_source = ogr.Open(path.abspath(name))
                    self.write_geometry_to_data_source(data_source, file,
                                                       types)

    def check_count_of_shp(self, extracted_files: list) -> bool:
        """
        Method for check if one shp file in archive.
        :param extracted_files: list of files.
        :return: True if more then one, else False
        """
        count = 0
        is_not_one_flag = False
        for file in extracted_files:
            if file.lower().endswith('.shp'):
                count = count + 1
                if count > 1:
                    is_not_one_flag = True
                    break
        return is_not_one_flag


class KMLValidator(VectorValidator):
    """
    Class for kml validator
    """

    def __init__(self):
        self.driver_name = 'KML'

    @staticmethod
    def driver_validation(file: str) -> bool:
        """
        Validate input KML file
        """
        mime_type = magic.from_file(file, mime=True)
        if mime_type in ['application/xml',
                         'text/plain', 'text/html'] \
                and file.lower().endswith('.kml'):
            return True
        else:
            return False


class KMZValidator(KMLValidator):
    """
    Class for kmz validator
    """
    KMZ_SET = {'kml'}

    @staticmethod
    def driver_validation(file: str) -> bool:
        """
        Validate input KML file
        """
        mime_type = magic.from_file(file, mime=True)
        if mime_type in ['application/xml',
                         'text/plain'] and file.lower().endswith('.kml'):
            return True
        else:
            return False


class GeoJSONValidator(VectorValidator):
    """
    Class for geojson validator
    """
    """
        GeoJSON driver
        """

    def __init__(self):
        self.driver_name = 'GeoJson'

    @staticmethod
    def driver_validation(file: str) -> bool:
        """
        Validate input GeoJSON file
        """
        mime_type = magic.from_file(file, mime=True)
        if mime_type == 'text/plain':
            try:
                data = ast.literal_eval(json.dumps(open(file).read()))
                if type(json.loads(data)) != dict:
                    return False
                DataSource(file)
                return True
            except Exception:
                return False
        else:
            return False
