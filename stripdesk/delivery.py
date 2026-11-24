"""Production packet for a saved scan and the numbered positive crops."""

import csv
from io import BytesIO, StringIO
import json
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from . import frames, raster


def index_csv(rows):
    text = StringIO(newline='')
    writer = csv.writer(text)
    writer.writerow(['film_number', 'guide_left', 'guide_right', 'aperture_x0', 'aperture_y0',
                     'aperture_x1', 'aperture_y1', 'shadow_fraction', 'highlight_fraction'])
    for row in rows:
        quality = row['quality']
        writer.writerow([row['number'], row['left'], row['right'], *row['aperture'],
                         quality['shadows'], quality['highlights']])
    return text.getvalue().encode('utf-8-sig')


def archive(source_png, image, run):
    data = BytesIO()
    config = run['config']
    rows = run['frames']
    with ZipFile(data, 'w', compression=ZIP_DEFLATED, compresslevel=4) as bundle:
        bundle.writestr(ZipInfo('source.png'), source_png, ZIP_DEFLATED, 4)
        bundle.writestr(ZipInfo('contact.png'), raster.png(frames.contact(image, config, rows)), ZIP_DEFLATED, 4)
        bundle.writestr(ZipInfo('frames.csv'), index_csv(rows), ZIP_DEFLATED, 4)
        bundle.writestr(ZipInfo('run.json'), json.dumps(run, ensure_ascii=False, indent=2), ZIP_DEFLATED, 4)
        for row in rows:
            number = row['number']
            patch, _ = frames.view(image, config, number)
            bundle.writestr(ZipInfo(f'frames/film-{number:04}.png'), raster.png(patch), ZIP_DEFLATED, 4)
    return data.getvalue()
