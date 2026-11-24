"""Browser and export entry points for digitizing horizontal film strips."""

from io import BytesIO
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request, send_file

from image_lab import create_app as preparation_app
from image_lab.validation import Invalid, object_value

from . import delivery, demo, frames, layout, raster
from .workspace import FilmWorkspace


def body():
    return object_value(request.get_json(silent=True), '底片操作')


def png(pixels):
    return send_file(BytesIO(raster.png(pixels)), mimetype='image/png', max_age=0)


def create_app(root):
    app = preparation_app(root / 'prepare')
    desk = FilmWorkspace(root)
    api = Blueprint('strip', __name__, url_prefix='/strip')

    @app.get('/')
    def home():
        return render_template('stripdesk.html')

    @api.get('/health')
    def health():
        return jsonify(status='ready', service='stripdesk')

    @api.route('/strips', methods=['GET', 'POST'])
    def strips():
        if request.method == 'GET':
            return jsonify(desk.strips())
        item = request.files.get('image')
        if item is None or not item.filename:
            raise Invalid('请选择一张水平底片扫描图。')
        name = Path(item.filename).name[:120]
        image = raster.decode(item.stream.read(raster.MAX_BYTES + 1))
        return jsonify(desk.add(request.form.get('name') or Path(name).stem[:84], image, name)), 201

    @api.post('/demo')
    def practice_strip():
        return jsonify(desk.add('山景练习条 · 合成扫描', demo.strip(), 'synthetic-film.png', True)), 201

    @api.route('/strips/<key>', methods=['GET', 'PATCH'])
    def strip(key):
        if request.method == 'PATCH':
            return jsonify(desk.configure(key, body()))
        return jsonify(desk.strip(key))

    @api.get('/strips/<key>/source.png')
    def source(key):
        return send_file(desk.source(key), mimetype='image/png', max_age=0)

    @api.get('/strips/<key>/guides')
    def guides(key):
        strip = desk.strip(key)
        config = strip['config']
        return jsonify(revision=strip['revision'], frames=layout.regular_frames(config),
                       profile=layout.inspect_columns(desk.pixels(key), config))

    @api.get('/strips/<key>/frames/<int:number>.png')
    def positive(key, number):
        strip = desk.strip(key)
        patch, _ = frames.view(desk.pixels(key), strip['config'], number)
        return png(patch)

    @api.get('/strips/<key>/frames/<int:number>')
    def quality(key, number):
        strip = desk.strip(key)
        patch, box = frames.view(desk.pixels(key), strip['config'], number)
        return jsonify(film_number=number, aperture=box, quality=frames.assess(patch))

    @api.get('/strips/<key>/pixel')
    def probe(key):
        strip = desk.strip(key)
        return jsonify(frames.probe(desk.pixels(key), strip['config'],
                                    request.args.get('x', type=int), request.args.get('y', type=int)))

    @api.get('/strips/<key>/contact.png')
    def contact(key):
        strip = desk.strip(key)
        config = strip['config']
        return png(frames.contact(desk.pixels(key), config, layout.regular_frames(config)))

    @api.route('/strips/<key>/runs', methods=['GET', 'POST'])
    def runs(key):
        if request.method == 'GET':
            return jsonify(desk.runs(key))
        return jsonify(desk.save(key, body().get('revision'))), 201

    @api.get('/strips/<key>/runs/<run_id>/package.zip')
    def download_run(key, run_id):
        run = desk.run(key, run_id)
        data = delivery.archive(desk.source(key).read_bytes(), desk.pixels(key), run)
        return send_file(BytesIO(data), mimetype='application/zip', max_age=0, as_attachment=True,
                         download_name=f"stripdesk-{run['strip_revision']}-{run_id[:8]}.zip")

    @api.post('/strips/<key>/frames/<int:number>/prepare')
    def transfer(key, number):
        strip = desk.strip(key)
        pixels, box = frames.view(desk.pixels(key), strip['config'], number)
        label = f"{strip['name']} · #{number:04}"
        metadata = {'strip_source_sha256': strip['source_sha256'], 'film_number': number, 'aperture': box}
        asset = app.extensions['assets'].put(pixels.astype('float32') / 255, label, metadata)
        draft = app.extensions['store'].create(label)
        project = app.extensions['frames'].add(draft['id'], draft['revision'], [asset['id']])['project']
        return jsonify(url=f"/prepare?project={project['id']}"), 201

    app.register_blueprint(api)
    return app
