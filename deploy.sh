#!/usr/bin/env bash
set +x
cd dist
docker run --rm -p 8000:80 -v "$(pwd)":/usr/share/nginx/html:ro,Z nginx:latest
