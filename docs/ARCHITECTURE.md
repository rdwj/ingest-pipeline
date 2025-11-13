# Pipeline Architecture

## Overview

This KubeFlow pipeline demonstrates enterprise-grade document ingestion for RAG (Retrieval-Augmented Generation) systems.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     OpenShift AI Pipeline                       │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Step 0: Download from S3/Minio (Conditional)            │   │
│  │ - boto3 S3 client                                       │   │
│  │ - Downloads all files from bucket/prefix                │   │
│  │ - Preserves directory structure                         │   │
│  └─────────────────┬───────────────────────────────────────┘   │
│                    │                                            │
│                    v                                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Step 1: Discover Documents                              │   │
│  │ - Walks directory tree                                  │   │
│  │ - Filters by file extension                             │   │
│  │ - Creates file list                                     │   │
│  └─────────────────┬───────────────────────────────────────┘   │
│                    │                                            │
│                    v                                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Step 2: Ingest Document Batch                           │   │
│  │ - Processes files in configurable batches               │   │
│  │ - POSTs to doc-ingest-service API                      │   │
│  │ - Tracks success/failure per document                   │   │
│  └─────────────────┬───────────────────────────────────────┘   │
│                    │                                            │
│                    v                                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Step 3: Verify Ingestion                                │   │
│  │ - Connects to PostgreSQL                                │   │
│  │ - Queries chunk statistics                              │   │
│  │ - Reports totals and averages                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              v
         ┌────────────────────────────────────────┐
         │    doc-ingest-service (FastAPI)        │
         │  - Document parsing (Docling)          │
         │  - Text chunking (LangChain)           │
         │  - Embedding generation (Nomic)        │
         │  - PostgreSQL insertion                │
         └────────────────┬───────────────────────┘
                          │
                          v
         ┌────────────────────────────────────────┐
         │   PostgreSQL + pgvector Extension      │
         │  - document_chunks table                │
         │  - HNSW vector index                    │
         │  - Full-text search index               │
         └────────────────────────────────────────┘
```

## Components

### Pipeline Components (KubeFlow)

Each pipeline step runs as a containerized component in OpenShift:

#### 1. download_from_s3
- **Base Image**: `registry.access.redhat.com/ubi9/python-311:latest`
- **Dependencies**: `boto3`
- **Function**: Downloads documents from S3/Minio to local ephemeral storage
- **Conditional**: Only runs if `use_s3=true`

#### 2. discover_documents
- **Base Image**: `registry.access.redhat.com/ubi9/python-311:latest`
- **Dependencies**: `requests`
- **Function**: Scans directory for documents matching file extensions
- **Output**: JSON list of file paths

#### 3. ingest_document_batch
- **Base Image**: `registry.access.redhat.com/ubi9/python-311:latest`
- **Dependencies**: `requests`
- **Function**: Sends documents to ingestion service API
- **Batch Size**: Configurable (default 10)
- **Timeout**: 300 seconds per request (handles large files)

#### 4. verify_ingestion
- **Base Image**: `registry.access.redhat.com/ubi9/python-311:latest`
- **Dependencies**: `psycopg2-binary`
- **Function**: Queries database to verify chunk creation
- **Output**: Statistics summary

### External Services

#### doc-ingest-service
- **Technology**: FastAPI
- **Port**: 8001
- **Functions**:
  - Document parsing with Docling (handles HTML, MD, PDF, DOCX)
  - Text cleaning (encoding fixes, null byte removal)
  - Text chunking with LangChain RecursiveCharacterTextSplitter
  - Embedding generation via Nomic API (768-dimensional vectors)
  - PostgreSQL insertion with metadata

#### PostgreSQL with pgvector
- **Version**: PostgreSQL 15+
- **Extension**: pgvector 0.5.0+
- **Schema**:
  ```sql
  CREATE TABLE document_chunks (
      id SERIAL PRIMARY KEY,
      document_uri TEXT NOT NULL,
      chunk_index INTEGER NOT NULL,
      text TEXT NOT NULL,
      embedding vector(768),  -- Nomic embeddings
      metadata JSONB,
      created_at TIMESTAMP DEFAULT NOW()
  );

  -- HNSW index for fast vector search
  CREATE INDEX idx_embedding_hnsw ON document_chunks
    USING hnsw (embedding vector_cosine_ops);
  ```

## Data Flow

### 1. Document Upload (Pre-Pipeline)

```
Developer Laptop → GitHub → Minio (via web UI or mc)
```

### 2. Pipeline Execution

```
Minio S3 → Pipeline Pod → doc-ingest-service → PostgreSQL
```

### 3. Processing Steps Per Document

```
1. Read file bytes
2. Send to /ingest endpoint with multipart/form-data
3. Service receives file
4. Clean text (UTF-8 normalization, null byte removal)
5. Parse with Docling (extract clean text)
6. Chunk with LangChain (800 char chunks, 150 overlap)
7. Generate embeddings via Nomic API
8. Insert chunks into PostgreSQL
9. Return chunk count
```

## Network Architecture

### Cluster-Internal Communication

All services communicate via cluster-internal DNS:

```
pipeline-pod.namespace.svc.cluster.local
    ↓
