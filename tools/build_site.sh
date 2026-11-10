#!/bin/sh
# Copies the files the page needs into dist/ for static hosting.
# Family folders are found from index.html, so new families need no change here.
set -e
cd "$(dirname "$0")/.."
rm -rf dist
mkdir -p dist
cp index.html app.js styles.css coach.js dist/
for dir in $(grep -o 'src="[a-z-]*/manifest.js"' index.html | sed 's/src="\(.*\)\/manifest.js"/\1/'); do
  mkdir -p "dist/$dir"
  cp "$dir"/*.js "dist/$dir/"
done
echo "dist/ ready: $(find dist -type f | wc -l) files"
