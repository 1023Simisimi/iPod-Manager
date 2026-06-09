"""
iPod Classic Manager — Flask backend
- Reads tags directly from audio files (no libgpod)
- Supports file upload + YouTube/audio URL download via yt-dlp
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_file
from mutagen import File as MutagenFile

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

SUPPORTED_INPUT_FORMATS = {'.mp3', '.m4a', '.aac', '.flac', '.wav', '.ogg', '.wma', '.aiff', '.opus'}
IPOD_NATIVE_FORMATS     = {'.mp3', '.m4a', '.aac', '.wav', '.aiff'}
AUDIO_EXTENSIONS        = {'.mp3', '.m4a', '.aac', '.wav', '.aiff', '.flac', '.ogg', '.wma'}


# ── iPod detection ─────────────────────────────────────────────────────────────

def find_ipod_mounts():
    candidates = []
    vol = Path('/Volumes')
    if vol.exists():
        for v in vol.iterdir():
            if (v / 'iPod_Control').exists():
                candidates.append(str(v))
    for p in ['/media/ipod', '/media/iPod', '/mnt/ipod']:
        if Path(p).exists() and (Path(p) / 'iPod_Control').exists():
            candidates.append(p)
    return list(set(candidates))


# ── Metadata ───────────────────────────────────────────────────────────────────

def get_metadata(filepath):
    meta = {'title':'','artist':'','album':'','genre':'','year':0,'tracknumber':0,'duration':0}
    try:
        audio = MutagenFile(str(filepath), easy=True)
        if audio:
            meta['title']  = str(audio.get('title',  [''])[0])
            meta['artist'] = str(audio.get('artist', [''])[0])
            meta['album']  = str(audio.get('album',  [''])[0])
            meta['genre']  = str(audio.get('genre',  [''])[0])
            try:    meta['year'] = int(str(audio.get('date',[0])[0])[:4])
            except: pass
            try:    meta['tracknumber'] = int(str(audio.get('tracknumber',['0'])[0]).split('/')[0])
            except: pass
            if hasattr(audio,'info') and audio.info:
                meta['duration'] = int(audio.info.length * 1000)
    except Exception:
        pass
    if not meta['title']:
        meta['title'] = Path(filepath).stem
    return meta


# ── Scan iPod filesystem ───────────────────────────────────────────────────────

def scan_ipod_tracks(mount):
    music_dir = Path(mount) / 'iPod_Control' / 'Music'
    if not music_dir.exists():
        raise FileNotFoundError(f'No Music folder at {music_dir}')
    tracks = []
    track_id = 1
    for folder in sorted(music_dir.iterdir()):
        if not folder.is_dir(): continue
        for f in sorted(folder.iterdir()):
            if f.suffix.lower() not in AUDIO_EXTENSIONS: continue
            meta = get_metadata(f)
            tracks.append({
                'id': track_id, 'title': meta['title'] or f.stem,
                'artist': meta['artist'] or 'Unknown Artist',
                'album':  meta['album']  or 'Unknown Album',
                'genre':  meta['genre'],  'year': meta['year'],
                'track_number': meta['tracknumber'], 'duration': meta['duration'],
                'size': f.stat().st_size, 'filetype': f.suffix.lstrip('.').upper(),
                'path': str(f),
            })
            track_id += 1
    tracks.sort(key=lambda t: (t['artist'].lower(), t['album'].lower(), t['track_number']))
    for i, t in enumerate(tracks, 1):
        t['id'] = i
    return tracks


# ── Copy file onto iPod ────────────────────────────────────────────────────────

def copy_to_ipod(src_path, mount):
    """Copy a file into iPod_Control/Music/Fxx/, avoiding name collisions.
    Returns the destination Path."""
    src = Path(src_path)
    music_dir = Path(mount) / 'iPod_Control' / 'Music'
    music_dir.mkdir(parents=True, exist_ok=True)

    folder_num = abs(hash(src.name)) % 50
    dest_folder = music_dir / f'F{folder_num:02d}'
    dest_folder.mkdir(exist_ok=True)

    dest_path = dest_folder / src.name
    counter = 1
    while dest_path.exists():
        dest_path = dest_folder / f'{src.stem}_{counter}{src.suffix}'
        counter += 1

    # src and dest are guaranteed different now
    shutil.copy2(str(src), str(dest_path))
    return dest_path


# ── Format conversion ──────────────────────────────────────────────────────────

def convert_to_ipod_format(src, out_dir):
    """Convert non-native formats to AAC/m4a. Returns (path, was_converted)."""
    ext = Path(src).suffix.lower()
    if ext in IPOD_NATIVE_FORMATS:
        # Don't copy — just return the original path
        return str(src), False
    out = Path(out_dir) / (Path(src).stem + '.m4a')
    r = subprocess.run(
        ['ffmpeg', '-y', '-i', str(src), '-c:a', 'aac', '-b:a', '192k',
         '-movflags', '+faststart', str(out)],
        capture_output=True, text=True)
    if r.returncode != 0:
        return None, f'FFmpeg error: {r.stderr[-400:]}'
    return str(out), True


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/detect')
def detect():
    mounts = find_ipod_mounts()
    results = []
    for m in mounts:
        try:
            tracks = scan_ipod_tracks(m)
            results.append({'mount': m, 'name': Path(m).name,
                            'track_count': len(tracks), 'error': None})
        except Exception as e:
            results.append({'mount': m, 'name': Path(m).name,
                            'track_count': 0, 'error': str(e)})
    return jsonify({'ipods': results})


@app.route('/api/set-mount', methods=['POST'])
def set_mount():
    mount = request.json.get('mount', '').strip()
    if not mount: return jsonify({'error': 'No mount point'}), 400
    p = Path(mount)
    if not p.exists(): return jsonify({'error': f'Path does not exist: {mount}'}), 400
    if not (p / 'iPod_Control').exists(): return jsonify({'error': 'No iPod_Control folder found'}), 400
    try:
        tracks = scan_ipod_tracks(mount)
        return jsonify({'success': True, 'mount': mount, 'track_count': len(tracks)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/library')
def library():
    mount = request.args.get('mount')
    if not mount: return jsonify({'error': 'No mount'}), 400
    try:
        tracks = scan_ipod_tracks(mount)
        return jsonify({'tracks': tracks, 'total': len(tracks)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stream')
def stream():
    path = request.args.get('path')
    if not path or not Path(path).exists():
        return jsonify({'error': 'File not found'}), 404
    mime_map = {'.mp3':'audio/mpeg','.m4a':'audio/mp4','.aac':'audio/aac',
                '.wav':'audio/wav','.aiff':'audio/aiff','.flac':'audio/flac','.ogg':'audio/ogg'}
    mime = mime_map.get(Path(path).suffix.lower(), 'audio/mpeg')
    return send_file(path, mimetype=mime, conditional=True)


@app.route('/api/delete', methods=['POST'])
def delete():
    path = request.json.get('path')
    if not path or not Path(path).exists():
        return jsonify({'error': 'File not found'}), 404
    try:
        Path(path).unlink()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/probe', methods=['POST'])
def probe():
    if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
    f = request.files['file']
    ext = Path(f.filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        f.save(tmp.name)
        meta = get_metadata(tmp.name)
        os.unlink(tmp.name)
    return jsonify({**meta, 'filename': f.filename, 'format': ext,
                    'needs_conversion': ext not in IPOD_NATIVE_FORMATS})


@app.route('/api/add-track', methods=['POST'])
def add_track():
    mount = request.form.get('mount')
    if not mount: return jsonify({'error': 'No mount'}), 400
    if 'file' not in request.files: return jsonify({'error': 'No file'}), 400

    f   = request.files['file']
    ext = Path(f.filename).suffix.lower()
    if ext not in SUPPORTED_INPUT_FORMATS:
        return jsonify({'error': f'Unsupported format: {ext}'}), 400

    with tempfile.TemporaryDirectory() as tmp:
        upload = Path(tmp) / f.filename
        f.save(str(upload))

        converted, was_converted = convert_to_ipod_format(str(upload), tmp)
        if converted is None:
            return jsonify({'error': was_converted}), 500

        meta = get_metadata(converted)
        meta['title']  = request.form.get('title',  meta['title'])  or meta['title']
        meta['artist'] = request.form.get('artist', meta['artist']) or meta['artist']
        meta['album']  = request.form.get('album',  meta['album'])  or meta['album']

        try:
            dest = copy_to_ipod(converted, mount)
            return jsonify({'success': True, 'converted': was_converted,
                            'track': {'title': meta['title'], 'artist': meta['artist'],
                                      'album': meta['album']}})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


@app.route('/api/add-from-url', methods=['POST'])
def add_from_url():
    """Download audio from a YouTube (or any yt-dlp supported) URL and add to iPod."""
    mount = request.json.get('mount')
    url   = request.json.get('url', '').strip()
    if not mount: return jsonify({'error': 'No mount'}), 400
    if not url:   return jsonify({'error': 'No URL provided'}), 400

    with tempfile.TemporaryDirectory() as tmp:
        # Download best audio as mp3 via yt-dlp
        out_template = str(Path(tmp) / '%(title)s.%(ext)s')
        r = subprocess.run([
            'python3', '-m', 'yt_dlp',
            '--extract-audio',
            '--audio-format', 'mp3',
            '--audio-quality', '0',
            '--output', out_template,
            '--no-playlist',
            '--extractor-args', 'youtube:player_client=tv_embedded',
            url
        ], capture_output=True, text=True)

        if r.returncode != 0:
            err = r.stderr[-600:] or r.stdout[-600:]
            return jsonify({'error': f'Download failed: {err}'}), 500

        # Find the downloaded file
        mp3_files = list(Path(tmp).glob('*.mp3'))
        if not mp3_files:
            # Try any audio file
            all_audio = [f for f in Path(tmp).iterdir()
                         if f.suffix.lower() in AUDIO_EXTENSIONS]
            if not all_audio:
                return jsonify({'error': 'No audio file found after download'}), 500
            downloaded = all_audio[0]
        else:
            downloaded = mp3_files[0]

        meta = get_metadata(downloaded)

        try:
            dest = copy_to_ipod(str(downloaded), mount)
            return jsonify({
                'success': True,
                'track': {
                    'title':  meta['title']  or downloaded.stem,
                    'artist': meta['artist'] or 'Unknown Artist',
                    'album':  meta['album']  or 'Unknown Album',
                }
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print('\n🎵  iPod Manager running at http://localhost:5050\n')
    app.run(debug=True, port=5050)
