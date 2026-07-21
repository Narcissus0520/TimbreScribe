"""Explicit gated-model installer process; never imports or executes model code."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import os
import shutil
import sys
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from timbrescribe import __version__
from timbrescribe.domain.errors import ErrorCode, TimbreScribeError
from timbrescribe.infrastructure.muscriptor import (
    JsonModelAcceptanceStore,
    MuscriptorModelManager,
    load_muscriptor_catalog,
    validate_muscriptor_config,
)
from timbrescribe.shared.protocol import (
    ErrorMessage,
    HelloMessage,
    ProgressMessage,
    ResultMessage,
    serialize_message,
)


def _emit(message: HelloMessage | ProgressMessage | ErrorMessage | ResultMessage) -> None:
    sys.stdout.write(f"{serialize_message(message)}\n")
    sys.stdout.flush()


def _install(job_id: str, variant: str, root: Path, acceptance_file: Path) -> Path:
    catalog = load_muscriptor_catalog()
    if variant not in {"small", "medium"}:
        raise TimbreScribeError(
            ErrorCode.MODEL_INCOMPATIBLE, "Only MuScriptor Small/Medium are supported"
        )
    manifest = catalog.model(variant)  # type: ignore[arg-type]
    if not JsonModelAcceptanceStore(acceptance_file).is_accepted(manifest):
        raise TimbreScribeError(
            ErrorCode.MODEL_LICENSE_NOT_ACCEPTED,
            "Current MuScriptor model terms have not been accepted",
            "Review the non-commercial terms and confirm source-media rights.",
        )
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise TimbreScribeError(
            ErrorCode.MODEL_MISSING,
            "No Hugging Face token is available to the installer",
            "Save a gated-model token in the operating-system credential store.",
        )
    try:
        hub = importlib.import_module("huggingface_hub")
        hf_hub_download = cast(Any, hub.hf_hub_download)
    except (ImportError, AttributeError) as exc:
        raise TimbreScribeError(
            ErrorCode.ENGINE_INCOMPATIBLE,
            "The optional MuScriptor installer runtime is missing",
            "Run tools/setup_muscriptor.ps1 without downloading weights.",
        ) from exc

    manager = MuscriptorModelManager(root, catalog)
    target = manager.model_directory(manifest)
    if target.exists():
        raise TimbreScribeError(
            ErrorCode.MODEL_INCOMPATIBLE,
            "The target model directory already exists",
            "Verify it or delete it through the model manager before reinstalling.",
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = root.resolve() / f".partial-{variant}-{uuid4().hex}"
    partial.mkdir(parents=True, exist_ok=False)
    try:
        _emit(ProgressMessage(job_id=job_id, stage="download-model", fraction=0.1))
        downloaded = Path(
            hf_hub_download(
                repo_id=manifest.source,
                filename=manifest.filename,
                revision=manifest.revision,
                token=token,
                local_dir=partial,
            )
        )
        if (
            downloaded.stat().st_size != manifest.size_bytes
            or _sha256_file(downloaded) != manifest.sha256
        ):
            raise TimbreScribeError(
                ErrorCode.MODEL_INCOMPATIBLE,
                "Downloaded MuScriptor model failed size/SHA-256 verification",
                "Delete the incomplete installation and retry.",
            )
        _emit(ProgressMessage(job_id=job_id, stage="download-config", fraction=0.9))
        config = Path(
            hf_hub_download(
                repo_id=manifest.source,
                filename="config.json",
                revision=manifest.revision,
                token=token,
                local_dir=partial,
            )
        )
        _validate_config(config, variant)
        cache = partial / ".cache"
        if cache.exists():
            shutil.rmtree(cache)
        partial.replace(target)
        _emit(ProgressMessage(job_id=job_id, stage="verified", fraction=1.0))
        return target / manifest.filename
    finally:
        if partial.exists():
            shutil.rmtree(partial)


def _validate_config(path: Path, variant: str) -> None:
    try:
        validate_muscriptor_config(path, variant)
    except ValueError as exc:
        raise TimbreScribeError(
            ErrorCode.MODEL_INCOMPATIBLE,
            str(exc),
            "Delete the incomplete installation and retry.",
        ) from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--variant", choices=("small", "medium"), required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--acceptance-file", type=Path, required=True)
    arguments = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="strict", newline="\n")
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    _emit(HelloMessage(worker="muscriptor-installer", version=__version__))
    try:
        result = _install(
            arguments.job_id,
            arguments.variant,
            arguments.root,
            arguments.acceptance_file,
        )
    except TimbreScribeError as exc:
        _emit(
            ErrorMessage(
                job_id=arguments.job_id,
                code=exc.code,
                message=exc.message,
                remediation=exc.remediation,
            )
        )
        return 1
    except Exception as exc:  # justified process boundary; token is never rendered
        _emit(
            ErrorMessage(
                job_id=arguments.job_id,
                code=ErrorCode.ENGINE_CRASHED,
                message=f"MuScriptor model installation failed: {type(exc).__name__}",
                remediation="Check network/gated access and retry; no model was activated.",
            )
        )
        return 1
    _emit(ResultMessage(job_id=arguments.job_id, result_path=str(result)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
