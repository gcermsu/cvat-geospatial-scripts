import argparse
from glob import glob
import json
from typing import Dict, Optional, Tuple, Union
from xml.etree import ElementTree
import os
import numpy as np
import rasterio as rio
import pandas as pd
import shapely
import cv2 as cv
from tqdm import tqdm
from functools import partial
from warnings import warn


def main():
    
    args = parse_args()
    
    annotations_df = load_annotations(args.input_xml)
    try:
        _, colormap_dict = load_labels(args.input_xml, zero_indexed=False, return_colormap=True)
    except Exception as e:
        warn(f'Could not load colormap from XML file, \
            got {type(e) }error: {e}.\n \
            A colormap will not be written to output raster', UserWarning)
        colormap_dict = None
    
    grouped_annotations_df = annotations_df.groupby('image_name')[['image_name', 'width', 'height', 'class_idx', 'area', 'polygon', 'mask']]
    
    pbar = tqdm(total=len(grouped_annotations_df), desc='Creating raster annotations', unit='rasters')
    func = partial(
        create_raster_annotation, 
        meta_dir=args.meta_dir,
        data_path=args.output_dir,
        colormap_dict=colormap_dict,
        pbar=pbar,
    )
    grouped_annotations_df.apply(func)



def parse_args() -> argparse.Namespace:
    '''
    Parse command line arguments
    
    Returns
    -------
    args: argparse.Namespace
        The parsed arguments
    '''
    
    description = 'Convert annotations in XML CVAT 1.1 Format to Georeferenced TIFFs'
    parser = argparse.ArgumentParser(description=description)
    
    parser.add_argument(
        'input_xml',
        type=str, 
        help='Path to the XML file containing the annotations in CVAT 1.1 format',
    )
    
    parser.add_argument(
        'meta_dir',
        type=str, 
        help='Path to the directory containing the georeferencing metadata JSON files',
    )
    
    parser.add_argument(
        '-o', '--output_dir',
        type=str, 
        required=False,
        help='Path to the directory where the GeoTIFF files will be saved',
    )
    
    return process_args(parser)


def process_args(parser: argparse.ArgumentParser) -> argparse.Namespace:
    '''
    Parse the arguments and perform some additional processing and checks
    
    Parameters
    ----------
    parser: argparse.ArgumentParser
        The argument parser
    
    Returns
    -------
    args: argparse.Namespace
        The parsed arguments with additional processing and checks
    
    '''
    
    args = parser.parse_args()
    
    if args.input_xml is None:
        parser.error('Input XML file is required')
    
    elif not args.input_xml.endswith('.xml'):
        parser.error('Input XML file must be an XML file')
    
    if args.meta_dir is None:
        try:
            args.meta_dir = glob(os.path.dirname(args.input_xml) + '*json')[0]
        except IndexError:
            parser.error('Could not find valid metadata directory. Please provide a metadata directory')
        finally:
            warn(f'Metadata directory not explicitly set, trying with args.metadir', UserWarning)
    
    if not os.path.exists(args.input_xml):
        raise FileNotFoundError(f'Could not find file {args.input_xml}')
    
    if not os.path.exists(args.meta_dir):
        raise FileNotFoundError(f'Could not find directory {args.meta_dir}')
    
    
    if args.output_dir is None:
        args.output_dir = os.path.dirname(args.input_xml) + '/labels'
    
    init_dirs(args)
    
    return args



def hex_to_rgb(hex: str, include_alpha=True) -> Union[Tuple[int, int, int, int], Tuple[int, int, int]]:
    """
    Convert a hex color to an RGB tuple.

    Parameters
    ----------
    hex : str
        The hex color to convert.
    include_alpha : bool, optional
        If True, the function returns a 4-tuple with the alpha channel set to 255 (default is True).

    Returns
    -------
    Union[Tuple[int, int, int, int], Tuple[int, int, int]]
        The RGB or RGBA tuple.
    """
    
    if hex.startswith('#'):
        hex = hex[1:]
    rgb = tuple(int(hex[i:i+2], 16) for i in (0, 2, 4))
    if include_alpha:
        return rgb + (255,)
    return rgb



