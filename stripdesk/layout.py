"""Native coordinates for regular guides and the scan's measured dark bands."""

import numpy as np

from image_lab.validation import Invalid, integer, number

from . import raster

RATIOS = {'native': None, '3:2': (3, 2), '4:3': (4, 3), '1:1': (1, 1), '2:3': (2, 3)}


def initial(size):
    width, height = size
    return {
        'origin': 0, 'pitch': width, 'count': 1, 'first': 1,
        'top': 0, 'bottom': height, 'ratio': 'native',
        'base': [222, 174, 131], 'negative': True,
        'dark_level': 36, 'dark_share': 0.8,
    }


def configuration(value, size):
    width, height = size
    origin = integer(value.get('origin'), '起点', 0, width - 8)
    pitch = integer(value.get('pitch'), '帧距', 8, width)
    count = integer(value.get('count'), '张数', 1, 24)
    first = integer(value.get('first'), '首张片号', 1, 9976)
    top = integer(value.get('top'), '上边', 0, height - 8)
    bottom = integer(value.get('bottom'), '下边', top + 8, height)
    if origin + pitch * count > width:
        raise Invalid('底片导线超出原片宽度。')
    ratio = value.get('ratio')
    if not isinstance(ratio, str) or ratio not in RATIOS:
        raise Invalid('请选择有效的成片比例。')
    base = value.get('base')
    if not isinstance(base, list) or len(base) != 3:
        raise Invalid('片基需有三个 RGB 通道。')
    negative = value.get('negative')
    if type(negative) is not bool:
        raise Invalid('请选择负片转正或维持原色。')
    return {
        'origin': origin, 'pitch': pitch, 'count': count, 'first': first,
        'top': top, 'bottom': bottom, 'ratio': ratio,
        'base': [integer(channel, '片基值', 8, 255) for channel in base],
        'negative': negative,
        'dark_level': integer(value.get('dark_level'), '暗值上限', 1, 254),
        'dark_share': number(value.get('dark_share'), '暗像素比例', 0.1, 1),
    }


def regular_frames(config):
    return [{
        'number': config['first'] + index,
        'left': config['origin'] + index * config['pitch'],
        'right': config['origin'] + (index + 1) * config['pitch'],
    } for index in range(config['count'])]


def inspect_columns(source, config):
    """Expose measured darkness over the selected band, independent of guide spacing."""
    start, stop = config['top'], config['bottom']
    luma = raster.gray(source[start:stop])
    dark = (luma <= config['dark_level']).mean(axis=0)
    columns = dark >= config['dark_share']
    edges = np.diff(np.pad(columns.astype(np.int8), (1, 1)))
    starts = np.flatnonzero(edges == 1)
    stops = np.flatnonzero(edges == -1)
    bands = [{
        'left': int(left), 'right': int(right),
        'average': round(float(dark[left:right].mean()), 3),
    } for left, right in zip(starts, stops)]
    return {
        'row_range': [start, stop],
        'fractions': np.round(dark, 4).tolist(),
        'bands': bands,
        'threshold': config['dark_share'],
    }
