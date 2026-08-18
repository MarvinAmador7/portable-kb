# Release and installation

## Version contract

`src/portable_kb/__init__.py` is the single source of truth for the stable
`X.Y.Z` version. Hatch reads that value for Python distribution metadata, the
CLI reports it through `pkb --version`, and release assets use the matching
`vX.Y.Z` tag. A release never derives a version from a mutable branch name.

To prepare a release, change `__version__` in a focused pull request. CI tests
the proposed commit. After it merges to `main`, the release workflow checks
whether the corresponding release or tag already exists. Existing releases are
left untouched, while an orphaned existing tag fails closed for human review.

## Continuous integration

`.github/workflows/ci.yml` runs on pull requests and pushes to `main` with
read-only repository permissions. It performs:

- lint and the complete coverage-gated test suite on supported Linux and macOS
  Python environments;
- POSIX shell syntax validation for `install`;
- wheel and source-distribution builds plus metadata checks;
- verification that schemas and the Portable KB agent skill are in the wheel;
  and
- a clean-environment wheel install and CLI smoke test.

GitHub-owned workflow actions are pinned to exact commit SHAs. Tests require no
release, deployment credential, or writable repository token.

## Automated GitHub release

`.github/workflows/release.yml` runs after the version source changes on
`main`, and can also be inspected through a manual dispatch. A new version is
published only after the release gate passes. The workflow builds:

```text
portable_kb_core-X.Y.Z-py3-none-any.whl
portable_kb_core-X.Y.Z.tar.gz
pkb-vX.Y.Z-darwin-arm64.tar.gz
pkb-vX.Y.Z-darwin-x86_64.tar.gz
pkb-vX.Y.Z-linux-arm64.tar.gz
pkb-vX.Y.Z-linux-x86_64.tar.gz
SHA256SUMS
```

Each standalone executable is built from the wheel on its native GitHub-hosted
runner. Before upload, it must report the expected version, complete local
setup, initialize and validate a fresh brain with the bundled schemas, and
install its bundled agent skill into an isolated temporary home. The publish
job uses only the scoped workflow `GITHUB_TOKEN` with `contents: write`, creates
the semantic tag at the tested `main` commit, generates release notes, and
uploads version-named assets. Post-publication jobs then run the real installer
against the release on all four target platforms.

Linux executables are built on Ubuntu 22.04 to retain compatibility with that
glibc baseline and newer compatible distributions. Alpine/musl and Windows are
not release targets in this milestone.

The workflow creates GitHub release assets; it does not publish to PyPI, alter
repository visibility, notarize a future macOS application, or install QMD.

The 0.1.2 CI and release gates install pinned `@tobilu/qmd@2.8.3` under Node.js
24 and exercise an isolated real keyword index plus cited query. This verifies
the optional external provider without adding QMD to the standalone archive or
downloading embedding models during installation.

## Installer safety

The root `install` script requires `curl`, `tar`, and either `sha256sum` or
`shasum`. It downloads the selected archive and `SHA256SUMS` into an
operation-owned temporary directory, verifies the exact filename digest, and
stages the executable before an atomic move to `~/.local/bin/pkb` (or
`PKB_INSTALL_DIR`). A failed download, missing checksum, checksum mismatch, bad
archive, or failed version check leaves the previous executable intact.

Re-running the installer upgrades to the latest GitHub release. Use
`--version vX.Y.Z` to install or restore a specific version. Explicit
`--uninstall` removes only the `pkb` executable at the selected install path;
it intentionally preserves brain repositories, configuration, indexes, and
agent skills.

Public repositories support the anonymous one-line `raw.githubusercontent.com`
command. While this repository remains private, retrieve the script and assets
with an exported `GH_TOKEN` and authenticated `gh` CLI. Repository visibility
is a separate owner decision and is never changed by CI.
