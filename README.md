# Document Ingestion Pipeline

KubeFlow pipeline for ingesting documents into PostgreSQL with pgvector for semantic search in RAG systems.

## Overview

This pipeline demonstrates enterprise-grade document ingestion for AI/RAG systems:

1. **Download from S3/Minio** - Retrieves documents from object storage
2. **Discover Documents** - Scans for markdown, HTML, and text files
3. **Ingest & Embed** - Processes documents, generates embeddings, stores in PostgreSQL+pgvector
4. **Verify** - Confirms successful ingestion with database statistics

**Technology Stack:**
- KubeFlow Pipelines for orchestration
- Minio/S3 for document storage
- PostgreSQL with pgvector extension for vector storage
- Nomic embeddings (768-dimensional vectors)
- Red Hat OpenShift AI for execution

## Quick Start

### Prerequisites

- OpenShift AI Data Science Project
- Minio with documents uploaded
- doc-ingest-service deployed and accessible
- PostgreSQL with pgvector deployed

### Deploy Pipeline

1. **Clone this repository** (on your VNC/cluster workstation):
   ```bash
   git clone https://your-gitlab-url/ingest-pipeline.git
   cd ingest-pipeline
   ```

2. **Compile pipeline** (if making changes):
   ```bash
   python pipeline.py
   ```

3. **Upload to OpenShift AI**:
   - Open OpenShift AI web console
   - Navigate to your Data Science Project
   - Go to **Pipelines** → **Import pipeline**
   - Upload `doc_ingestion_pipeline.yaml`

4. **Configure parameters** (see example in `example-parameters.yaml`)

5. **Create run** and monitor progress

## Pipeline Parameters

### Document Source
- `use_s3`: `true` (enable S3/Minio download)
- `documents_path`: `/tmp/documents` (local path for downloaded files)
- `file_extensions`: `[".md", ".txt", ".html"]`

### S3/Minio Configuration
- `s3_endpoint`: Minio endpoint URL
- `s3_bucket`: Bucket name (e.g., `kb-documents`)
- `s3_prefix`: Folder prefix (e.g., `kb/`)
- `s3_access_key`: Minio access key
- `s3_secret_key`: Minio secret key

### Service Configuration
- `service_url`: `http://doc-ingest-service.servicenow-ai-poc.svc.cluster.local:8001`
- `batch_size`: `10` (documents per batch)

### Database Configuration
- `db_host`: `postgres-pgvector.servicenow-ai-poc.svc.cluster.local`
- `db_port`: `5432`
- `db_user`: `raguser`
- `db_password`: **(required - from OpenShift secret)**
- `db_name`: `ragdb`

## Files

```
ingest-pipeline/
├── README.md                        # This file
├── pipeline.py                      # Pipeline source code
├── doc_ingestion_pipeline.yaml      # Compiled pipeline (ready to upload)
├── example-parameters.yaml          # Example run parameters
├── requirements.txt                 # Python dependencies
├── verify-pipeline.sh               # Helper script to test compilation
└── docs/
    ├── ARCHITECTURE.md              # Technical architecture
    └── TROUBLESHOOTING.md           # Common issues and solutions
```

## Expected Results

For a typical knowledge base with ~90 documents:

- **Download**: ~10-30 seconds (depends on file sizes)
- **Discovery**: ~1 second
- **Ingestion**: ~2-5 minutes for 90 files (with encoding fixes applied)
- **Success Rate**: ~85-90% (large files may timeout)

**Database Output:**
- ~380 chunks created
- ~76 documents successfully processed
- Average chunk length: ~785 characters

## Proof of Value

This pipeline demonstrates:

✅ **Enterprise Integration**: S3/Minio, PostgreSQL, OpenShift AI
✅ **Scalability**: Batch processing with configurable sizes
✅ **Observability**: Detailed logging and verification steps
✅ **Production-Ready**: Error handling, retries, cluster-internal networking
✅ **MLOps Best Practices**: KubeFlow pipelines, version control, reproducibility

## Next Steps

1. Run pipeline with your KB documents
2. Verify vector search results
3. Demonstrate semantic search capabilities
4. Show vector similarity metrics
5. Extend to production dataset

## Support

For issues:
- Check `docs/TROUBLESHOOTING.md`
- Review pipeline logs in OpenShift AI console
- Verify service health endpoints

---

**Author**: rdwj
**Version**: 1.0
**Date**: November 2025
