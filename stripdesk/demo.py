"""A deterministic, clearly labeled synthetic strip for practicing the usual workflow."""

from PIL import Image, ImageDraw
import numpy as np


SETTINGS = {
    'origin': 32, 'pitch': 233, 'count': 4, 'first': 17,
    'top': 67, 'bottom': 237, 'ratio': '3:2', 'base': [228, 175, 130],
    'negative': True, 'dark_level': 38, 'dark_share': 0.8,
}


def scene(index, width, height):
    palettes = [
        ((44, 84, 105), (226, 176, 130), (39, 84, 74), (93, 127, 114)),
        ((48, 66, 100), (247, 154, 122), (41, 56, 80), (108, 100, 130)),
        ((43, 102, 120), (216, 227, 187), (38, 68, 62), (97, 132, 114)),
        ((62, 79, 119), (236, 199, 129), (41, 73, 88), (97, 129, 141)),
    ]
    start, end, foreground, distant = palettes[index]
    gradient = np.linspace(start, end, height).astype(np.uint8)
    image = Image.fromarray(np.repeat(gradient[:, None, :], width, axis=1))
    draw = ImageDraw.Draw(image)
    rng = np.random.default_rng(650 + index)
    draw.ellipse((148 - 12 * index, 32, 175 - 12 * index, 59), fill='#f4db9e')
    for ridge in range(4):
        cross = np.linspace(-12, width + 12, 10).astype(int)
        rise = rng.integers(-31, 13, len(cross))
        points = [(int(x), int(95 + 14 * ridge + y)) for x, y in zip(cross, rise)]
        color = tuple(int(a + ridge * (b - a) / 3) for a, b in zip(distant, foreground))
        draw.polygon(points + [(width, height), (0, height)], fill=color)
    ground = height - 19
    for tree in range(7):
        x = int(rng.integers(17, width - 15))
        h = int(rng.integers(10, 35))
        shade = tuple(max(13, value - 15) for value in foreground)
        draw.polygon([(x - h // 4, ground), (x, ground - h), (x + h // 4, ground)], fill=shade)
        draw.line((x, ground, x, ground + 6), fill=shade, width=2)
    return np.asarray(image)


def strip():
    width, height = 996, 304
    rng = np.random.default_rng(9140)
    pixels = np.empty((height, width, 3), dtype=np.float32)
    pixels[:] = [64, 37, 20]
    pixels[SETTINGS['top']:SETTINGS['bottom']] = [27, 22, 18]
    base = np.asarray(SETTINGS['base'])
    for index in range(4):
        left = SETTINGS['origin'] + SETTINGS['pitch'] * index
        patch = scene(index, SETTINGS['pitch'] - 10, SETTINGS['bottom'] - SETTINGS['top'])
        pixels[67:237, left + 5:left + 5 + patch.shape[1]] = base * (1 - (patch / 255) ** 2)
    pixels[15:44, 13:36] = base
    for x in range(48, width - 16, 27):
        pixels[28:42, x:x + 11] = [237, 218, 185]
        pixels[263:277, x:x + 11] = [237, 218, 185]
    pixels += rng.normal(0, 1.2, pixels.shape)
    return np.clip(np.rint(pixels), 0, 255).astype(np.uint8)
