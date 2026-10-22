"""The pinned dataset: the Microcosm UK 2024-25 national release of 21 October 2026 (a858c100).

Loaded the way PolicyEngine/uk-energy-reforms loads it (``datasets.py``): a
fixed Hugging Face revision, its sha256 checked before use. The repository is
private, so a token is required (``HF_TOKEN`` or ``HUGGING_FACE_TOKEN``).
Setting ``HF_HUB_OFFLINE=1`` instead reads the file from the local Hugging
Face cache only; the sha256 check applies either way.

The release carries its own signed certification and its manifest pins
policyengine-uk 2.134.4 exactly. No policyengine.py release bundles that
version yet, so pyproject.toml pins policyengine-uk directly, and the
simulations pass the verified local file to ``managed_microsimulation`` with
``allow_unmanaged=True``: policyengine.py builds the simulation, and this
module, not the bundle, pins the data. Switch to the bundle's managed dataset
once a policyengine.py release registers this release.
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


# Release microcosm-uk-2024-25-national cut on 21 October 2026 (PolicyEngine/microcosm#1338,
# tracked in #1339): nested universal-under-working-parent take-up, reception children out
# of the take-up fit and DfE calibration rows, copies drawing their own take-up and hours,
# and ONS single-year-of-age and DfE registration targets. Pinned by the commit of its
# immutable cut tag, as recorded by the Hugging Face download (snapshot 415b034b...), and
# the sha256 posted with the release on uk-childcare-100k-threshold#8. Its manifest pins
# policyengine-uk 2.134.4 exactly: 2.102.3 silently drops stored inputs from this file.
# latest-national.json still points at 6cba5d71 while the release is in the inspect lane.
MICROCOSM = DatasetSpec(
    key="microcosm_uk_2024_25",
    label="Microcosm UK 2024-25 (national release, 21 October 2026)",
    repo_id="policyengine/populace-uk-private",
    repo_type="dataset",
    filename="microcosm_uk_2024_25.h5",
    revision="415b034b2a46ba536065c48754636e916ed096a1",
    sha256="e1f027b98a5127329643abc62e2de47b8fd67344b311ab1d9b86c7411908d190",
    release="microcosm-uk-2024-25-national-20261021T195620Z-a858c100",
    notes="Release cut 21 October 2026 (microcosm#1338), built and certified with policyengine-uk 2.134.4.",
)
# The engine the release manifest pins; engine.provenance refuses any other.
POLICYENGINE_UK_VERSION = "2.134.4"


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
