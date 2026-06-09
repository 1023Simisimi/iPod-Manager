"""
Pure-Python iTunesDB parser/writer for iPod nano (4th gen) and similar.
Handles the mhbd/mhsd/mhlt/mhit record structure.
Reference: http://www.ipodlinux.org/ITunesDB/
"""

import struct
import os
import shutil
from pathlib import Path


def _read4(data, off):
    return struct.unpack_from('<I', data, off)[0]

def _read2(data, off):
    return struct.unpack_from('<H', data, off)[0]

def _readstr(data, off, length):
    raw = data[off:off+length]
    try:
        return raw.decode('utf-16-le').rstrip('\x00')
    except Exception:
        return raw.decode('latin-1', errors='replace').rstrip('\x00')

def _encode_mhod_string(s):
    """Encode a string as an mhod type-1 record."""
    encoded = (s or '').encode('utf-16-le')
    header_size = 0x28
    total = header_size + len(encoded)
    out = bytearray(total)
    out[0:4]   = b'mhod'
    struct.pack_into('<I', out, 4,  header_size)
    struct.pack_into('<I', out, 8,  total)
    struct.pack_into('<I', out, 12, 1)   # type = string
    struct.pack_into('<I', out, 24, 1)   # UTF-16-LE
    struct.pack_into('<I', out, 28, len(encoded))
    struct.pack_into('<I', out, 32, 0)
    out[header_size:] = encoded
    return bytes(out)


class Track:
    def __init__(self):
        self.id = 0
        self.title = ''
        self.artist = ''
        self.album = ''
        self.genre = ''
        self.year = 0
        self.track_number = 0
        self.duration = 0      # ms
        self.size = 0
        self.filetype = ''
        self.ipod_path = ''    # e.g. :iPod_Control:Music:F00:song.mp3


