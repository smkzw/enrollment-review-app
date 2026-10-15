import pytest

from app.evidence.artifacts import ArtifactStore, ArtifactStoreError, ArtifactIntegrityError
from scripts.run_isolated_page_revision import verify_page_inputs


def test_source_copy_requires_present_hash_verified_page_images(data_paths):
    store = ArtifactStore(data_paths)
    image = store.put("page_image", b"synthetic image")
    pages = [{"page_image_sha256": image.sha256}]
    assert verify_page_inputs(data_paths.root, pages) == 1
    with pytest.raises(ArtifactStoreError):
        verify_page_inputs(data_paths.root, [{"page_image_sha256": "a" * 64}])
    (data_paths.root / image.storage_ref).write_bytes(b"changed")
    with pytest.raises(ArtifactIntegrityError):
        verify_page_inputs(data_paths.root, pages)
