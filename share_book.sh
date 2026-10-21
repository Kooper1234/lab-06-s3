#!/bin/bash
# Download one book, upload it to a private S3 bucket, and print a presigned URL.
set -euo pipefail

# Check that all three arguments are there
if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <book_url> <bucket> <expires_in_seconds>"
    exit 1
fi

URL="$1"
BUCKET="$2"
EXPIRES="$3"
FILE_NAME="$(basename "$URL")"   # e.g. pg1342.txt
LOCAL_PATH="books/$FILE_NAME"

# Download the book into books direcotey
mkdir -p books
curl -f -o "$LOCAL_PATH" "$URL"

# Make the bucket 
if aws s3 ls "s3://$BUCKET" > /dev/null 2>&1; then
    echo "Bucket $BUCKET already exists"
else
    aws s3 mb "s3://$BUCKET"
fi

# Upload the book 
aws s3 cp "$LOCAL_PATH" "s3://$BUCKET/$FILE_NAME" --content-type "text/plain; charset=utf-8"

# Presign a URL to the book and print it
aws s3 presign "s3://$BUCKET/$FILE_NAME" --expires-in "$EXPIRES"