"""
KubeFlow Pipeline for Document Ingestion
Processes documents and sends them to the doc-ingest-service

Supports two modes:
1. S3/Minio: Downloads documents from object storage (recommended)
2. Local: Uses documents from mounted PVC
"""
from kfp import dsl, compiler
from kfp.dsl import component, Input, Output, Dataset
from typing import List, Optional


@component(
    base_image="registry.access.redhat.com/ubi9/python-311:latest",
    packages_to_install=["boto3"]
)
def download_from_s3(
    s3_endpoint: str,
    s3_bucket: str,
    s3_prefix: str,
    s3_access_key: str,
    s3_secret_key: str,
    download_path: str = "/tmp/documents"
):
    """
    Download documents from S3/Minio to local storage

    Args:
        s3_endpoint: S3 endpoint URL (e.g., https://minio.apps.cluster.com)
        s3_bucket: S3 bucket name
        s3_prefix: Prefix/folder in bucket (e.g., "kb/" or "")
        s3_access_key: S3 access key
        s3_secret_key: S3 secret key
        download_path: Local path to download files to
    """
    import boto3
    import os
    from pathlib import Path

    print(f"Downloading from S3: {s3_endpoint}/{s3_bucket}/{s3_prefix}")

    # Create S3 client (Minio is S3-compatible)
    s3_client = boto3.client(
        's3',
        endpoint_url=s3_endpoint,
        aws_access_key_id=s3_access_key,
        aws_secret_access_key=s3_secret_key,
        verify=False  # For self-signed certs in dev/staging
    )

    # Create download directory
    Path(download_path).mkdir(parents=True, exist_ok=True)

    # List and download all objects with the prefix
    paginator = s3_client.get_paginator('list_objects_v2')
    downloaded_count = 0

    for page in paginator.paginate(Bucket=s3_bucket, Prefix=s3_prefix):
        if 'Contents' not in page:
            continue

        for obj in page['Contents']:
            s3_key = obj['Key']

            # Skip directory markers
            if s3_key.endswith('/'):
                continue

            # Calculate local path (preserve directory structure)
            relative_path = s3_key[len(s3_prefix):] if s3_prefix else s3_key
            local_file = os.path.join(download_path, relative_path)

            # Create local directory if needed
            Path(local_file).parent.mkdir(parents=True, exist_ok=True)

            # Download file
            print(f"  Downloading: {s3_key} -> {local_file}")
            s3_client.download_file(s3_bucket, s3_key, local_file)
            downloaded_count += 1

    print(f"Downloaded {downloaded_count} files to {download_path}")


@component(
    base_image="registry.access.redhat.com/ubi9/python-311:latest",
    packages_to_install=["requests"]
)
def discover_documents(
    documents_path: str,
    file_extensions: List[str],
    discovered_files: Output[Dataset]
):
    """Discover all documents in the specified path"""
    import os
    import json

    files = []
    for root, _, filenames in os.walk(documents_path):
        for filename in filenames:
            if any(filename.endswith(ext) for ext in file_extensions):
                full_path = os.path.join(root, filename)
                files.append(full_path)

    print(f"Discovered {len(files)} files")

    # Write discovered files to output
    with open(discovered_files.path, 'w') as f:
        json.dump(files, f)


@component(
    base_image="registry.access.redhat.com/ubi9/python-311:latest",
    packages_to_install=["requests"]
)
def ingest_document_batch(
    discovered_files: Input[Dataset],
    service_url: str,
    collection_name: str,
    batch_size: int,
    results: Output[Dataset]
):
    """Ingest documents in batches via the vector-search-service API"""
    import json
    import requests
    from pathlib import Path

    # Load discovered files
    with open(discovered_files.path, 'r') as f:
        files = json.load(f)

    print(f"Processing {len(files)} files in batches of {batch_size}")
    print(f"Target collection: {collection_name}")

    batch_results = []
    successful = 0
    failed = 0

    # Process in batches
    for i in range(0, len(files), batch_size):
        batch = files[i:i + batch_size]
        print(f"Processing batch {i//batch_size + 1}: {len(batch)} files")

        for file_path in batch:
            try:
                # Read file content as text
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()

                # Prepare request for vector-search-service
                filename = Path(file_path).name
                payload = {
                    "content": file_content,
                    "metadata": {
                        "source": "kubeflow-pipeline",
                        "file_path": file_path,
                        "filename": filename
                    }
                }

                # Send to vector-search-service collection endpoint
                response = requests.post(
                    f"{service_url}/api/v1/collections/{collection_name}/documents",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=300  # Increased for large files
                )

                if response.status_code in [200, 201]:
                    result = response.json()
                    # vector-search-service returns document_id on success
                    doc_id = result.get('document_id', 'unknown')
                    print(f"SUCCESS: {filename}: Document ID {doc_id}")
                    batch_results.append({
                        "file": file_path,
                        "success": True,
                        "document_id": doc_id
                    })
                    successful += 1
                else:
                    error_detail = response.text
                    print(f"FAILED: {filename}: HTTP {response.status_code} - {error_detail}")
                    batch_results.append({
                        "file": file_path,
                        "success": False,
                        "error": f"HTTP {response.status_code}: {error_detail}"
                    })
                    failed += 1

            except Exception as e:
                print(f"ERROR: {file_path}: {str(e)}")
                batch_results.append({
                    "file": file_path,
                    "success": False,
                    "error": str(e)
                })
                failed += 1

    # Save results
    summary = {
        "total": len(files),
        "successful": successful,
        "failed": failed,
        "results": batch_results
    }

    with open(results.path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nSummary: {successful}/{len(files)} files ingested successfully")


@component(
    base_image="registry.access.redhat.com/ubi9/python-311:latest",
    packages_to_install=["psycopg2-binary"]
)
def verify_ingestion(
    results: Input[Dataset],
    db_host: str,
    db_port: str,
    db_user: str,
    db_password: str,
    db_name: str
):
    """Verify documents were created in the database"""
    import json
    import psycopg2

    # Load results
    with open(results.path, 'r') as f:
        summary = json.load(f)

    print(f"Ingestion results: {summary['successful']} successful, {summary['failed']} failed")

    # Connect to database
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name
    )

    cur = conn.cursor()

    # Query document statistics (vector-search-service tables)
    cur.execute("""
        SELECT
            COUNT(*) as total_documents,
            COUNT(DISTINCT collection_id) as total_collections
        FROM documents
    """)

    doc_stats = cur.fetchone()

    # Query embedding statistics
    cur.execute("""
        SELECT COUNT(*) as total_embeddings
        FROM embeddings
    """)

    emb_stats = cur.fetchone()

    print(f"\nDatabase Statistics:")
    print(f"  Total documents: {doc_stats[0]}")
    print(f"  Total collections: {doc_stats[1]}")
    print(f"  Total embeddings: {emb_stats[0]}")

    cur.close()
    conn.close()