class ITunesDB:
    def __init__(self, mount_point):
        self.mount = Path(mount_point)
        self.db_path = self.mount / 'iPod_Control' / 'iTunes' / 'iTunesDB'
        self.tracks = []
        self._raw = None
        self._parse()

    def _parse(self):
        if not self.db_path.exists():
            raise FileNotFoundError(f'iTunesDB not found at {self.db_path}')

        with open(self.db_path, 'rb') as f:
            self._raw = bytearray(f.read())

        data = self._raw
        if data[0:4] != b'mhbd':
            raise ValueError('Not a valid iTunesDB file')

        self.tracks = []
        self._scan_mhit(data)

    def _scan_mhit(self, data):
        """Walk the binary blob and extract all mhit (track) records."""
        pos = 0
        track_id = 1
        while pos < len(data) - 4:
            if data[pos:pos+4] == b'mhit':
                t = self._parse_mhit(data, pos)
                t.id = track_id
                track_id += 1
                self.tracks.append(t)
                header_len = _read4(data, pos+4)
                total_len  = _read4(data, pos+8)
                pos += max(total_len, header_len, 4)
            else:
                pos += 1

    def _parse_mhit(self, data, base):
        t = Track()
        header_len = _read4(data, base + 4)
        total_len  = _read4(data, base + 8)
        num_mhod   = _read4(data, base + 12)

        # Fixed fields in mhit header
        try:
            t.size     = _read4(data, base + 36)
            t.duration = _read4(data, base + 40)   # ms
            t.year     = _read4(data, base + 48) if header_len > 48 else 0
            t.track_number = _read4(data, base + 44) if header_len > 44 else 0
        except Exception:
            pass

        # Walk mhod children for strings
        pos = base + header_len
        end = base + total_len
        for _ in range(num_mhod):
            if pos + 12 > len(data):
                break
            if data[pos:pos+4] != b'mhod':
                break
            mhod_header = _read4(data, pos + 4)
            mhod_total  = _read4(data, pos + 8)
            mhod_type   = _read4(data, pos + 12)
            str_len     = _read4(data, pos + 28) if mhod_header >= 32 else 0
            str_off     = pos + mhod_header

            if mhod_type in (1, 2, 3, 4, 5, 6) and str_len > 0:
                s = _readstr(data, str_off, str_len)
                if   mhod_type == 1: t.title  = s
                elif mhod_type == 2: t.artist = s
                elif mhod_type == 3: t.album  = s
                elif mhod_type == 4: t.genre  = s
                elif mhod_type == 5: t.filetype = s
                elif mhod_type == 6: t.ipod_path = s

            pos += max(mhod_total, mhod_header, 1)
            if pos >= end:
                break

        return t

    def add_track(self, src_path, title='', artist='', album='', genre='',
                  year=0, track_number=0):
        """
        Copy a file onto the iPod and register it in the iTunesDB.
        Returns the new Track object.
        """
        src = Path(src_path)
        ext = src.suffix.lower()

        # Pick a music folder (F00–F49)
        music_dir = self.mount / 'iPod_Control' / 'Music'
        music_dir.mkdir(parents=True, exist_ok=True)

        # Use folder based on hash of filename
        folder_num = hash(src.name) % 50
        dest_folder = music_dir / f'F{folder_num:02d}'
        dest_folder.mkdir(exist_ok=True)

        # Avoid name collisions
        dest_name = src.name
        dest_path = dest_folder / dest_name
        counter = 1
        while dest_path.exists():
            dest_path = dest_folder / f'{src.stem}_{counter}{ext}'
            counter += 1

        shutil.copy2(src, dest_path)

        # iPod path uses colons and starts from root
        rel = dest_path.relative_to(self.mount)
        ipod_path = ':' + ':'.join(rel.parts)

        # Build track object
        t = Track()
        t.id = len(self.tracks) + 1
        t.title  = title  or src.stem
        t.artist = artist or ''
        t.album  = album  or ''
        t.genre  = genre  or ''
        t.year   = year
        t.track_number = track_number
        t.size   = dest_path.stat().st_size
        t.filetype = ext.lstrip('.').upper()
        t.ipod_path = ipod_path
        t.duration = 0  # will be filled by mutagen below

        # Get duration via mutagen
        try:
            from mutagen import File as MF
            audio = MF(str(dest_path))
            if audio and audio.info:
                t.duration = int(audio.info.length * 1000)
        except Exception:
            pass

        self.tracks.append(t)
        self._write_db()
        return t

    def remove_track(self, track_id):
        """Remove a track by id, delete the file, rewrite DB."""
        track = next((t for t in self.tracks if t.id == track_id), None)
        if not track:
            raise ValueError(f'Track {track_id} not found')

        # Delete the actual file
        if track.ipod_path:
            rel = track.ipod_path.lstrip(':').replace(':', os.sep)
            full = self.mount / rel
            if full.exists():
                full.unlink()

        self.tracks = [t for t in self.tracks if t.id != track_id]
        self._write_db()

    def _write_db(self):
        """Rebuild the iTunesDB from scratch using current self.tracks."""
        # Back up original
        backup = self.db_path.with_suffix('.bak')
        if self.db_path.exists() and not backup.exists():
            shutil.copy2(self.db_path, backup)

        db = self._build_db()
        tmp = self.db_path.with_suffix('.tmp')
        with open(tmp, 'wb') as f:
            f.write(db)
        tmp.replace(self.db_path)

    def _build_db(self):
        """Build a minimal but valid iTunesDB binary."""
        # Build mhlt (track list) containing all mhit records
        mhit_blobs = [self._build_mhit(t) for t in self.tracks]
        mhlt_children = b''.join(mhit_blobs)
        mhlt = self._mhlt(len(self.tracks), mhlt_children)

        # mhsd type 1 = track list
        mhsd1 = self._mhsd(1, mhlt)

        # mhsd type 3 = playlist list (minimal: just "All tracks")
        mhsd3 = self._mhsd(3, self._mhlp_all(self.tracks))

        body = mhsd1 + mhsd3
        mhbd = self._mhbd(2, body)
        return mhbd

    def _mhbd(self, num_children, body):
        size = 0x68
        total = size + len(body)
        h = bytearray(size)
        h[0:4] = b'mhbd'
        struct.pack_into('<I', h, 4,  size)
        struct.pack_into('<I', h, 8,  total)
        struct.pack_into('<I', h, 12, num_children)
        struct.pack_into('<I', h, 16, 1)       # version
        struct.pack_into('<I', h, 20, len(self.tracks))
        return bytes(h) + body

    def _mhsd(self, type_, body):
        size = 0x60
        total = size + len(body)
        h = bytearray(size)
        h[0:4] = b'mhsd'
        struct.pack_into('<I', h, 4,  size)
        struct.pack_into('<I', h, 8,  total)
        struct.pack_into('<I', h, 12, type_)
        return bytes(h) + body

    def _mhlt(self, num_tracks, body):
        size = 0x5c
        total = size + len(body)
        h = bytearray(size)
        h[0:4] = b'mhlt'
        struct.pack_into('<I', h, 4,  size)
        struct.pack_into('<I', h, 8,  total)
        struct.pack_into('<I', h, 12, num_tracks)
        return bytes(h) + body

    def _build_mhit(self, t):
        strings = []
        for type_, val in [(1, t.title), (2, t.artist), (3, t.album),
                           (4, t.genre), (5, t.filetype), (6, t.ipod_path)]:
            if val:
                mhod = _encode_mhod_string(val)
                # patch type
                struct.pack_into('<I', bytearray(mhod), 12, type_)
                strings.append(mhod)

        children = b''.join(strings)
        size = 0x148
        total = size + len(children)
        h = bytearray(size)
        h[0:4] = b'mhit'
        struct.pack_into('<I', h, 4,  size)
        struct.pack_into('<I', h, 8,  total)
        struct.pack_into('<I', h, 12, len(strings))
        struct.pack_into('<I', h, 16, t.id)
        struct.pack_into('<I', h, 36, t.size)
        struct.pack_into('<I', h, 40, t.duration)
        struct.pack_into('<I', h, 44, t.track_number)
        struct.pack_into('<I', h, 48, t.year)
        return bytes(h) + children

    def _mhlp_all(self, tracks):
        """Build a minimal playlist list with one 'All tracks' playlist."""
        # mhip for each track
        mhips = b''
        for t in tracks:
            mhip = bytearray(0x4c)
            mhip[0:4] = b'mhip'
            struct.pack_into('<I', mhip, 4, 0x4c)
            struct.pack_into('<I', mhip, 8, 0x4c)
            struct.pack_into('<I', mhip, 12, 0)
            struct.pack_into('<I', mhip, 24, t.id)
            mhips += bytes(mhip)

        name_mhod = _encode_mhod_string('All tracks')
        # patch type to 1
        tmp = bytearray(name_mhod)
        struct.pack_into('<I', tmp, 12, 1)
        name_mhod = bytes(tmp)

        # mhyp (playlist)
        mhyp_hdr_size = 0x6c
        mhyp_total = mhyp_hdr_size + len(name_mhod) + len(mhips)
        mhyp = bytearray(mhyp_hdr_size)
        mhyp[0:4] = b'mhyp'
        struct.pack_into('<I', mhyp, 4,  mhyp_hdr_size)
        struct.pack_into('<I', mhyp, 8,  mhyp_total)
        struct.pack_into('<I', mhyp, 12, 1 + len(tracks))  # 1 mhod + N mhip
        struct.pack_into('<I', mhyp, 16, len(tracks))
        struct.pack_into('<I', mhyp, 20, 1)  # master playlist flag

        mhyp_blob = bytes(mhyp) + name_mhod + mhips

        # mhlp wrapper
        mhlp_size = 0x5c
        mhlp_total = mhlp_size + len(mhyp_blob)
        mhlp = bytearray(mhlp_size)
        mhlp[0:4] = b'mhlp'
        struct.pack_into('<I', mhlp, 4,  mhlp_size)
        struct.pack_into('<I', mhlp, 8,  mhlp_total)
        struct.pack_into('<I', mhlp, 12, 1)  # 1 playlist
        return bytes(mhlp) + mhyp_blob
