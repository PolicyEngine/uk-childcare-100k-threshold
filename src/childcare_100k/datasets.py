"""The pinned dataset: the Microcosm UK 2024-25 national release of 23 October 2026 (a133f37a).

Loaded the way PolicyEngine/uk-energy-reforms loads it (``datasets.py``): a
fixed Hugging Face revision, its sha256 checked before use. The repository is
private, so a token is required: ``HF_TOKEN`` or ``HUGGING_FACE_TOKEN``, or
the one saved by ``hf auth login``.
Setting ``HF_HUB_OFFLINE=1`` instead reads the file from the local Hugging
Face cache only; the sha256 check applies either way.

The release carries its own signed certification and its manifest pins
policyengine-uk 2.147.2 and policyengine-core 3.33.3 exactly. No
policyengine.py release bundles that model version yet, so pyproject.toml pins
both directly, and the simulations pass the verified local file to
``managed_microsimulation`` with ``allow_unmanaged=True``: policyengine.py
builds the simulation, and this module, not the bundle, pins the data. Switch
to the bundle's managed dataset once a policyengine.py release registers this
release.
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


# Release microcosm-uk-2024-25-national cut on 23 October 2026 from PolicyEngine/microcosm
# 829c1bc26, a head of #1338 (tracked in #1339; #1338 merged later that day at a12885f9):
# childcare take-up and the DfE funded-childcare rows measured at the spring term, a
# working-parent take-up rate for each age under 2, and the 9-11-months row bound. It does not
# carry #1338's later round-3 fix to key the under-2 draw on DfE age, nor #1344 or #1347. Pinned
# by the commit of its immutable cut tag (c3a751d9...); the dataset repository's main carried the
# same file (sha256 below) when this was pinned and again on 24 October 2026 (d9be8162...). The
# sha256 is the one in the release manifest, build manifest and certification. Its manifest pins
# policyengine-uk 2.147.2, which carries policyengine-uk#2570 (reception and the working-parent
# start from the term after 9 months, from the date of birth).
# latest-national.json has pointed at this release since 23 October 2026 (11:23 UTC): it is the
# latest national release. policyengine.py 6.10.2's bundle still registers 6cba5d71.
MICROCOSM = DatasetSpec(
    key="microcosm_uk_2024_25",
    label="Microcosm UK 2024-25 (national release, 23 October 2026)",
    repo_id="policyengine/populace-uk-private",
    repo_type="dataset",
    filename="microcosm_uk_2024_25.h5",
    revision="c3a751d911ac82e482d298dda0b6f2c949f4ed4d",
    sha256="64f83900ca3a1242fb017585234844ce89f743d32e41cd2b6558057777f914aa",
    release="microcosm-uk-2024-25-national-20261023T075039Z-a133f37a",
    notes="Release cut 23 October 2026 from microcosm 829c1bc26 (#1338), built and certified with policyengine-uk 2.147.2.",
)
# The engine the release manifest pins; engine.provenance refuses any other.
POLICYENGINE_UK_VERSION = "2.147.2"


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
    from huggingface_hub import get_token, hf_hub_download

    if _offline():
        path = hf_hub_download(
            repo_id=spec.repo_id,
            filename=spec.filename,
            revision=spec.revision,
            repo_type=spec.repo_type,
            local_files_only=True,
        )
    else:
        token = (
            os.environ.get("HF_TOKEN")
            or os.environ.get("HUGGING_FACE_TOKEN")
            or get_token()
        )
        if not token:
            raise RuntimeError(
                f"{spec.repo_id} is private: set HF_TOKEN or HUGGING_FACE_TOKEN, or run `hf auth login` "
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
        raise ValueError(
            f"{spec.key}: sha256 {actual} does not match the pinned {spec.sha256}"
        )
    return path
