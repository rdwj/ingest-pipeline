#!/usr/bin/env python3
"""
Test MinIO S3 access and list bucket contents
Run this as a Kubernetes Job to diagnose MinIO connectivity
"""
import os
import sys
import boto3
from botocore.exceptions import ClientError

def test_minio_access():
    """Test MinIO S3 access with provided credentials"""

    # Get parameters from environment variables
    endpoint = os.getenv('MINIO_ENDPOINT', [replace with your minio endpoint])
    access_key = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
    secret_key = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
    bucket = os.getenv('MINIO_BUCKET', 'kb-documents')
    prefix = os.getenv('MINIO_PREFIX', 'data/')

    print(f"Testing MinIO S3 Access")
    print(f"=" * 60)
    print(f"Endpoint: {endpoint}")
    print(f"Bucket: {bucket}")
    print(f"Prefix: {prefix}")
    print(f"Access Key: {access_key[:4]}...{access_key[-4:] if len(access_key) > 8 else '****'}")
    print(f"=" * 60)
    print()

    try:
        # Create S3 client
        print("Creating S3 client...")
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            verify=False  # For self-signed certs
        )
        print("SUCCESS: S3 client created")
        print()

        # Test 1: List buckets
        print("Test 1: Listing all buckets...")
        try:
            response = s3_client.list_buckets()
            buckets = [b['Name'] for b in response.get('Buckets', [])]
            print(f"SUCCESS: Found {len(buckets)} buckets:")
            for b in buckets:
                print(f"  - {b}")
            print()
        except ClientError as e:
            print(f"FAILED: {e}")
            print()

        # Test 2: Check if our bucket exists
        print(f"Test 2: Checking if bucket '{bucket}' exists...")
        try:
            s3_client.head_bucket(Bucket=bucket)
            print(f"SUCCESS: Bucket '{bucket}' exists")
            print()
        except ClientError as e:
            print(f"FAILED: Bucket '{bucket}' does not exist or access denied: {e}")
            print()
            return 1

        # Test 3: List objects in bucket with prefix
        print(f"Test 3: Listing objects in '{bucket}/{prefix}'...")
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            object_count = 0

            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                if 'Contents' not in page:
                    print(f"No objects found with prefix '{prefix}'")
                    continue

                for obj in page['Contents']:
                    # Skip directory markers
                    if obj['Key'].endswith('/'):
                        continue
                    object_count += 1
                    size_mb = obj['Size'] / (1024 * 1024)
                    print(f"  {obj['Key']} ({size_mb:.2f} MB)")

            print()
            print(f"SUCCESS: Found {object_count} objects in '{bucket}/{prefix}'")
            print()

            if object_count == 0:
                print("WARNING: No files found! Check:")
                print(f"  1. Files are uploaded to '{bucket}/{prefix}'")
                print(f"  2. Prefix is correct (should end with / if it's a directory)")
                return 1

        except ClientError as e:
            print(f"FAILED: {e}")
            return 1

        # Test 4: Try to download first file
        print("Test 4: Testing download capability...")
        try:
            # Get first non-directory object
            response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=10)
            if 'Contents' in response:
                for obj in response['Contents']:
                    if not obj['Key'].endswith('/'):
                        test_key = obj['Key']
                        print(f"Attempting to download: {test_key}")

                        # Download to memory (don't save to disk)
                        response = s3_client.get_object(Bucket=bucket, Key=test_key)
                        content_length = len(response['Body'].read())
                        print(f"SUCCESS: Downloaded {content_length} bytes")
                        break
                else:
                    print("No downloadable files found (all are directories)")
            else:
                print("No objects to test download")
        except ClientError as e:
            print(f"FAILED: {e}")
            return 1

        print()
        print("=" * 60)
        print("All tests passed! MinIO S3 access is working correctly.")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(test_minio_access())
