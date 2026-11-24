"""Canonical RGB source and image measures in native image coordinates."""

from io import BytesIO
import warnings

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from image_lab.validation import Invalid

MAX_BYTES = 24 * 1024 * 1024
MAX_PIXELS = 8_000_000
FORMATS = {'PNG', 'JPEG', 'TIFF', 'BMP', 'WEBP'}


def check_size(size):
    width, height = size
    if not (8 <= width <= 4096 and 8 <= height <= 4096 and width * height <= MAX_PIXELS):
        raise Invalid('图片需在 8 至 4096 像素之间，且总像素不超过 800 万。')


def decode(raw):
    if len(raw) > MAX_BYTES:
        raise Invalid('单张底片扫描不得超过 24 MiB。')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as source:
                if source.format not in FORMATS or getattr(source, 'n_frames', 1) != 1:
                    raise Invalid('请上传单帧 PNG、JPEG、TIFF、BMP 或 WebP。')
                check_size(source.size)
                oriented = ImageOps.exif_transpose(source)
                return np.array(oriented.convert('RGB'), dtype=np.uint8)
    except (OSError, UnidentifiedImageError, Image.DecompressionBombWarning, Image.DecompressionBombError) as error:
        raise Invalid('图片损坏、编码不受支持或像素过多。') from error


def read(path):
    with Image.open(path) as source:
        return np.asarray(source)


def png(pixels):
    buffer = BytesIO()
    Image.fromarray(pixels).save(buffer, format='PNG', compress_level=3)
    return buffer.getvalue()


def gray(pixels):
    return cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)


def histogram(pixels):
    gray_values = gray(pixels)
    bins = np.bincount(gray_values.ravel(), minlength=256)
    coarse = bins.reshape(32, 8).sum(axis=1)
    return {'histogram': coarse.tolist(),
            'saturated': int(np.count_nonzero(np.max(pixels, axis=2) >= 250)),
            'mean': round(float(np.mean(gray_values)), 2)}
