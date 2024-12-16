# CVAT Geospatial Tools
This repository contains scripts for converting between CVAT-compatible file formats and geospatial rasters. 

## Requirements
The scripts are written in Python and require the following libraries:

- `rasterio`
- `numpy`
- `shapely`
- `pandas`
- `opencv-python`

These scripts have been tested with Python 3.8.19.

## Usage

### `geotiff2png.py`

Convert a directory of GeoTIFF files to PNG (or JPEG) images. The georeferencing metadata is stored in a JSON file in a separate directory.

#### Examples

Convert all GeoTIFF files in the `input` directory to PNG images in the `input_png` directory with the georeferencing metadata stored in the `input_json` directory:

```
$ python geotiff2png.py input
```

The resulting directory structure will be:

```
input
├── image1.tif
├── image2.tif
└── ...
input_json
├── image1.json
├── image2.json
└── ...
input_png
├── image1.png
├── image2.png
└── ...
```

See `python geotiff2png.py --help` for more options.

```
$ python geotiff2png.py --help
usage: geotiff2png.py [-h] [-o OUTPUT] [-t THREADS] [-b BANDS [BANDS ...]] [-f {png,jpg,jpeg}] [-c {0,1,2,3,4,5,6,7,8,9}] [-jo JSON_OUTPUT] [-nj] input

Convert GeoTIFF data to PNG and save georeferencing information in a JSON file

positional arguments:
  input                 Path to the directory containing the GeoTIFF files

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT, --output OUTPUT
                        Path to the directory where the PNG/JSON files will be saved
  -t THREADS, --threads THREADS
                        Number of threads to use for processing
  -b BANDS [BANDS ...], --bands BANDS [BANDS ...]
                        Band indeces to extract from raster. Must be either 1 or 3 bands. Default is 1 2 3.
  -f {png,jpg,jpeg}, --format {png,jpg,jpeg}
                        Output format for the image files. Options are png, jpg, and jpeg. Default is png.
  -c {0,1,2,3,4,5,6,7,8,9}, --compression {0,1,2,3,4,5,6,7,8,9}
                        Compression level for the image files. 0 is no compression, 9 is maximum compression. Default is 3.
  -jo JSON_OUTPUT, --json_output JSON_OUTPUT
                        Path to the directory where the JSON files will be saved
  -nj, --no_json        Do not save the georeferencing information in a JSON file. Default is False
```

### `xml2geotiff.py`

Given an XML file with polygon, shape, or mask annotations in [CVAT 1.1 format](https://docs.cvat.ai/docs/manual/advanced/xml_format/#version-11) and a directory of JSON files containing georeferencing metadata, convert the annotations to a geo-referenced GeoTIFF file.

NOTE: Annotations must be in CVAT 1.1 format, which is the default format for annotations exported from CVAT. The JSON files containing the georeferencing metadata must have the same name as the corresponding image name in the XML file.

#### Examples

Convert the annotations in `annotations.xml` to GeoTIFFs using the georeferencing metadata in the `input_json` directory:

```
$ python xml2geojson.py annotations.xml input_json
```

The resulting directory structure will be:

```
annotations.xml
input_json
├── image1.json
├── image2.json
└── ...
labels
├── image1.tif
├── image2.tif
└── ...
```

See `python xml2geotiff.py --help` for more options.

```
$ python xml2geotiff.py --help
usage: xml2geotiff.py [-h] [-o OUTPUT_DIR] input_xml meta_dir

Convert annotations in XML CVAT 1.1 Format to Georeferenced TIFFs

positional arguments:
  input_xml             Path to the XML file containing the annotations in CVAT 1.1 format
  meta_dir              Path to the directory containing the georeferencing metadata JSON files

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUT_DIR, --output_dir OUTPUT_DIR
                        Path to the directory where the GeoTIFF files will be saved
```

## Issues

Please report any issues or feature requests using the GitHub issue tracker.

## License

These scripts are licensed under the MIT License, and are provided without warranty of any kind. See the [LICENSE](LICENSE) file for more information.

## Acknowledgements

These scripts were developed by the [Geospatial Computing for Environmental Research (GCER) Lab](https://www.gcerlab.com/) at Mississippi State University. 
