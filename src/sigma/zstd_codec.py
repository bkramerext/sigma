"""Bounded, fast Zstandard compression for portable and stored project members.

Uses the libzstd shared library installed by `./sigma setup` (and in the
production image). We avoid starting a compression subprocess for every member
on each atomic project update, especially during research sessions.
"""

from __future__ import annotations

import ctypes
import ctypes.util
from functools import lru_cache

MAX_MEMBER_BYTES = 256 * 1024 * 1024
MAX_BUNDLE_BYTES = 1024 * 1024 * 1024


class ZstdCodecError(ValueError):
    """Unavailable or malformed Zstandard data."""


@lru_cache(maxsize=1)
def _library() -> ctypes.CDLL:
    candidates = (
        ctypes.util.find_library("zstd"),
        "libzstd.so.1",
        "libzstd.dylib",
        "/opt/homebrew/opt/zstd/lib/libzstd.dylib",
        "/usr/local/opt/zstd/lib/libzstd.dylib",
    )
    library = None
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            library = ctypes.CDLL(candidate)
            break
        except OSError:
            continue
    if library is None:
        raise ZstdCodecError("Zstandard is unavailable; run ./sigma setup to install zstd")
    size = ctypes.c_size_t
    pointer = ctypes.c_void_p
    library.ZSTD_compressBound.argtypes = [size]
    library.ZSTD_compressBound.restype = size
    library.ZSTD_compress.argtypes = [pointer, size, pointer, size, ctypes.c_int]
    library.ZSTD_compress.restype = size
    library.ZSTD_decompress.argtypes = [pointer, size, pointer, size]
    library.ZSTD_decompress.restype = size
    library.ZSTD_findFrameCompressedSize.argtypes = [pointer, size]
    library.ZSTD_findFrameCompressedSize.restype = size
    library.ZSTD_isError.argtypes = [size]
    library.ZSTD_isError.restype = ctypes.c_uint
    return library


def _valid_size(size: int) -> bool:
    return type(size) is int and 0 <= size <= MAX_MEMBER_BYTES


def compress(data: bytes) -> bytes:
    """Compress one member in a single self-contained Zstandard frame."""
    if not isinstance(data, bytes) or not _valid_size(len(data)):
        raise ZstdCodecError("Project bundle member exceeds the allowed size")
    library = _library()
    buffer = ctypes.create_string_buffer(library.ZSTD_compressBound(len(data)))
    written = library.ZSTD_compress(buffer, len(buffer), data, len(data), 3)
    if library.ZSTD_isError(written):
        raise ZstdCodecError("Zstandard compression failed")
    return buffer.raw[:written]


def decompress(frame: bytes, expected_size: int) -> bytes:
    """Decode one frame with a fixed allocation, rejecting extra frames/trailers."""
    if not isinstance(frame, bytes) or not _valid_size(expected_size):
        raise ZstdCodecError("Invalid uncompressed project member size")
    if len(frame) > MAX_MEMBER_BYTES:
        raise ZstdCodecError("Compressed project member exceeds the allowed size")
    library = _library()
    frame_size = library.ZSTD_findFrameCompressedSize(frame, len(frame))
    if library.ZSTD_isError(frame_size) or frame_size != len(frame):
        raise ZstdCodecError("Invalid or trailing Zstandard project member data")
    output = ctypes.create_string_buffer(expected_size)
    written = library.ZSTD_decompress(output, expected_size, frame, len(frame))
    if library.ZSTD_isError(written) or written != expected_size:
        raise ZstdCodecError("Invalid Zstandard project member or length")
    return output.raw[:written]
