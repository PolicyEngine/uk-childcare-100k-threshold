"""The pinned dataset: the Microcosm UK 2024-25 national release of 19 October 2026 (uncertified).

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
registers a certified release containing microcosm#1126.
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


# Release microcosm-uk-2024-25-national cut on 19 October 2026: the commit of its
# immutable cut tag microcosm-uk-2024-25-national-20261019T083323Z-6cba5d71, as
# recorded by the Hugging Face download (snapshot bb225848...); the release
# manifest gives the same sha256. Built with policyengine-uk 2.132.6. It is the
# first national release with PolicyEngine/microcosm#1126 (weekly extended hours
# drawn to DfE's 28.5-hour mean), and it is NOT certified: the latest certified
# release (14 October 2026) predates #1126.
MICROCOSM = DatasetSpec(
    key="microcosm_uk_2024_25",
    label="Microcosm UK 2024-25 (national release, uncertified)",
    repo_id="policyengine/populace-uk-private",
    repo_type="dataset",
    filename="microcosm_uk_2024_25.h5",
    revision="bb2258482ef8ce44f814a29288ee22bad2b636a0",
    sha256="810ba980005a8b907cb51464279fa5e0125464b7af9a4871b7f6744c30951ece",
    release="microcosm-uk-2024-25-national-20261019T083323Z-6cba5d71",
    notes="Uncertified release cut 19 October 2026, the first with microcosm#1126. Built with policyengine-uk 2.132.6.",
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
