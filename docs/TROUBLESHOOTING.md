# Troubleshooting Guide

Common issues and solutions when running the document ingestion pipeline.

## Table of Contents
- [Pipeline Upload Issues](#pipeline-upload-issues)
- [S3/Minio Connection Problems](#s3minio-connection-problems)
- [Service Connection Failures](#service-connection-failures)
- [Database Issues](#database-issues)
- [Document Processing Failures](#document-processing-failures)
- [Performance Problems](#performance-problems)

---

## Pipeline Upload Issues

### Error: "Invalid YAML format"

**Symptoms**: OpenShift AI rejects the pipeline YAML file

**Solutions**:
```bash
# Validate YAML structure locally
python -c "import yaml; yaml.safe_load(open('doc_ingestion_pipeline.yaml'))"

# Recompile pipeline
python pipeline.py

# Check file size (should be ~20-40KB)
ls -lh doc_ingestion_pipeline.yaml
```

### Error: "Pipeline already exists"

**Symptoms**: Cannot upload pipeline with same name

**Solutions**:
1. Delete existing pipeline in OpenShift AI UI
2. Or rename pipeline in `pipeline.py`:
   ```python
   name="Document Ingestion Pipeline v2"
   ```
3. Recompile: `python pipeline.py`

---

## S3/Minio Connection Problems

### Error: "Connection timeout to S3 endpoint"

**Symptoms**: `download-from-s3` step fails immediately

**Diagnosis**:
```bash
# Test Minio connectivity from cluster
oc run test-curl --image=curlimages/curl --rm -it -n <namespace> -- \
  curl -v http://minio-api-minio.apps.<cluster-domain>

# Check Minio service status
oc get pods -l app=minio -n <namespace>
oc get svc minio -n <namespace>
```

**Solutions**:
- Verify S3 endpoint URL (use internal cluster URL, not external)
- Check Minio pods are running
- Verify network policies allow access

### Error: "Access Denied (403)"

**Symptoms**: S3 download fails with authentication error

**Diagnosis**:
```bash
# Verify credentials work from Minio UI
# Login to http://minio-api-minio.apps.<cluster-domain>

# Or test with mc:
mc alias set test http://minio-api-minio.apps.<cluster-domain> ACCESS_KEY SECRET_KEY
mc ls test/kb-documents
```

**Solutions**:
- Verify access key and secret key are correct
- Check bucket permissions (must have read access)
- Ensure bucket exists: `mc mb test/kb-documents`

### Error: "Bucket not found (404)"

**Symptoms**: S3 download fails saying bucket doesn't exist

**Solutions**:
```bash
# List all buckets
mc ls test/

# Create bucket if missing
mc mb test/kb-documents

# Verify files exist
mc ls test/kb-documents/kb/
```

---

## Service Connection Failures

### Error: "Connection refused: doc-ingest-service:8001"

**Symptoms**: `ingest-document-batch` step fails connecting to service

**Diagnosis**:
```bash
# Check service is running
oc get pods -l app=doc-ingest-service -n <namespace>

# Check service exists
oc get svc doc-ingest-service -n <namespace>

# View service logs
oc logs -f deployment/doc-ingest-service -n <namespace>
```

**Solutions**:
```bash
# Restart service if crashed
oc rollout restart deployment/doc-ingest-service -n <namespace>

# Scale up if scaled down
oc scale deployment/doc-ingest-service --replicas=1 -n <namespace>

# Verify service URL format
# Should be: http://SERVICE_NAME.NAMESPACE.svc.cluster.local:PORT
service_url: http://doc-ingest-service.<namespace>.svc.cluster.local:8001
```

### Error: "Wrong namespace in service URL"

**Symptoms**: Service connection fails even though pod is running

**Solutions**:
```bash
# Find correct namespace
oc get deploy doc-ingest-service --all-namespaces

# Update parameter in pipeline run
# If service is in namespace "my-namespace":
service_url: http://doc-ingest-service.my-namespace.svc.cluster.local:8001
```

### Error: "Gateway timeout (504)"

**Symptoms**: Some large files timeout during ingestion

**Solutions**:
1. **Increase timeout in pipeline**:
   Edit `pipeline.py` line ~158:
   ```python
   timeout=600  # Increase from 300 to 600 seconds
   ```
   Recompile: `python pipeline.py`

2. **Reduce batch size**:
   ```yaml
   batch_size: 5  # Process fewer files at once
   ```

3. **Process large files separately**:
   ```bash
   # Upload large files to different S3 prefix
   mc cp large-files/ test/kb-documents/large/

   # Run separate pipeline with longer timeout
   ```

---

## Database Issues

### Error: "Could not connect to PostgreSQL"

**Symptoms**: `verify-ingestion` step fails with connection error

**Diagnosis**:
```bash
# Check PostgreSQL is running
oc get pods -l app=postgres-pgvector -n <namespace>

# Check service
oc get svc postgres-pgvector -n <namespace>

# Test connection
oc run psql-test --image=postgres:15 --rm -it -n <namespace> -- \
  psql -h postgres-pgvector -U raguser -d ragdb -c "SELECT 1;"
```

**Solutions**:
```bash
# Restart PostgreSQL if needed
oc rollout restart statefulset/postgres-pgvector -n <namespace>

# Verify password is correct
oc get secret postgres-pgvector-secret -n <namespace> \
  -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d
```

### Error: "Authentication failed for user"

**Symptoms**: Database password is incorrect

**Solutions**:
```bash
# Get correct password from secret
DB_PASSWORD=$(oc get secret postgres-pgvector-secret -n <namespace> \
  -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)

# Use this password in pipeline parameters
echo "Password: ${DB_PASSWORD}"
```

### Error: "Too many connections"

**Symptoms**: Database rejects connections during ingestion

**Solutions**:
```bash
# Check current connections
oc exec deployment/postgres-pgvector -n <namespace> -- \
  psql -U raguser -d ragdb -c "SELECT count(*) FROM pg_stat_activity;"

# Increase max_connections in PostgreSQL config
# Or reduce batch_size to fewer concurrent requests
```

---

## Document Processing Failures

### Error: "UTF-8 encoding error"

**Symptoms**: Documents fail with "invalid byte sequence for encoding UTF8: 0x00"

**Status**: ✅ **FIXED** - The doc-ingest-service now includes `clean_text()` function

**Verification**:
```bash
# Check service has encoding fixes
oc logs deployment/doc-ingest-service -n <namespace> | grep "clean_text"

# If not present, rebuild service with latest code
```

### Error: "Document parsing failed"

**Symptoms**: Specific documents fail with parsing errors

**Solutions**:
1. Check document format is supported (.md, .txt, .html, .pdf, .docx)
2. Verify file is not corrupted:
   ```bash
   # Download and open manually
   mc cp test/kb-documents/kb/problem-file.md .
   file problem-file.md
   ```

### Error: "No chunks created"

**Symptoms**: Document processes but creates 0 chunks

**Causes**:
- Empty document
- Document all whitespace
- Parsing failed silently

**Solutions**:
```bash
# Check document content
mc cat test/kb-documents/kb/empty-doc.md

# Check service logs for detailed error
oc logs deployment/doc-ingest-service -n <namespace> | grep "empty-doc.md"
```

---

## Performance Problems

### Issue: Pipeline runs very slowly

**Symptoms**: Processing takes >10 minutes for <100 documents

**Diagnosis**:
```bash
# Check pod resources
oc describe pod -l component=pipeline -n <data-science-project>

# Check service resources
oc describe deployment doc-ingest-service -n <namespace>
```

**Solutions**:
1. **Increase service resources**:
   ```bash
   oc set resources deployment/doc-ingest-service -n <namespace> \
     --limits=cpu=2,memory=4Gi \
     --requests=cpu=1,memory=2Gi
   ```

2. **Increase batch size** (if service can handle it):
   ```yaml
   batch_size: 20  # Process more documents per batch
   ```

3. **Check embedding API latency**:
   ```bash
   # Nomic API should respond in <500ms
   oc logs deployment/doc-ingest-service -n <namespace> | grep "embedding"
   ```

### Issue: Out of memory errors

**Symptoms**: Pipeline pod or service crashes with OOM

**Solutions**:
```bash
# Increase pipeline pod memory
# (This requires modifying pipeline component resources)

# Reduce batch size to process fewer files at once
batch_size: 5

# Check for memory leaks in service
oc adm top pod -n <namespace>
```

---

## Debug Checklist

When troubleshooting, run through this checklist:

- [ ] All pods running: `oc get pods -n <namespace>`
- [ ] Services accessible: `oc get svc -n <namespace>`
- [ ] Minio has documents: `mc ls test/kb-documents/kb/`
- [ ] Credentials are correct (S3 and DB)
- [ ] Service URLs use cluster-internal format
- [ ] Pipeline YAML compiled successfully
- [ ] Pipeline logs show detailed errors
- [ ] Service health endpoints respond

## Getting Help

### View Pipeline Logs

In OpenShift AI console:
1. Go to Pipelines → Runs
2. Click on your pipeline run
3. Click on failed step
4. View logs in right panel

### View Service Logs

```bash
# doc-ingest-service logs
oc logs -f deployment/doc-ingest-service -n <namespace> --tail=100

# PostgreSQL logs
oc logs -f statefulset/postgres-pgvector -n <namespace> --tail=100

# Minio logs
oc logs -f deployment/minio -n <namespace> --tail=100
```

### Export Pipeline Logs

```bash
# Export all logs for debugging
oc logs deployment/doc-ingest-service -n <namespace> > service.log

# Search for specific error
grep -i "error\|exception\|fail" service.log
```

### Common Log Patterns

**Successful ingestion**:
```
✅ document.md: 5 chunks
Processing chunk 0/5
Generating embedding...
Storing in database...
Document ingested successfully
```

**Failed ingestion**:
```
❌ document.md: HTTP 500
Error: invalid byte sequence for encoding "UTF8": 0x00
```

**Timeout**:
```
❌ large-doc.html: HTTP 504
Error: Gateway Time-out
```

---

## Contact

For issues not covered in this guide:
- Review pipeline code in `pipeline.py`
- Check OpenShift AI documentation
- Review service logs for detailed error messages
