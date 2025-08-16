#!/usr/bin/env bash
REQ=${1:-requirements.docker.txt}
OUT=${2:-wheelhouse}

if [ ! -f "$REQ" ]; then
  echo "Requirements file not found: $REQ" >&2
  exit 1
fi

mkdir -p "$OUT"
python -m pip download -r "$REQ" -d "$OUT"
echo "Downloaded wheels to $OUT. Copy $OUT into your build context and run: docker compose build --build-arg WHEELHOUSE=1"
