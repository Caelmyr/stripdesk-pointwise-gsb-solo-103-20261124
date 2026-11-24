"""Revisioned film projects and immutable digitization runs."""

from hashlib import sha256
import json
from pathlib import Path
from shutil import rmtree
from threading import RLock
from uuid import uuid4

from werkzeug.exceptions import NotFound

from image_lab.validation import Conflict, identifier, integer, text, timestamp

from . import demo, frames, layout, raster


def read_json(path):
    try:
        return json.loads(path.read_bytes())
    except FileNotFoundError:
        raise NotFound('找不到这条底片或出片记录。') from None


def write_json(path, value):
    staging = path.with_name('.' + uuid4().hex)
    try:
        staging.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        staging.replace(path)
    finally:
        staging.unlink(missing_ok=True)


class FilmWorkspace:
    def __init__(self, location):
        self.root = Path(location) / 'strips'
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()

    def directory(self, key):
        return self.root / identifier(key)

    def strip(self, key):
        return read_json(self.directory(key) / 'strip.json')

    def strips(self):
        records = [read_json(path) for path in self.root.glob('[a-f0-9]*/strip.json')]
        return sorted(records, key=lambda record: (record['created'], record['id']), reverse=True)

    def add(self, name, image, source_name, synthetic=False):
        name = text(name, '底片名称', 84, False)
        key = uuid4().hex
        source = raster.png(image)
        size = [int(image.shape[1]), int(image.shape[0])]
        config = demo.SETTINGS if synthetic else layout.initial(size)
        record = {
            'id': key, 'name': name, 'created': timestamp(), 'revision': 1,
            'size': size, 'synthetic': synthetic, 'source_name': source_name,
            'source_sha256': sha256(source).hexdigest(), 'config': config,
            'exposure': raster.histogram(image),
        }
        staging = self.root / ('.' + key)
        try:
            (staging / 'runs').mkdir(parents=True)
            (staging / 'source.png').write_bytes(source)
            write_json(staging / 'strip.json', record)
            staging.rename(self.directory(key))
        finally:
            if staging.exists():
                rmtree(staging)
        return record

    def source(self, key):
        self.strip(key)
        return self.directory(key) / 'source.png'

    def pixels(self, key):
        return raster.read(self.source(key))

    def current(self, key, rev):
        record = self.strip(key)
        if integer(rev, '版次', 1) != record['revision']:
            raise Conflict('导线或成片设置已更新，请重新打开这条底片。')
        return record

    def configure(self, key, value):
        with self.lock:
            record = self.current(key, value.get('revision'))
            record['config'] = layout.configuration(value, record['size'])
            record['revision'] += 1
            write_json(self.directory(key) / 'strip.json', record)
            return record

    def save(self, key, revision):
        with self.lock:
            record = self.current(key, revision)
            config = record['config']
            rows = layout.regular_frames(config)
            image = self.pixels(key)
            reviews = []
            for row in rows:
                patch, box = frames.view(image, config, row['number'])
                reviews.append({**row, 'aperture': box, 'quality': frames.assess(patch)})
            run = {
                'schema': 1, 'id': uuid4().hex, 'name': record['name'], 'created': timestamp(),
                'strip_id': key, 'strip_revision': record['revision'], 'source_size': record['size'],
                'source_sha256': record['source_sha256'], 'synthetic': record['synthetic'],
                'config': config, 'frames': reviews,
            }
            write_json(self.directory(key) / 'runs' / (run['id'] + '.json'), run)
            return run

    def runs(self, key):
        self.strip(key)
        records = [read_json(path) for path in (self.directory(key) / 'runs').glob('[a-f0-9]*.json')]
        return sorted(records, key=lambda run: (run['created'], run['id']), reverse=True)

    def run(self, key, run_id):
        return read_json(self.directory(key) / 'runs' / (identifier(run_id) + '.json'))
