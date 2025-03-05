#!/bin/bash

# Root directory (change if needed)
ROOT_DIR="$(pwd)"
OUTPUT_DIR="$ROOT_DIR/download"
RELEASE_FILE="$OUTPUT_DIR/docker-compose-release.txt"

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

# Clear release file if it exists
echo "Docker Images Backup - $(date)" > "$RELEASE_FILE"

# Find and process each docker-compose.yml
find "$ROOT_DIR/docker-compose" -name "docker-compose.yml" | while read -r compose_file; do
    echo "Processing: $compose_file"

    # Change to the directory containing docker-compose.yml
    compose_dir="$(dirname "$compose_file")"
    cd "$compose_dir" || continue

    # Extract and pull images
    images=$(docker compose config | awk '/image:/ {print $2}')

    for image in $images; do
        echo "Pulling image: $image"
        docker pull "$image"

        # Save image as tar.gz
        image_name=$(echo "$image" | tr '/:' '_')
        output_file="$OUTPUT_DIR/${image_name}.tar.gz"

        echo "Saving image: $image to $output_file"
        docker save "$image" | gzip > "$output_file"

        # Add to release.txt
        echo "$image" >> "$RELEASE_FILE"
    done

done

echo "Backup complete. Images saved to $OUTPUT_DIR and release.txt generated."
