import argparse
import os
import json
import cv2 as cv
import numpy as np
import rasterio as rio
from warnings import warn
from tqdm import tqdm
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor
from functools import partial

def convert_png2geotiff(
    in_path: str,
    meta_dir: str,
    out_dir: str,
) -> None:
    """
    Convert a single PNG file to GeoTIFF using associated JSON metadata.

    Parameters
    ----------
    in_path : str
        Path to the input PNG file.
    meta_dir : str
        Directory containing JSON metadata files.
    out_dir : str
        Output directory where GeoTIFF will be saved.
    """
    if not os.path.exists(in_path):
        raise FileNotFoundError(f'Could not find file {in_path}')

    # Load the image
    png_img = cv.imread(in_path)
    if png_img is None:
        raise ValueError(f'Could not read PNG file {in_path}')
    
    # convert to RGB if necessary
    if len(png_img.shape) == 3 and png_img.shape[2] == 3:
        png_img = cv.cvtColor(png_img, cv.COLOR_BGR2RGB)

    # Load metadata
    metadata_path = os.path.join(meta_dir, os.path.basename(in_path).replace('.png', '.json'))
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f'Could not find metadata file {metadata_path}')
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    try:
        metadata['crs'] = rio.crs.CRS.from_dict(metadata['crs'])
    except:
        try:
            metadata['crs'] = rio.crs.CRS.from_string(metadata['crs'])
        except:
            raise ValueError('Could not properly extract CRS')
    
    # Prepare output
    out_path = os.path.join(out_dir, os.path.basename(in_path).replace('.png', '.tif'))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    height, width = png_img.shape[:2]
    out_meta = {
        'crs': metadata['crs'],
        'transform': metadata['transform'],
        'width': width,
        'height': height,
        'count': 1 if len(png_img.shape) == 2 else png_img.shape[2],
        'dtype': str(png_img.dtype),
        'driver': 'GTiff',
        'compress': 'LZW',
        'nodata': 0,
    }
    
    with rio.open(out_path, 'w', **out_meta) as dst:
        if len(png_img.shape) == 2:
            dst.write(png_img, 1)
        else:
            for i in range(png_img.shape[2]):
                dst.write(png_img[:,:,i], i + 1)
    
    # print(f'Successfully wrote GeoTIFF to {out_path}')

def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments for png2geotiff conversion.

    Returns
    -------
    argparse.Namespace
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(description='Convert PNG files + JSON metadata to GeoTIFF')
    parser.add_argument('input', type=str, help='Path to directory containing PNG files')
    parser.add_argument('meta_dir', type=str, help='Path to directory with JSON metadata')
    parser.add_argument('-o','--output_dir', type=str, default=None, required=False, help='Output directory')
    parser.add_argument('-t','--threads', type=int, default=1, help='Number of threads to use')
    return process_args(parser.parse_args())



def process_args(args: argparse.Namespace) -> argparse.Namespace:
    """
    Process command line arguments for png2geotiff conversion.

    Parameters
    ----------
    args : argparse.Namespace
        The parsed arguments.

    Returns
    -------
    argparse.Namespace
        The processed arguments.
    """
    # Check if output directory is provided
    if args.output_dir is None:
        args.output_dir = args.input + '_geotiff'
    return args



def main() -> None:
    """
    Main function to handle multithreaded PNG-to-GeoTIFF conversions with TQDM progress bar.
    """
    args = parse_args()
    if not os.path.isdir(args.input):
        raise NotADirectoryError(f'Input path `{args.input}` is not a directory or does not exist')
    png_paths = [os.path.join(args.input, f) for f in os.listdir(args.input) if f.lower().endswith('.png')]
    os.makedirs(args.output_dir, exist_ok=True)

    pbar = tqdm(total=len(png_paths), desc='Converting PNGs', unit='files')
    worker = partial(convert_png2geotiff, meta_dir=args.meta_dir, out_dir=args.output_dir)
    if args.threads > 1:
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            for _ in executor.map(worker, png_paths):
                pbar.update(1)
    else:
        for path in png_paths:
            worker(path)
            pbar.update(1)

    pbar.close()

if __name__ == '__main__':
    exit(main())
