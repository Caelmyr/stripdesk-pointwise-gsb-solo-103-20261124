"""Positive rendering and native centered apertures for each numbered film image."""

from PIL import Image, ImageDraw
import numpy as np

from image_lab.validation import Invalid, integer

from . import layout, raster


def fixed_gate(config, number):
    """Rebuild the native rectangle from the plate number and active guide edges."""
    rows = layout.guide_frames(config)
    for row in rows:
        if row['number'] == integer(number, '片号', config['first'],
                                    config['first'] + config['count'] - 1):
            return [row['left'], config['top'], row['right'], config['bottom']]
    raise Invalid('找不到该片号的导线。')


def aperture(config, number):
    left, top, right, bottom = fixed_gate(config, number)
    pair = layout.RATIOS[config['ratio']]
    if pair:
        width, height = right - left, bottom - top
        scale = min(width // pair[0], height // pair[1])
        cut_w, cut_h = pair[0] * scale, pair[1] * scale
        left += (width - cut_w) // 2
        top += (height - cut_h) // 2
        right, bottom = left + cut_w, top + cut_h
    return [left, top, right, bottom]


def positive(pixels, config):
    if not config['negative']:
        return pixels
    base = np.asarray(config['base'], dtype=np.float32)
    density = np.clip(1 - pixels / base, 0, 1)
    return np.rint(np.sqrt(density) * 255).astype(np.uint8)


def view(source, config, number):
    left, top, right, bottom = aperture(config, number)
    raw = source[top:bottom, left:right]
    return positive(raw, config), [left, top, right, bottom]


def probe(source, config, x, y):
    height, width = source.shape[:2]
    x = integer(x, '原片 X', 0, width - 1)
    y = integer(y, '原片 Y', 0, height - 1)
    color = source[y, x]
    sample = source[max(0, y - 2):min(y + 3, height), max(0, x - 2):min(x + 3, width)]
    return {
        'xy': [x, y], 'raw': color.tolist(),
        'positive': positive(color, config).tolist(),
        'base_sample': np.maximum(8, np.median(sample, axis=(0, 1)).astype(int)).tolist(),
    }


def assess(scene):
    if not scene.size:
        raise Invalid('成片画幅为空。')
    luma = raster.gray(scene)
    shadow = np.count_nonzero(luma <= 12) / luma.size
    highlight = np.count_nonzero(luma >= 243) / luma.size
    levels = np.percentile(luma, [5, 95])
    return {'shadows': round(float(shadow), 4), 'highlights': round(float(highlight), 4),
            'luma_5_95': np.rint(levels).astype(int).tolist()}


def contact(source, config, rows):
    columns = min(4, len(rows))
    lines = (len(rows) + columns - 1) // columns
    tile_w, tile_h = 240, 184
    sheet = Image.new('RGB', (columns * tile_w, lines * tile_h), '#1c2521')
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(rows):
        image, _ = view(source, config, row['number'])
        tile = Image.fromarray(image)
        tile.thumbnail((tile_w - 20, tile_h - 30), Image.Resampling.LANCZOS)
        x, y = (index % columns) * tile_w, (index // columns) * tile_h
        sheet.paste(tile, (x + (tile_w - tile.width) // 2, y + (tile_h - 24 - tile.height) // 2))
        draw.text((x + 10, y + tile_h - 20), f"#{row['number']:04}", fill='#e9edd7')
    return np.asarray(sheet)
