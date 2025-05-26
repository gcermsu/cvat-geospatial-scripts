import json
from typing import List, Optional
import rasterio as rio
import cv2 as cv
import argparse
from glob import glob
from tqdm import tqdm 
import os
from functools import partial
from warnings import warn

def main():
    
    args = parse_args()
    
    in_paths = glob(args.input + os.sep + '*.tif')
    filenames = [os.path.basename(f).split('.')[0] for f in in_paths]
    
    pbar = tqdm(total=len(in_paths), desc='Converting GeoTIFFs', unit='files')
    
    out_paths = [args.output + os.sep + f + '.' + args.format for f in filenames]
    if args.json_output is not None:
        json_out_paths = [args.json_output + os.sep + f + '.json' for f in filenames]
    else:
        json_out_paths = [None] * len(in_paths)
    
    conv_func = partial(
        convert_geotiff,
        bands=args.bands,
        compression=args.compression,
        pbar=pbar
    )
    
    if args.threads > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            executor.map(conv_func, in_paths, out_paths, json_out_paths)
    else:
        for in_path, out_path, json_out_path in zip(in_paths, out_paths, json_out_paths):
            conv_func(in_path, out_path, json_out_path)


def convert_geotiff(
    in_path: str, 
    out_path: str,
    json_out_path: Optional[str]=None,
    bands: List[int]=[1, 2, 3],
    compression: int=3,
    pbar: Optional[tqdm]=None
) -> None:
    
    with rio.open(in_path) as src:
        
        data = src.read(bands).transpose(1, 2, 0)
        if json_out_path is not None:
            meta = src.meta
    
    if len(bands) == 3:
        data = cv.cvtColor(data, cv.COLOR_BGR2RGB)
    else: # len(bands) == 1
        data = data.squeeze() # Remove the singleton dimension
    
    if out_path.split('.')[-1] == 'jpg' or out_path.split('.')[-1] == 'jpeg':
        cv.imwrite(out_path, data, [int(cv.IMWRITE_JPEG_QUALITY), compression])
    elif out_path.split('.')[-1] == 'png':
        cv.imwrite(out_path, data, [int(cv.IMWRITE_PNG_COMPRESSION), compression])
    elif out_path.split('.')[-1] == 'tif':
        cv.imwrite(out_path, data, [int(cv.IMWRITE_TIFF_COMPRESSION), compression])
    else:
        out_format = out_path.split('.')[-1]
        raise ValueError(f'Output format `{out_format}` not supported')
    
    if json_out_path is not None:
        try:
            meta['crs'] = src.crs.to_dict()
        except:
            try:
                meta['crs'] = str(src.crs)
            except:
                raise ValueError('Could not propoerly extract CRS')
        
        with open(json_out_path, 'w') as f:
            json.dump(meta, f, indent=4)

    if pbar is not None:
        pbar.update(1)


def parse_args() -> argparse.Namespace:
    '''
    Parse command line arguments
    
    Returns
    -------
    args: argparse.Namespace
        The parsed arguments
    '''
    
    description = 'Convert GeoTIFF data to PNG and save georeferencing information in a JSON file'
    parser = argparse.ArgumentParser(description=description)
    
    parser.add_argument(
        'input',
        type=str, 
        help='Path to the directory containing the GeoTIFF files'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str, 
        required=False,
        help='Path to the directory where the PNG/JSON files will be saved',
    )
    
    parser.add_argument(
        '-t', '--threads',
        type=int,
        required=False,
        help='Number of threads to use for processing',
        default=1
    )
    
    parser.add_argument(
        '-b', '--bands',
        type=int,
        nargs='+',
        required=False,
        help='Band indeces to extract from raster. Must be either 1 or 3 bands. Default is 1 2 3.',
        default=[1, 2, 3],
    )
    
    parser.add_argument(
        '-f', '--format',
        type=str, 
        required=False,
        help='Output format for the image files. Options are png, jpg, and jpeg. Default is png.',
        default='png',
        choices=['png', 'jpg', 'jpeg']
    )
    
    parser.add_argument(
        '-c', '--compression',
        type=int, 
        required=False,
        help='Compression level for the image files. 0 is no compression, 9 is maximum compression. Default is 3.',
        default=3,
        choices=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    )
    
    parser.add_argument(
        '-jo', '--json_output',
        type=str,
        required=False,
        help='Path to the directory where the JSON files will be saved',
    )
    
    parser.add_argument(
        '-nj', '--no_json',
        action='store_true',
        help='Do not save the georeferencing information in a JSON file. Default is False',
        default=False
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
    
    if args.no_json and args.json_output is not None:
        warn('Ignoring --json_output since --no_json is set', RuntimeWarning)
        args.json_output = None
    
    if len(args.bands) != 3 and len(args.bands) != 1:
        parser.error(f'Can only specify 1 or 3 bands, not {len(args.bands)}')
    
    if args.input is None:
        parser.error('Input directory is required')
    
    if args.input[-1] == os.sep:
        args.input = args.input[:-1]
    
    if args.output is None:
        args.output = args.input + '_' + args.format
    
    if args.json_output is None and not args.no_json:
        args.json_output = args.input + '_' + 'json'
    
    init_dirs(args)
    
    return args



def init_dirs(args: argparse.Namespace) -> None:
    '''
    Initialize the output directories
    
    Parameters
    ----------
    args: argparse.Namespace
        The parsed arguments
    '''
    
    if not os.path.exists(args.output):
        os.makedirs(args.output)
    
    if not os.path.exists(args.json_output):
        os.makedirs(args.json_output)



if __name__ == '__main__':
    exit(main())