# Wheelhouse offline build

This repo now supports an offline `wheelhouse` for Docker builds to avoid network dependency.

How to create the wheelhouse (on a machine with working internet):

Windows PowerShell:

```powershell
.\download_wheelhouse.ps1 -requirements requirements.docker.txt -output wheelhouse
```

Linux / macOS:

```bash
./download_wheelhouse.sh requirements.docker.txt wheelhouse
```

How to build using the wheelhouse:

1. Copy the `wheelhouse/` directory into the repository root so path is `./wheelhouse`.
2. Build normally:

```bash
docker compose build --progress=plain
```

Notes:

- Dockerfile will prefer installing from `/wheelhouse` when present.
- If you want to keep the wheelhouse out of the repo, pass it as build context or use `--build-arg` to copy it in via your CI.
- Wheelhouse must contain all required distributions and wheels for your platform (many packages publish platform-specific wheels). On Windows, build the wheelhouse on a Linux or Windows machine matching your build environment depending on your target image.
