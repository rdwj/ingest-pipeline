# Test MinIO S3 Access

This test job will help diagnose MinIO connectivity and credential issues.

## Run the Test

**On the customer cluster:**

```bash
# 1. Apply the test job
oc apply -f test-minio-job.yaml -n servicenow-ai-poc

# 2. Wait for it to complete
oc get jobs -n servicenow-ai-poc -w

# 3. Get the pod name
POD=$(oc get pods -n servicenow-ai-poc -l job-name=test-minio-access -o jsonpath='{.items[0].metadata.name}')

# 4. View the logs
oc logs $POD -n servicenow-ai-poc
```

## What the Test Does

1. **Test S3 Connection** - Verifies boto3 can connect to MinIO
2. **List Buckets** - Shows all available buckets
3. **Check Bucket Exists** - Confirms 'kb-documents' is accessible
4. **List Objects** - Shows all files in 'data/' prefix
5. **Test Download** - Attempts to download one file

## Troubleshooting Different Credentials

### Option 1: Try default credentials (already configured)
The job is configured to use `minioadmin/minioadmin`

### Option 2: Try credentials from secret

Edit `test-minio-job.yaml` and comment/uncomment the env sections:

```yaml
# Comment out these lines:
# - name: MINIO_ACCESS_KEY
#   value: "minioadmin"
# - name: MINIO_SECRET_KEY
#   value: "minioadmin"

# Uncomment these lines:
- name: MINIO_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: minio-credentials
      key: MINIO_ACCESS_KEY
- name: MINIO_SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: minio-credentials
      key: MINIO_SECRET_KEY
```

### Option 3: Try different credentials directly

Edit the `value:` fields in the YAML:

```yaml
- name: MINIO_ACCESS_KEY
  value: "YOUR_ACCESS_KEY_HERE"
- name: MINIO_SECRET_KEY
  value: "YOUR_SECRET_KEY_HERE"
```

## Expected Output (Success)

```
Testing MinIO S3 Access
============================================================
Endpoint: YOUR ENDPOINT
Bucket: kb-documents
Prefix: data/
Access Key: mini...dmin
============================================================

Creating S3 client...
SUCCESS: S3 client created

Test 1: Listing all buckets...
SUCCESS: Found 1 buckets:
  - kb-documents

Test 2: Checking if bucket 'kb-documents' exists...
SUCCESS: Bucket 'kb-documents' exists

Test 3: Listing objects in 'kb-documents/data/'...
  data/file1.md (0.05 MB)
  data/file2.md (0.03 MB)
  ...

SUCCESS: Found 90 objects in 'kb-documents/data/'

Test 4: Testing download capability...
Attempting to download: data/file1.md
SUCCESS: Downloaded 52341 bytes

============================================================
All tests passed! MinIO S3 access is working correctly.
============================================================
```

## Common Errors

### "Access Denied"
- Wrong access key or secret key
- User doesn't have permission to the bucket

### "No such bucket"
- Bucket name is wrong
- Check: `oc get pvc` - MinIO might be using a different bucket

### "Connection refused" or "timeout"
- MinIO endpoint URL is wrong
- Network policy blocking traffic
- MinIO not running

### "No objects found"
- Files uploaded to wrong prefix
- Prefix should be `data/` (with trailing slash) not `data`

## Clean Up

```bash
# Delete the job when done
oc delete job test-minio-access -n servicenow-ai-poc
oc delete configmap test-minio-script -n servicenow-ai-poc
```

## Next Steps

Once the test passes:
1. Use the same credentials in your pipeline run
2. Verify the endpoint URL matches exactly
3. Verify the prefix matches what the test found
