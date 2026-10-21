"""Check the demo environment and configured paths without running an analysis."""
import argparse
import importlib
from pathlib import Path
import sys
from tempfile import TemporaryFile


def check_dependencies(requirements_path):
    results = []
    for package in requirements_path.read_text(encoding="utf-8").splitlines():
        package = package.strip()
        if not package or package.startswith("#"):
            continue
        module = {"scikit-image": "skimage"}.get(package, package)
        try:
            importlib.import_module(module)
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            results.append(("FAIL", f"{package}: {type(exc).__name__}: {exc}"))
        else:
            results.append(("OK", f"{package}: import successful"))
    return results


def check_file(name, path):
    if path is None:
        return "FAIL", f"{name}: no path configured in EA_setup.py"
    path = Path(path)
    try:
        with path.open("rb") as source:
            source.read(1)
    except OSError as exc:
        return "FAIL", f"{name}: {path} ({exc})"
    return "OK", f"{name}: {path}"


def check_output(name, path):
    if path is None:
        return "FAIL", f"{name}: no path configured in EA_setup.py"
    path = Path(path)
    ancestor = path
    try:
        while not ancestor.exists() and ancestor != ancestor.parent:
            ancestor = ancestor.parent
        if not ancestor.is_dir():
            return "FAIL", f"{name}: {ancestor} is not a directory"
        with TemporaryFile(dir=ancestor) as probe:
            probe.write(b"write test")
            probe.flush()
    except OSError as exc:
        return "FAIL", f"{name}: cannot write to {path} ({exc})"
    return "OK", f"{name}: {path} (writable parent: {ancestor})"


def check_paths(settings, productivity=False):
    results = []
    for name in ("site_polygon_path", "raster_opening_path", "lut_path", "threat_csv"):
        results.append(check_file(name, getattr(settings, name)))
    if settings.raster_closing_path is None:
        results.append(("FAIL" if productivity else "WARN",
                        "No closing site raster: conversion and productivity require both years."))
    else:
        results.append(check_file("raster_closing_path", settings.raster_closing_path))
    if settings.legend_qml_path is None:
        results.append(("OK", "Map legend disabled; JPG previews will be skipped."))
    else:
        results.append(check_file("legend_qml_path", settings.legend_qml_path))

    reference_maps = (settings.ref_raster_opening_path, settings.ref_raster_closing_path)
    if all(path is None for path in reference_maps):
        results.append(("OK", "Reference-site productivity comparison disabled."))
    elif any(path is None for path in reference_maps):
        results.append(("FAIL", "Set both reference rasters, or set both to None to disable the comparison."))
    else:
        for name in ("ref_polygon_path", "ref_raster_opening_path", "ref_raster_closing_path"):
            results.append(check_file(name, getattr(settings, name)))

    for name in ("extent_output_dir", "transformations_output_dir", "conversion_output_dir",
                 "connectivity_output_dir", "productivity_output_dir"):
        results.append(check_output(name, getattr(settings, name)))

    if productivity:
        for year in settings.year_labels:
            tiles = sorted(Path(settings.tprod_dir).glob(f"VPP_{year}_S2_*_TPROD.tif"))
            if not tiles:
                results.append(("FAIL", f"No TPROD tiles for {year} in {settings.tprod_dir}. "
                                "Run python -m Metrics_scripts.Download_TPROD after configuring WEkEO credentials."))
            for tile in tiles:
                results.append(check_file(f"TPROD {year}", tile))
    else:
        results.append(("WARN", "TPROD tiles not checked (not bundled). Use --productivity before running productivity."))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--productivity", action="store_true",
                        help="also require readable TPROD tile files for each configured year")
    args = parser.parse_args(argv)
    print(f"Python: {sys.version.split()[0]}\nInterpreter: {sys.executable}")
    print("Read IMPORTANT_READ_FIRST.md before using this demonstration.")
    demo_dir = Path(__file__).resolve().parent
    results = check_dependencies(demo_dir / "requirements.txt")
    try:
        settings = importlib.import_module("EA_setup")
    except (ImportError, OSError, SyntaxError, NameError, TypeError, ValueError) as exc:
        results.append(("FAIL", f"Cannot load EA_setup.py: {type(exc).__name__}: {exc}"))
    else:
        results.extend(check_paths(settings, args.productivity))
    for status, message in results:
        print(f"[{status}] {message}")
    failures = sum(status == "FAIL" for status, _ in results)
    if failures:
        print(f"\nSetup check failed: {failures} problem(s).")
        print("For dependency failures, install requirements into the interpreter printed above:")
        print(f'"{sys.executable}" -m pip install -r "{demo_dir / "requirements.txt"}"')
        print("For path failures, correct EA_setup.py and rerun this check.")
        return 1
    print("\nSetup check passed. Review any warnings before proceeding.")
    print("This checks imports and file access, not raster validity/coverage, settings semantics, "
          "WEkEO authentication or scientific suitability.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