@dsl.pipeline(
    name="Document Ingestion Pipeline",
    description="Discovers and ingests documents into the RAG system from S3/Minio or local storage"
)
def document_ingestion_pipeline(
    # Document source configuration
    use_s3: bool = True,
    documents_path: str = "/tmp/documents",  # Local path after S3 download or mounted PVC
    file_extensions: list = [".md", ".txt", ".html"],

    # S3/Minio configuration (only used if use_s3=True)
    s3_endpoint: str = "",
    s3_bucket: str = "",
    s3_prefix: str = "",
    s3_access_key: str = "",
    s3_secret_key: str = "",

    # Service configuration (cluster-internal URLs)
    service_url: str = "http://vector-search-service.servicenow-ai-poc.svc.cluster.local:8000",
    collection_name: str = "default",
    batch_size: int = 10,

    # Database configuration (cluster-internal)
    db_host: str = "postgres-pgvector.servicenow-ai-poc.svc.cluster.local",
    db_port: str = "5432",
    db_user: str = "raguser",
    db_password: str = "",  # MUST be provided
    db_name: str = "ragdb"
):
    """
    Main pipeline for document ingestion

    Args:
        use_s3: If True, download from S3/Minio first. If False, use documents_path directly
        documents_path: Path to documents directory (destination for S3 or mounted PVC)
        file_extensions: List of file extensions to process

        s3_endpoint: S3 endpoint URL (e.g., https://your-minio-endpoint)
        s3_bucket: S3 bucket name
        s3_prefix: Prefix/folder in bucket (e.g., "kb/")
        s3_access_key: S3 access key
        s3_secret_key: S3 secret key

        service_url: URL of the vector-search-service (cluster-internal)
        collection_name: Name of the collection to ingest documents into
        batch_size: Number of documents to process in each batch

        db_host: PostgreSQL host (cluster-internal)
        db_port: PostgreSQL port
        db_user: PostgreSQL user
        db_password: PostgreSQL password (required)
        db_name: PostgreSQL database name
    """

    # Step 0: Download from S3/Minio if enabled (conditional)
    with dsl.If(use_s3 == True):
        download_task = download_from_s3(
            s3_endpoint=s3_endpoint,
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
            s3_access_key=s3_access_key,
            s3_secret_key=s3_secret_key,
            download_path=documents_path
        )
        download_task.set_caching_options(False)

    # Step 1: Discover documents
    discover_task = discover_documents(
        documents_path=documents_path,
        file_extensions=file_extensions
    )
    discover_task.set_caching_options(False)

    # Step 2: Ingest documents in batches
    ingest_task = ingest_document_batch(
        discovered_files=discover_task.outputs["discovered_files"],
        service_url=service_url,
        collection_name=collection_name,
        batch_size=batch_size
    )
    ingest_task.set_caching_options(False)

    # Step 3: Verify ingestion
    verify_task = verify_ingestion(
        results=ingest_task.outputs["results"],
        db_host=db_host,
        db_port=db_port,
        db_user=db_user,
        db_password=db_password,
        db_name=db_name
    )
    verify_task.set_caching_options(False)


if __name__ == "__main__":
    # Compile pipeline
    compiler.Compiler().compile(
        pipeline_func=document_ingestion_pipeline,
        package_path="doc_ingestion_pipeline.yaml"
    )
    print("Pipeline compiled to doc_ingestion_pipeline.yaml")
