"""Tests für ``app.utils.hashing``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.utils.hashing import (
    hash_bytes,
    hash_directory,
    hash_file,
    hash_iterable,
    hash_object,
    hash_text,
)


def test_hash_bytes_stable() -> None:
    assert hash_bytes(b"abc") == hash_bytes(b"abc")
    assert hash_bytes(b"abc") != hash_bytes(b"abd")


def test_hash_text_matches_bytes() -> None:
    assert hash_text("hello") == hash_bytes(b"hello")


def test_hash_object_order_independent() -> None:
    a = {"foo": 1, "bar": [1, 2, 3], "baz": {"x": "y", "z": True}}
    b = {"bar": [1, 2, 3], "baz": {"z": True, "x": "y"}, "foo": 1}
    assert hash_object(a) == hash_object(b)


def test_hash_object_detects_change() -> None:
    base = {"foo": 1, "bar": 2}
    changed = {"foo": 1, "bar": 3}
    assert hash_object(base) != hash_object(changed)


def test_hash_object_rejects_non_serialisable() -> None:
    class Opaque:
        pass

    with pytest.raises(TypeError):
        hash_object({"x": Opaque()})


def test_hash_object_handles_set_and_path(tmp_path: Path) -> None:
    payload = {"items": {3, 1, 2}, "where": tmp_path / "x.txt"}
    # Wirft nicht.
    digest = hash_object(payload)
    assert len(digest) == 64


def test_hash_file_matches_text(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_text("hallo welt", encoding="utf-8")
    assert hash_file(file_path) == hash_text("hallo welt")


def test_hash_file_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        hash_file(tmp_path / "ghost.txt")


def test_hash_file_rejects_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        hash_file(tmp_path)


def test_hash_directory_stable_order(tmp_path: Path) -> None:
    (tmp_path / "b.txt").write_text("two", encoding="utf-8")
    (tmp_path / "a.txt").write_text("one", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.txt").write_text("three", encoding="utf-8")
    first = hash_directory(tmp_path)
    # Schreibe weitere Datei in anderer Reihenfolge, dann lösche sie wieder.
    extra = tmp_path / "d.txt"
    extra.write_text("four", encoding="utf-8")
    differing = hash_directory(tmp_path)
    extra.unlink()
    second = hash_directory(tmp_path)
    assert first == second
    assert first != differing


def test_hash_directory_changes_on_rename(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("content", encoding="utf-8")
    digest_a = hash_directory(tmp_path)
    (tmp_path / "a.txt").rename(tmp_path / "b.txt")
    digest_b = hash_directory(tmp_path)
    assert digest_a != digest_b


def test_hash_directory_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        hash_directory(tmp_path / "ghost")


def test_hash_directory_rejects_file(tmp_path: Path) -> None:
    file_path = tmp_path / "a.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        hash_directory(file_path)


def test_hash_iterable_preserves_order() -> None:
    assert hash_iterable([1, 2, 3]) != hash_iterable([3, 2, 1])


def test_hash_object_uses_canonical_serialisation() -> None:
    # hash_object verwendet sort_keys + kompakte Separatoren. Wer den Wert
    # nachbauen will, muss dieselben Optionen wählen — der Test
    # dokumentiert das Vertragsformat.
    payload = {"foo": "bar", "n": 5, "list": [1, 2, 3]}
    expected_raw = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    assert hash_object(payload) == hash_text(expected_raw)
