"""Four distinct recordings from CHAD camera 1, with built-in public access.

The publisher distributes an 87.97 GB ZIP. HTTP ranges retrieve only the named
MP4 members; the complete archive is never downloaded or extracted.
"""
from dataclasses import dataclass
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import struct
import time
import zlib

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE_ID = "13am4hfhicErcozAYgkmQm02_K-cCmtkQ"
ARCHIVE_URL = f"https://drive.usercontent.google.com/download?id={ARCHIVE_ID}&export=download"
ARCHIVE_PAGE = f"https://drive.google.com/file/d/{ARCHIVE_ID}/view"
SOURCE_PAGE = "https://github.com/TeCSAR-UNCC/CHAD"
ARCHIVE_BYTES = 87_967_801_766


@dataclass(frozen=True)
class Clip:
    id: str
    member: str
    size: int
    compressed_size: int
    offset: int
    crc32: int
    sha256: str = ""

    @property
    def title(self):
        return f"Video {self.id[-1]}  |  CHAD camera 1  |  {self.member}"


CLIPS = (
    Clip("chad-1", "1_029_0.mp4", 75938290, 75949894, 12078122037, 2444211748, "acb28b2908a7c075b4c57954bcdbc1df1be6786ce7f2788a8fc363a3ad7564a0"),
    Clip("chad-2", "1_038_0.mp4", 83008936, 83023888, 13793046476, 1965741059, "ccb6161e2cb46ea246de5f4caffa49d5db1c5ccbff6db3ffb29340dfea5a4ac2"),
    Clip("chad-3", "1_049_0.mp4", 50621254, 50625744, 17158920262, 340777217, "e919f6fb0878bdb62a241a9d55f414f71d133347ae38a18df053b198902d11b7"),
    Clip("chad-4", "1_054_0.mp4", 83249960, 83263662, 18063963469, 855700875, "35e7c508bbc77738143fed165bc2d920682d448872db25b84df2d41a667fa929"),
)


class DownloadError(RuntimeError):
    pass


class DownloadForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = ""
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "form":
            self.action = values.get("action", "")
        if tag == "input" and values.get("name"):
            self.fields[values["name"]] = values.get("value", "")


class ArchiveReader:
    def __init__(self):
        self.session = requests.Session()
        self.url = None
        self.params = None

    def resolve(self):
        with self.session.get(ARCHIVE_URL, timeout=(5, 15), stream=True) as response:
            response.raise_for_status()
            if "text/html" not in response.headers.get("Content-Type", ""):
                self.url, self.params = ARCHIVE_URL, None
                return
            chunks = []
            length = 0
            for chunk in response.iter_content(16384):
                length += len(chunk)
                if length > 100_000:
                    raise DownloadError("The publisher download page has changed.")
                chunks.append(chunk)
            form = DownloadForm()
            form.feed(b"".join(chunks).decode("utf-8", errors="replace"))
        if form.action != "https://drive.usercontent.google.com/download" or form.fields.get("id") != ARCHIVE_ID:
            raise DownloadError("Public video access is unavailable. See PROJECT_DOCUMENTATION.md#doc-video-sources.")
        self.url, self.params = form.action, form.fields

    def read(self, start, size):
        if size <= 0 or size > 8 * 1024 * 1024 or start < 0 or start + size > ARCHIVE_BYTES:
            raise DownloadError("Invalid archive range.")
        if self.url is None:
            try:
                self.resolve()
            except requests.RequestException:
                raise DownloadError("Cannot reach the public video archive. Check the connection and retry.") from None
        expected = f"bytes {start}-{start + size - 1}/{ARCHIVE_BYTES}"
        for attempt in range(2):
            try:
                begun = time.monotonic()
                with self.session.get(self.url, params=self.params,
                        headers={"Range": f"bytes={start}-{start + size - 1}"},
                        timeout=(5, 15), stream=True) as response:
                    # Abort before reading when a server ignores Range: this
                    # prevents accidental download of the entire 82 GiB ZIP.
                    if response.status_code != 206 or response.headers.get("Content-Range") != expected:
                        raise DownloadError("Server did not honor the small video range request.")
                    chunks, count = [], 0
                    for chunk in response.iter_content(65536):
                        count += len(chunk)
                        if count > size or time.monotonic() - begun > 60:
                            raise DownloadError("Video range exceeded its size or time limit.")
                        chunks.append(chunk)
                if count != size:
                    raise DownloadError("Incomplete video range.")
                return b"".join(chunks)
            except requests.RequestException:
                if attempt == 1:
                    raise DownloadError("Video download failed. Check the internet connection and retry.") from None
                time.sleep(.5)
        raise AssertionError("unreachable")

    def close(self):
        self.session.close()


def checksum(path):
    digest, crc = hashlib.sha256(), 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
            crc = zlib.crc32(block, crc)
    return digest.hexdigest(), crc


def fetch_clip(clip, progress=lambda message: None, cancelled=lambda: False, directory=None):
    directory = directory or PROJECT_ROOT / "data" / "chad"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / clip.member
    if target.exists() and target.stat().st_size == clip.size:
        digest, crc = checksum(target)
        if crc == clip.crc32 and (not clip.sha256 or digest == clip.sha256):
            progress(f"Using cached {clip.member}")
            return target
    archive = ArchiveReader()
    partial = target.with_suffix(".mp4.part")
    try:
        header = archive.read(clip.offset, 30)
        signature, version, flags, method, _, _, _, _, _, name_len, extra_len = struct.unpack("<I5H3I2H", header)
        if signature != 0x04034B50 or method != 8 or flags & 1 or name_len > 1024 or extra_len > 65535:
            raise DownloadError("Unexpected or encrypted archive member.")
        name = archive.read(clip.offset + 30, name_len).decode("utf-8")
        if name != clip.member:
            raise DownloadError("The archive changed; review the video catalog before retrying.")
        start = clip.offset + 30 + name_len + extra_len
        inflater = zlib.decompressobj(-15)
        written = 0
        with partial.open("wb") as handle:
            for offset in range(0, clip.compressed_size, 8 * 1024 * 1024):
                if cancelled():
                    raise DownloadError("Download stopped.")
                count = min(8 * 1024 * 1024, clip.compressed_size - offset)
                block = archive.read(start + offset, count)
                decoded = inflater.decompress(block, clip.size - written + 1)
                written += len(decoded)
                if written > clip.size or inflater.unconsumed_tail:
                    raise DownloadError("Unexpected expanded video size.")
                handle.write(decoded)
                progress(f"Downloading {clip.member}: {100 * (offset + count) / clip.compressed_size:.0f}%")
        if written != clip.size or not inflater.eof or inflater.unused_data:
            raise DownloadError("Incomplete video member.")
        digest, crc = checksum(partial)
        if crc != clip.crc32 or (clip.sha256 and digest != clip.sha256):
            raise DownloadError("Video checksum failed.")
        partial.replace(target)
        return target
    finally:
        archive.close()
        partial.unlink(missing_ok=True)