def load_labels(
    annotation_file: str, 
    zero_indexed: bool=False, 
    return_colormap: bool=True
) -> Union[Dict[str, int], Tuple[Dict[str, int], Dict[int, Tuple[int, int, int, int]]]]:
    """
    Load labels from an annotation XML file.

    Parameters
    ----------
    annotation_file : str
        Path to the annotation XML file.
    zero_indexed : bool, optional
        If True, labels are zero-indexed (default is False).
    return_colormap : bool, optional
        If True, the function returns a colormap dictionary (default is True).

    Returns
    -------
    Union[Dict[str, int], Tuple[Dict[str, int], Dict[int, Tuple[int, int, int, int]]]]
        If return_colormap is False, returns a dictionary mapping label names to indices.
        If return_colormap is True, returns a tuple containing the labels dictionary and a colormap dictionary.
    """
    
    et = ElementTree.parse(annotation_file)
    
    labels_dict = {}
    if return_colormap:
        colormap_dict = {}
    for i, label in enumerate(et.iter('label')):
        if not zero_indexed:
            i += 1
        labels_dict[label.find('name').text] = i
        if return_colormap:
            colormap_dict[i] = hex_to_rgb(label.find('color').text)
        
    if not return_colormap:
        return labels_dict
    return labels_dict, colormap_dict



def rle_to_mask(
    mask_rle: str, 
    mask_height: int, # height of the mask
    mask_width: int, # width of the mask
    top: int=0, # top coordinate of the mask where it begins
    left: int=0, # left coordinate of the mask where it begins
    img_height: int=256, 
    img_width: int=256
) -> np.ndarray:
    
    if mask_rle == '':
        return np.zeros((img_height, img_width), dtype=np.uint8)
    mask_rle_arr = np.array(mask_rle.split(', '))
    mask_rle_arr = mask_rle_arr.astype(int) 
    
    sub_mask = np.zeros(mask_height * mask_width, dtype=bool)
    
    start_idx = 0
    for i in range(len(mask_rle_arr)):
        if i % 2 == 1:
            start_idx += mask_rle_arr[i-1]
            length = mask_rle_arr[i]
            sub_mask[start_idx:start_idx+length] = 1
            start_idx += length
    
    sub_mask = sub_mask.reshape((mask_height, mask_width))
    mask = np.zeros((img_height, img_width), dtype=np.uint8)
    mask[top:top+mask_height, left:left+mask_width] = sub_mask
    
    return mask



def load_annotations(annotation_file: str, zero_indexed: bool=False, include_colormap: bool=True) -> pd.DataFrame:
    """
    Load annotations from an XML file in CVAT 1.1 format consisting of polygons, masks, and boxes into a DataFrame.

    Parameters
    ----------
    annotation_file : str
        The path to the XML file containing the annotations.
    zero_indexed : bool, optional
        If True, labels are zero-indexed (default is False).
    include_colormap : bool, optional
        If True, the function returns a colormap dictionary (default is True).

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the annotations with columns:
        - 'image_name': The name of the image.
        - 'label': The label of the annotation.
        - 'type': The type of the annotation ('polygon', 'mask', or 'box').
        - 'polygon': The polygon geometry (if type is 'polygon' or 'box').
        - 'mask': The mask array (if type is 'mask').
        - 'area': The area of the annotation.
        - 'height': The height of the image.
        - 'width': The width of the image.
        - 'class_idx': The index of the class label.
        - 'rgba_color': The RGBA color tuple of the class (if include_colormap is True).

    Notes
    -----
    - This function assumes that the XML file is in CVAT 1.1 format.
    - Only polygon, mask, and box annotations are supported.
    """
    if include_colormap:
        labels_dict, colormap_dict = load_labels(annotation_file, zero_indexed=zero_indexed, return_colormap=True)
    else:
        labels_dict = load_labels(annotation_file, zero_indexed=zero_indexed, return_colormap=False)

    et = ElementTree.parse(annotation_file)

    annotations_list = []
    image_annotations = list(et.iterfind('image'))
    for image_annotation in image_annotations:
        
        image_name = image_annotation.get('name')
        
        image_height = int(image_annotation.get('height'))
        image_width = int(image_annotation.get('width'))
        
        for polygon in image_annotation.iterfind('polygon'):
            
            label = polygon.get('label')
            coordinates = polygon.get('points').split(';')
            coordinates = [coordinate.split(',') for coordinate in coordinates]
            coordinates = [[float(x), float(y)] for x, y in coordinates]
            shapely_polygon = shapely.Polygon(coordinates)
            
            annotations_list.append({
                'image_name': image_name,
                'label': label,
                'type': 'polygon',
                'polygon': shapely_polygon,
                'area': shapely_polygon.area,
                'height': image_height,
                'width': image_width,
            })
            
        for mask in image_annotation.iterfind('mask'):
            
            mask_rle = mask.get('rle')
            mask_width = int(mask.get('width'))
            mask_height = int(mask.get('height'))
            top = int(mask.get('top'))
            left = int(mask.get('left'))
            label = mask.get('label')
            label_idx = labels_dict[label]
            mask = rle_to_mask(mask_rle, mask_height, mask_width, top, left, image_height, image_width)
            
            annotations_list.append({
                'image_name': image_name,
                'label': label,
                'type': 'mask',
                'mask': mask,
                'area': np.count_nonzero(mask),
                'height': image_height,
                'width': image_width,
            })
        
        for box in image_annotation.iterfind('box'):
            
            x_topleft = float(box.get('xtl'))
            y_topleft = float(box.get('ytl'))
            x_bottomright = float(box.get('xbr'))
            y_bottomright = float(box.get('ybr'))
            label = box.get('label')
            label_idx = labels_dict[label]
            
            # convert from (0, 0) being the top-left corner to (0, 0) being the bottom-left corner
            y_topleft = image_height - y_topleft
            y_bottomright = image_height - y_bottomright
            
            polygon = shapely.geometry.box(x_topleft, y_bottomright, x_bottomright, y_topleft)
            
            annotations_list.append({
                'image_name': image_name,
                'label': label,
                'type': 'box',
                'polygon': polygon,
                'area': polygon.area,
                'height': image_height,
                'width': image_width,
            })

    annotations_df = pd.DataFrame(annotations_list)
    
    annotations_df['class_idx'] = annotations_df['label'].apply(lambda x: labels_dict.get(x))
    if include_colormap:
        annotations_df['rgba_color'] = annotations_df['class_idx'].apply(lambda x: colormap_dict.get(x))

    
    return annotations_df



