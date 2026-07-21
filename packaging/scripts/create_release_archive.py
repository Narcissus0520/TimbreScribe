"""Create a deterministic ZIP from one staged onedir bundle."""

from __future__ import annotations

import argparse
import time
import zipfile
from pathlib import Path


def create_archive(bundle: Path, output: Path, source_date_epoch: int) -> Path:
    bundle = bundle.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    timestamp = time.gmtime(max(source_date_epoch, 315532800))[:6]
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    try:
        with zipfile.ZipFile(
            temporary,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for path in sorted(
                bundle.rglob("*"), key=lambda item: item.relative_to(bundle).as_posix()
            ):
                if not path.is_file():
                    continue
                relative = (Path(bundle.name) / path.relative_to(bundle)).as_posix()
                info = zipfile.ZipInfo(relative, timestamp)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o644 & 0xFFFF) << 16
                info.create_system = 3
                archive.writestr(info, path.read_bytes(), compresslevel=9)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return output


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-date-epoch", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    create_archive(arguments.bundle, arguments.output, arguments.source_date_epoch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
