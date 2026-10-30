#!/usr/bin/env bash
set +x
python3 build.py
cd dist
docker run --rm -p 8000:80 -v "$(pwd)":/usr/share/nginx/html:ro,Z nginx:latest