def create_raster_annotation(
    annotations_df: pd.DataFrame, 
    meta_dir: str,
    data_path: str, 
    colormap_dict: Optional[Dict[int, Tuple[int, int, int, int]]]=None,
    pbar: Optional[tqdm]=None
) -> None:
    '''
    Create a raster using annotations from a DataFrame.
    
    Given a DataFrame constianing annotations (polygons, masks, and class indices),
    this function creates a raster image with the annotations. Polygons are drawn
    in order of decreasing area such that smaller polygons are drawn on top of larger
    polygons. The raster is saved to the target directory with the same name as the
    corresponding image. Georeferncing metadata must be provided in the image's 
    corresponding JSON file. For more information on metadata extraction, see the 
    sampling.ipynb notebook.
    
    Parameters
    ----------
    annotations_df : pd.DataFrame
        The input Dataframe containing the annotations.
    meta_dir : str
        The path to the directory containing the georeferencing metadata JSON files.
    data_path : str
        The path to the output directory where the raster will be saved.
    colormap_dict : Dict[int, Tuple[int, int, int, int]], optional
        A dictionary mapping class indices to RGBA color tuples (default is None).
        If not provided, the function will not write a colormap to the output raster.
    pbar : tqdm, optional
        The progress bar object.
    
    Returns
    -------
    None
    
    '''
    
    image_name = annotations_df['image_name'].iloc[0]
    image_width = annotations_df['width'].iloc[0]
    image_height = annotations_df['height'].iloc[0]
    
    annotations_df = annotations_df.sort_values('area', ascending=False)
    ann_img = np.zeros((image_height, image_width), dtype=np.uint8) # since we're converting to geospatial raster, no need for 3 color channels - just 1
    
    for row in annotations_df.itertuples():
        
        if row.polygon is not np.nan: # if the row has a polygon
            points = np.array(row.polygon.exterior.coords, dtype=np.int32)
            cv.fillPoly(ann_img, [points], color=row.class_idx)
        
        elif row.mask is not np.nan: # if the row has a mask
            ann_img[row.mask > 0] = row.class_idx
        
        else:
            raise ValueError(f'No geometry or mask found for row {row.Index}')
    
    metadata_path = os.path.join(meta_dir, image_name.replace(".png", ".json"))
    with open(metadata_path, 'rb') as f:
        metadata = json.load(f)
        
    try:
        metadata['crs'] = rio.crs.CRS.from_dict(metadata['crs'])
    except:
        try:
            metadata['crs'] = rio.crs.CRS.from_string(metadata['crs'])
        except:
            raise ValueError('Could not properly extract CRS')
    
    out_meta = {
        'crs': metadata['crs'],
        'transform': metadata['transform'],
        'width': image_width,
        'height': image_height,
        'count': 1,
        'dtype': rio.uint8,
        'driver': 'GTiff',
        'compress': 'LZW',
        'nodata': 0,
    }
    
    out_path = os.path.join(data_path, image_name.replace(".png", ".tif"))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with rio.open(out_path, 'w', **out_meta) as dst:
        dst.write(ann_img, 1)
        dst.write_colormap(1, colormap_dict)
    
    if pbar is not None:
        pbar.update(1)



def init_dirs(args: argparse.Namespace) -> None:
    '''
    Initialize the output directories
    
    Parameters
    ----------
    args: argparse.Namespace
        The parsed arguments
    '''
    
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)



if __name__ == '__main__':
    main()
