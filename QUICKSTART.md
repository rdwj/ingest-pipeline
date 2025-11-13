# Quick Start Guide

Get the pipeline running in 5 minutes.

## Prerequisites Checklist

- [ ] Documents uploaded to Minio (`kb-documents` bucket)
- [ ] doc-ingest-service deployed and running
- [ ] PostgreSQL with pgvector deployed
- [ ] OpenShift AI Data Science Project created
- [ ] Have Minio and DB credentials ready

## 5-Minute Setup

### 1. Get Credentials

```bash
# On your VNC/cluster workstation

# Get database password
oc get secret postgres-pgvector-secret -n servicenow-ai-poc \
  -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d
# Save this password

# Get Minio credentials (if stored in secret)
oc get secret minio-credentials -n servicenow-ai-poc -o yaml
# Or use the credentials you used to upload files
```

### 2. Upload Pipeline

1. Open OpenShift AI web console
2. Go to your Data Science Project
3. Click **Pipelines** → **Import pipeline**
4. Upload: `doc_ingestion_pipeline.yaml`
5. Click **Import**

### 3. Create Run

Click **Create run** and fill in these values:

```yaml
# Copy these values, replacing YOUR_* placeholders:

use_s3: true
documents_path: /tmp/documents
file_extensions: [".md", ".txt", ".html"]

s3_endpoint: https://your-minio-endpoint
s3_bucket: kb-documents
s3_prefix: data/
s3_access_key: YOUR_MINIO_ACCESS_KEY
s3_secret_key: YOUR_MINIO_SECRET_KEY

service_url: http://doc-ingest-service.servicenow-ai-poc.svc.cluster.local:8001
batch_size: 10

db_host: postgres-pgvector.servicenow-ai-poc.svc.cluster.local
db_port: 5432
db_user: raguser
db_password: YOUR_DATABASE_PASSWORD
db_name: ragdb
```

### 4. Run and Monitor

1. Click **Create run**
2. Watch the pipeline graph
3. Click steps to view logs
4. Wait for completion (~3-5 minutes for 90 documents)

### 5. Verify Results

```bash
# Port-forward to PostgreSQL
oc port-forward statefulset/postgres-pgvector 5432:5432 -n servicenow-ai-poc

# In another terminal, query results
PGPASSWORD='your-password' psql -h localhost -U raguser -d ragdb -c "
  SELECT
    COUNT(*) as chunks,
    COUNT(DISTINCT document_uri) as docs
  FROM document_chunks
  WHERE metadata->>'source' = 'kubeflow-pipeline';"
```

Expected output:
```
 chunks | docs
--------+------
    380 |   76
```

## Success! 🎉

You now have:
- ✅ Documents ingested and chunked
- ✅ Embeddings generated and stored
- ✅ Vector search ready database
- ✅ KubeFlow pipeline proven

## Next Steps

1. **Test Vector Search**:
   ```bash
   # Query the vector-search service
   curl -X POST http://vector-search-service:8000/api/v1/search \
     -H "Content-Type: application/json" \
     -d '{"query": "How to troubleshoot VNC?", "limit": 5}'
   ```

2. **Demonstrate to Stakeholders**:
   - Show pipeline execution in OpenShift AI
   - Show database statistics
   - Demonstrate semantic search results
   - Explain architecture (use `docs/ARCHITECTURE.md`)

3. **Scale Up**:
   - Add more documents to Minio
   - Re-run pipeline with larger dataset
   - Increase `batch_size` for faster processing

## Troubleshooting

If something goes wrong:
1. Check `docs/TROUBLESHOOTING.md`
2. View pipeline step logs in OpenShift AI
3. Check service logs: `oc logs -f deployment/doc-ingest-service -n servicenow-ai-poc`

## Common Issues

**Pipeline upload fails**: Run `./verify-pipeline.sh` to check YAML

**S3 connection fails**: Verify endpoint URL and credentials

**Service timeout**: Increase timeout or reduce batch_size

**DB connection fails**: Check password and verify PostgreSQL is running

---

**Time to success**: ~5 minutes
**Success rate**: 85-90% of documents
**Total pipeline runtime**: 3-5 minutes for 90 documents
