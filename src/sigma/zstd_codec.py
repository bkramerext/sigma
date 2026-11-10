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
# Incompressible Zstandard frames can be slightly larger than raw input.
MAX_COMPRESSED_MEMBER_BYTES = MAX_MEMBER_BYTES + (MAX_MEMBER_BYTES >> 8) + 65536
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
    if len(frame) > MAX_COMPRESSED_MEMBER_BYTES:
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


def compress_archive(data: bytes, frame_bytes: int = MAX_MEMBER_BYTES) -> bytes:
    """Compress a bounded archive as consecutive complete Zstandard frames.

    Individual runtime members retain the strict 256 MiB limit. A v4 TAR
    archive may contain several such members and therefore needs more than
    one frame. Concatenated Zstandard frames remain one valid zstd stream.
    """
    if (
        not isinstance(data, bytes)
        or len(data) > MAX_BUNDLE_BYTES
        or type(frame_bytes) is not int
        or not 1 <= frame_bytes <= MAX_MEMBER_BYTES
    ):
        raise ZstdCodecError("Invalid or oversized project artifact archive")
    if not data:
        return compress(b"")
    return b"".join(
        compress(data[offset : offset + frame_bytes]) for offset in range(0, len(data), frame_bytes)
    )


def decompress_archive(
    encoded: bytes, expected_size: int, frame_bytes: int = MAX_MEMBER_BYTES
) -> bytes:
    """Decode a bounded sequence of frames without accepting trailing data.

    The exact chunk sizes are deterministic from the declared total length.
    Each frame is decoded through the existing bounded single-frame decoder,
    so malformed frames, overlong chunks and injected suffixes fail closed.
    """
    if (
        not isinstance(encoded, bytes)
        or type(expected_size) is not int
        or not 0 <= expected_size <= MAX_BUNDLE_BYTES
        or type(frame_bytes) is not int
        or not 1 <= frame_bytes <= MAX_MEMBER_BYTES
    ):
        raise ZstdCodecError("Invalid project artifact archive size")
    frames = max(1, (expected_size + frame_bytes - 1) // frame_bytes)
    if not encoded or len(encoded) > frames * MAX_COMPRESSED_MEMBER_BYTES:
        raise ZstdCodecError("Compressed artifact archive exceeds the allowed size")
    library = _library()
    chunks: list[bytes] = []
    offset = 0
    decoded_size = 0
    for _ in range(frames):
        remaining = encoded[offset:]
        frame_size = library.ZSTD_findFrameCompressedSize(remaining, len(remaining))
        if library.ZSTD_isError(frame_size) or not 0 < frame_size <= len(remaining):
            raise ZstdCodecError("Invalid compressed archive frame")
        length = min(frame_bytes, expected_size - decoded_size)
        decoded = decompress(encoded[offset : offset + frame_size], length)
        chunks.append(decoded)
        decoded_size += len(decoded)
        offset += frame_size
    if offset != len(encoded) or decoded_size != expected_size:
        raise ZstdCodecError("Unexpected trailing or missing artifact archive frames")
    return b"".join(chunks)