doc-ingest-service.<namespace>.svc.cluster.local:8001
    ↓
postgres-pgvector.<namespace>.svc.cluster.local:5432
```

### External Access Points

- **Minio**: `http://minio-api-minio.apps.<cluster-domain>` (internal route)
- **OpenShift AI**: `https://rhods-dashboard-redhat-ods-applications.apps.<cluster-domain>`
- **Developer Access**: Via cluster workstation or web console

## Security

### Secrets Management

Sensitive data passed as pipeline parameters (stored in OpenShift AI):
- S3 access key and secret key
- Database password

**Best Practice**: Use OpenShift Secrets and reference them in pipeline runs.

### Network Isolation

- Pipeline pods run in user's Data Science Project namespace
- Services access via cluster-internal networking only
- No external internet access required during pipeline execution (post-download)

## Scalability

### Current Configuration
- **Batch Size**: 10 documents per batch
- **Timeout**: 300 seconds per document
- **Parallelism**: Sequential batch processing

### Optimization Options
1. **Increase Batch Size**: Process more documents concurrently (requires service scaling)
2. **Parallel Batches**: Modify pipeline to process multiple batches in parallel
3. **Service Replicas**: Scale doc-ingest-service horizontally
4. **Database Connection Pooling**: Increase PostgreSQL connections

### Expected Performance

For 90 documents (~5MB total):
- **S3 Download**: 10-30 seconds
- **Discovery**: 1 second
- **Ingestion**: 2-5 minutes (depends on file sizes and embedding API latency)
- **Verification**: 1 second

**Throughput**: ~300-500 documents per hour with current configuration

## Error Handling

### Retry Logic
- Pipeline steps do not auto-retry (fail fast)
- Failed documents logged with error details
- Pipeline completes even if some documents fail

### Common Failure Modes
1. **S3 Timeout**: Network issues or slow Minio
2. **Service Timeout**: Large files >5MB or slow embedding API
3. **Encoding Errors**: Fixed by clean_text() function in service
4. **Database Connection**: PostgreSQL unavailable or full

### Recovery Strategy
- Review pipeline logs to identify failed documents
- Re-run pipeline with failed documents only (future enhancement)
- Check service logs for detailed error messages

## Monitoring

### Pipeline Observability
- Each step logs detailed progress
- Success/failure counts reported
- Database verification provides final confirmation

### Service Health Checks
```bash
# doc-ingest-service
curl http://doc-ingest-service:8001/health

# PostgreSQL
psql -h postgres-pgvector -U raguser -d ragdb -c "SELECT 1;"
```

## Future Enhancements

1. **Incremental Ingestion**: Skip already-processed documents
2. **Parallel Processing**: Process multiple batches simultaneously
3. **Advanced Error Recovery**: Automatic retry with exponential backoff
4. **Real-time Monitoring**: Prometheus metrics and Grafana dashboards
5. **Document Versioning**: Track document changes and re-embedding
6. **Quality Checks**: Validate embedding quality and chunk coherence

## References

- [KubeFlow Pipelines Documentation](https://www.kubeflow.org/docs/components/pipelines/)
- [PostgreSQL pgvector](https://github.com/pgvector/pgvector)
- [Docling](https://github.com/DS4SD/docling)
- [LangChain Text Splitters](https://python.langchain.com/docs/modules/data_connection/document_transformers/)
