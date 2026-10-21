#!/usr/bin/env python3
"""Downloads books, creates a public bucket and uploads the books to it. Publicly accessible URL is returned."""
import json
import logging
import os
import sys
import time
import boto3
import requests
from botocore.exceptions import ClientError
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)
s3 = boto3.client("s3", region_name="us-east-1")
def parse_args():
    """Parse command line arguments."""
    if len(sys.argv) < 4:
        log.error(f"Usage: {sys.argv[0]} <list_file> <index_path> <bucket>")
        sys.exit(1)
    else:
        list_file = sys.argv[1]
        index_path = sys.argv[2]
        bucket = sys.argv[3]
        return list_file, index_path, bucket

def download_books(list_file, dest_dir):
    """Download each book URL in list_file into dest_dir. Returns a list of local paths of the books that are available.
    """
    os.makedirs(dest_dir, exist_ok=True)  # like mkdir -p
    book_paths = []
    with open(list_file) as f:
        for line in f:
            url = line.strip()
            if not url:
                continue
            file_name = url.split("/")[-1]
            book_path = os.path.join(dest_dir, file_name)
            if os.path.exists(book_path):
                log.info(f"Already have {book_path}, skipping download")
                book_paths.append(book_path)
                continue
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                with open(book_path, "wb") as out:
                    out.write(response.content)
                book_paths.append(book_path)
                log.info(f"Downloaded {url} -> {book_path}")
            except requests.RequestException as e:
                log.error(f"Error downloading {url}: {e}")
            time.sleep(1)
    log.info(f"{len(book_paths)} books available in {dest_dir}/")
    return book_paths
    
def create_bucket(bucket):
    """Create the bucket unless it already exists. And returns True if the bucket exists afterwards, False otherwise."""
    try:
        s3.head_bucket(Bucket=bucket)
        log.info(f"Bucket {bucket} already exists")
        return True
    except ClientError:
        log.info(f"Bucket {bucket} not found, creating it")
    try:
        s3.create_bucket(Bucket=bucket)
        log.info(f"Created bucket: {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error creating bucket {bucket}: {e}")
        return False

def make_public(bucket):
    """Turn off Block Public Access and attach a public-read bucket policy."""
    try:
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )
        log.info(f"Turned off Block Public Access for {bucket}")
    except ClientError as e:
        log.error(f"Error turning off Block Public Access for {bucket}: {e}")
        return False
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket}/*",
            }
        ],
    }
    try:
        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        log.info(f"Attached public-read policy to {bucket}")
        return True
    except ClientError as e:
        log.error(f"Error attaching bucket policy to {bucket}: {e}")
        return False

def upload_files(bucket, file_paths):
    """Upload each file to the top level of the bucket. Returns the number uploaded."""
    uploaded = 0
    for path in file_paths:
        key = os.path.basename(path)
        try:
            with open(path, "rb") as f:
                s3.put_object(Bucket=bucket, Key=key, Body=f, ContentType="text/plain; charset=utf-8")
            uploaded += 1
            log.info(f"Uploaded {path} to s3://{bucket}/{key}")
        except (FileNotFoundError, ClientError) as e:
            log.error(f"Error uploading {path}: {e}")
    log.info(f"Uploaded {uploaded} of {len(file_paths)} files")
    return uploaded


def upload_index(bucket, index_path):
    """Upload the index page as index.html. Returns True on success, False otherwise."""
    try:
        with open(index_path, "rb") as f:
            s3.put_object(Bucket=bucket, Key="index.html", Body=f, ContentType="text/html")
        log.info(f"Uploaded {index_path} to s3://{bucket}/index.html")
        return True
    except FileNotFoundError:
        log.error(f"Local file not found: {index_path}")
    except ClientError as e:
        log.error(f"Error uploading {index_path}: {e}")
    return False

def main():
    """Download the books, stage them in a public bucket, and log the index URL."""
    list_file, index_path, bucket = parse_args()

    book_paths = download_books(list_file, "books")
    if not book_paths:
        log.error("No books were downloaded")
        sys.exit(1)

    if not create_bucket(bucket) or not make_public(bucket):
        log.error(f"Could not create public bucket {bucket}")
        sys.exit(1)

    uploaded = upload_files(bucket, book_paths)
    index_ok = upload_index(bucket, index_path)

    if uploaded == len(book_paths) and index_ok:
        log.info("Success: all files uploaded")
    else:
        log.error("Failure - some files were not uploaded")
    log.info(f"Index page: https://{bucket}.s3.amazonaws.com/index.html")


if __name__ == "__main__":
    main()
