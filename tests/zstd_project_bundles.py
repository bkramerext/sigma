"""Offline v1/v2 compatibility, v3 Zstandard round-trip, and corruption checks."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from sigma.project_bundle import (
    BundleError,
    _decode,
    download_bytes,
    import_bundle,
    portable_bundle,
    read_bundle,
    read_file,
    stored_bundle,
    write_file,
)
from sigma.zstd_codec import MAX_MEMBER_BYTES, ZstdCodecError, compress, decompress

ENCODING = "$sigma_bundle_encoding"


def must_reject(payload: dict, directory: Path, name: str) -> None:
    target = directory / (name + ".json")
    try:
        import_bundle(payload, target)
    except BundleError:
        assert not target.exists()
    else:
        raise AssertionError(f"Accepted corrupt bundle: {name}")


def main() -> None:
    document = {"schema_version": 11, "id": "example"}
    members = {
        "project.json": (json.dumps(document) + "\n").encode(),
        "evidence/notes.json": b'{"notes":"' + b"x" * 40_000 + b'"}',
        "artifacts/papers/paper-a.tex": b"\\\\section{Proof}\n" + b"Text " * 20_000,
        "artifacts/papers/paper-a.pdf": b"%PDF-1.7\n" + os.urandom(100_000),
        "artifacts/papers/paper-a.json": b'{"paper_id":"paper-a"}\n',
        "evidence/raw.bin": bytes(range(256)),
    }
    stored = stored_bundle(members)
    assert stored["version"] == 3
    assert all(
        type(value) is dict
        and value[ENCODING] == "zstd+base64"
        and type(value["size"]) is int
        and value["size"] == len(members[name])
        for name, value in stored["files"].items()
    )
    assert _decode(stored) == members
    assert len(stored["files"]["evidence/notes.json"]["data"]) < 2500

    exported = portable_bundle(members)
    assert exported["version"] == 3
    assert exported["files"]["project.json"] == document
    assert (
        exported["files"]["artifacts/papers/paper-a.tex"]
        == members["artifacts/papers/paper-a.tex"].decode()
    )
    assert exported["files"]["artifacts/papers/paper-a.pdf"][ENCODING] == "zstd+base64"
    assert exported["files"]["evidence/raw.bin"][ENCODING] == "zstd+base64"
    assert (
        _decode(exported)["artifacts/papers/paper-a.pdf"] == members["artifacts/papers/paper-a.pdf"]
    )

    # Portable v3 may store damaged-but-readable JSON as a plain text
    # wrapper. That is not Base64 and must survive an exact byte round trip.
    text_members = {
        "project.json": members["project.json"],
        "evidence/unfinished.json": b"Unfinished draft, still valid UTF-8",
    }
    text_export = portable_bundle(text_members)
    assert text_export["files"]["evidence/unfinished.json"][ENCODING] == "text"
    assert _decode(text_export)["evidence/unfinished.json"] == text_members[
        "evidence/unfinished.json"
    ]
    old_json = {
        "format": "sigma.project.bundle",
        "version": 2,
        "files": {
            "project.json": document,
            "evidence/unusual.json": {ENCODING: "custom-field", "note": "ordinary JSON"},
        },
    }
    assert json.loads(_decode(old_json)["evidence/unusual.json"]) == {
        ENCODING: "custom-field",
        "note": "ordinary JSON",
    }

    with TemporaryDirectory() as directory:
        root = Path(directory)
        live = root / "new.json"
        assert import_bundle(exported, live) == live
        assert read_bundle(live)["version"] == 3
        for name, value in members.items():
            if name.endswith(".json"):
                assert json.loads(read_file(live, name)) == json.loads(value)
            else:
                assert read_file(live, name) == value
        reexport = json.loads(download_bytes(live))
        assert reexport["version"] == 3
        assert (
            _decode(reexport)["artifacts/papers/paper-a.tex"]
            == members["artifacts/papers/paper-a.tex"]
        )
        assert (
            _decode(reexport)["artifacts/papers/paper-a.pdf"]
            == members["artifacts/papers/paper-a.pdf"]
        )

        # Both pre-compression formats remain importable and writable.
        legacy_v1 = {
            "format": "sigma.project.bundle",
            "version": 1,
            "files": {name: base64.b64encode(value).decode() for name, value in members.items()},
        }
        legacy_v2 = {
            "format": "sigma.project.bundle",
            "version": 2,
            "files": {
                "project.json": document,
                "artifacts/papers/paper-a.tex": members["artifacts/papers/paper-a.tex"].decode(),
                "artifacts/papers/paper-a.pdf": {
                    ENCODING: "base64",
                    "data": base64.b64encode(members["artifacts/papers/paper-a.pdf"]).decode(),
                },
            },
        }
        for version, legacy in ((1, legacy_v1), (2, legacy_v2)):
            target = root / f"legacy-{version}.json"
            import_bundle(legacy, target)
            assert read_bundle(target)["version"] == 3
            assert (
                read_file(target, "artifacts/papers/paper-a.pdf")
                == members["artifacts/papers/paper-a.pdf"]
            )
            write_file(target, "evidence/new.bin", b"new research")
            assert read_file(target, "evidence/new.bin") == b"new research"
            assert read_bundle(target)["files"]["evidence/new.bin"][ENCODING] == "zstd+base64"

        # Existing persisted v1/v2 bundles can also be edited directly; the
        # first mutation upgrades storage atomically, preserving raw bytes.
        for version, legacy in ((1, legacy_v1), (2, legacy_v2)):
            target = root / f"old-on-disk-{version}.json"
            target.write_text(json.dumps(legacy))
            assert (
                read_file(target, "artifacts/papers/paper-a.pdf")
                == members["artifacts/papers/paper-a.pdf"]
            )
            write_file(target, "evidence/additional.bin", b"persisted")
            assert read_bundle(target)["version"] == 3
            assert read_file(target, "evidence/additional.bin") == b"persisted"

        # Corrupt/malformed lengths, frames, and legacy encodings must fail
        # before publishing a destination or allocating enormous buffers.
        pdf_value = stored["files"]["artifacts/papers/paper-a.pdf"]
        for label, altered in (
            ("wrong-size", {**pdf_value, "size": pdf_value["size"] + 1}),
            ("boolean-size", {**pdf_value, "size": True}),
            ("oversized", {**pdf_value, "size": MAX_MEMBER_BYTES + 1}),
            ("invalid-base64", {**pdf_value, "data": "!"}),
            (
                "truncated",
                {
                    **pdf_value,
                    "data": base64.b64encode(base64.b64decode(pdf_value["data"])[:-1]).decode(),
                },
            ),
            (
                "trailing-frame",
                {
                    **pdf_value,
                    "data": base64.b64encode(
                        base64.b64decode(pdf_value["data"]) + compress(b"extra")
                    ).decode(),
                },
            ),
            (
                "uncompressed-v3",
                {
                    ENCODING: "base64",
                    "data": base64.b64encode(members["artifacts/papers/paper-a.pdf"]).decode(),
                },
            ),
        ):
            corrupted = {
                **stored,
                "files": {
                    **stored["files"],
                    "artifacts/papers/paper-a.pdf": altered,
                },
            }
            must_reject(corrupted, root, label)

    for data in (b"", b"a" * 32_000, os.urandom(32_000), b"x\\x00y"):
        frame = compress(data)
        assert decompress(frame, len(data)) == data
    try:
        decompress(compress(b"x"), MAX_MEMBER_BYTES + 1)
    except ZstdCodecError:
        pass
    else:
        raise AssertionError("Oversized decompression claim accepted")
    print("PASS: v3 zstd/base64, legacy v1/v2 imports, exact papers, bounded frame integrity")


if __name__ == "__main__":
    main()
