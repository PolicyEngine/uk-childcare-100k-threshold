"""The pinned dataset: the certified Microcosm UK 2024-25 national release.

Loaded the way PolicyEngine/uk-energy-reforms loads it (``datasets.py``): a
fixed Hugging Face revision, its sha256 checked before use. The repository is
private, so a token is required (``HF_TOKEN`` or ``HUGGING_FACE_TOKEN``).
Setting ``HF_HUB_OFFLINE=1`` instead reads the file from the local Hugging
Face cache only; the sha256 check applies either way.

policyengine.py 6.2.1's release bundle does not register this release, so the
simulations pass the verified local file to ``managed_microsimulation`` with
``allow_unmanaged=True``: policyengine.py still runs the model (its bundle
pins policyengine-uk 2.102.3), and this module, not the bundle, certifies the
data. Switch to the bundle's managed dataset once a policyengine.py release
registers the certified release.
"""

import hashlib
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path


@dataclass(frozen=True)
class DatasetSpec:
    key: str
    label: str
    repo_id: str
    repo_type: str
    filename: str
    revision: str
    sha256: str
    release: str
    notes: str


# Release microcosm-uk-2024-25-national, published 4 October 2026: the commit of
# its immutable cut tag microcosm-uk-2024-25-national-20261002T230158Z-5c6b3f68
# (the same bytes as microcosm_uk_2024_25.h5 on main). Built with policyengine-uk 2.100.0.
MICROCOSM = DatasetSpec(
    key="microcosm_uk_2024_25",
    label="Microcosm UK 2024-25 (national release)",
    repo_id="policyengine/populace-uk-private",
    repo_type="dataset",
    filename="microcosm_uk_2024_25.h5",
    revision="f9d1922cddab6b54a0dd37794a9bac74e3780c88",
    sha256="aa31bdf67c977927ea2b325567d1cf7a79d94381239bc79918a0a0fc9c9588af",
    release="microcosm-uk-2024-25-national-20261002T230158Z-5c6b3f68",
    notes="Certified release, published 4 October 2026. Built with policyengine-uk 2.100.0.",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _offline() -> bool:
    return os.environ.get("HF_HUB_OFFLINE", "").lower() in {"1", "true", "yes"}


@cache
def dataset_path(spec: DatasetSpec = MICROCOSM) -> Path:
    """Download (or, offline, read from the cache) the pinned file and verify its sha256."""
    from huggingface_hub import hf_hub_download

    if _offline():
        path = hf_hub_download(
            repo_id=spec.repo_id,
            filename=spec.filename,
            revision=spec.revision,
            repo_type=spec.repo_type,
            local_files_only=True,
        )
    else:
        token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_TOKEN")
        if not token:
            raise RuntimeError(
                f"{spec.repo_id} is private: set HF_TOKEN or HUGGING_FACE_TOKEN "
                "(or HF_HUB_OFFLINE=1 to read the pinned revision from the local cache)."
            )
        path = hf_hub_download(
            repo_id=spec.repo_id,
            filename=spec.filename,
            revision=spec.revision,
            repo_type=spec.repo_type,
            token=token,
        )
    path = Path(path)
    actual = _sha256(path)
    if actual != spec.sha256:
        raise ValueError(f"{spec.key}: sha256 {actual} does not match the pinned {spec.sha256}")
    return path
