# Service Diagnostics

Run this notebook FIRST to verify all services are up and accessible.

```python
# Configuration
NAMESPACE = "servicenow-ai-poc"
DB_HOST = "postgres-pgvector.servicenow-ai-poc.svc.cluster.local"
DB_PORT = "5432"
SERVICE_URL = "http://vector-search-service.servicenow-ai-poc.svc.cluster.local:8000"
```

## Test 1: DNS Resolution

```python
import socket

# Test database DNS
print("Testing DNS resolution...\n")

services_to_test = [
    ("PostgreSQL", DB_HOST, int(DB_PORT)),
    ("Vector Search", "vector-search-service.servicenow-ai-poc.svc.cluster.local", 8000),
]

for name, host, port in services_to_test:
    print(f"Testing {name}: {host}:{port}")
    try:
        # Try DNS resolution
        ip = socket.gethostbyname(host)
        print(f"  DNS: SUCCESS - Resolved to {ip}")
      
        # Try TCP connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
      
        if result == 0:
            print(f"  TCP:  SUCCESS - Port {port} is open")
        else:
            print(f"  TCP:  FAILED - Port {port} is closed or filtered")
          
    except socket.gaierror as e:
        print(f"  DNS:  FAILED - {e}")
    except Exception as e:
        print(f"  ERROR: {e}")
    print()
```

    Testing DNS resolution...

    Testing PostgreSQL: postgres-pgvector.servicenow-ai-poc.svc.cluster.local:5432
      DNS: SUCCESS - Resolved to 172.30.131.133
      TCP:  SUCCESS - Port 5432 is open

    Testing Vector Search: vector-search-service.servicenow-ai-poc.svc.cluster.local:8000
      DNS: SUCCESS - Resolved to 172.30.80.53
      TCP:  SUCCESS - Port 8000 is open

## Test 2: Check PostgreSQL (if DNS works)

```python
try:
    import psycopg2
  
    DB_USER = "raguser"
    DB_PASSWORD = "0x8eight*"  # UPDATE THIS
    DB_NAME = "ragdb"
  
    print(f"Connecting to PostgreSQL: {DB_HOST}:{DB_PORT}/{DB_NAME}")
  
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connect_timeout=10
    )
  
    cur = conn.cursor()
    cur.execute("SELECT version()")
    version = cur.fetchone()[0]
  
    print(f"SUCCESS: Connected to PostgreSQL")
    print(f"Version: {version}")
  
    # Check for required tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cur.fetchall()]
  
    print(f"\nTables in database:")
    for table in tables:
        print(f"  - {table}")
  
    required_tables = ['collections', 'documents', 'embeddings']
    missing = [t for t in required_tables if t not in tables]
  
    if missing:
        print(f"\nWARNING: Missing required tables: {missing}")
    else:
        print(f"\nSUCCESS: All required tables exist")
  
    cur.close()
    conn.close()
  
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
```

    Connecting to PostgreSQL: postgres-pgvector.servicenow-ai-poc.svc.cluster.local:5432/ragdb
    SUCCESS: Connected to PostgreSQL
    Version: PostgreSQL 16.10 (Debian 16.10-1.pgdg12+1) on x86_64-pc-linux-gnu, compiled by gcc (Debian 12.2.0-14+deb12u1) 12.2.0, 64-bit

    Tables in database:
      - collections
      - document_chunks
      - documentation
      - documents
      - embeddings

    SUCCESS: All required tables exist

## Test 3: Check Vector Search Service Health

```python
import requests

print(f"Testing vector-search-service at: {SERVICE_URL}")

try:
    # Test CORRECT health endpoint (with /api/v1 prefix)
    response = requests.get(f"{SERVICE_URL}/api/v1/health", timeout=10)
    print(f"\nHealth check status: {response.status_code}")
    print(f"Response: {response.text}")
  
    if response.status_code == 200:
        print("SUCCESS: Service is up")
        # Try to parse JSON response
        try:
            health_data = response.json()
            print(f"Health data: {health_data}")
        except:
            pass
    else:
        print(f"WARNING: Unexpected status code")
      
except requests.exceptions.ConnectionError as e:
    print(f"FAILED: Cannot connect to service")
    print(f"Error: {e}")
    print("\nPossible causes:")
    print("  1. Service is not running")
    print("  2. Service crashed during startup")
    print("  3. Service can't connect to database")
  
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
```

    Testing vector-search-service at: http://vector-search-service.servicenow-ai-poc.svc.cluster.local:8000

    Health check status: 200
    Response: {"status":"healthy","timestamp":"2025-11-14T04:05:26.249449","version":"1.0.0","service":"vector-search-service","uptime":0.001119,"components":{"database":{"status":"healthy","message":"Database connection OK","response_time_ms":1},"response_time_seconds":0.001119}}
    SUCCESS: Service is up
    Health data: {'status': 'healthy', 'timestamp': '2025-11-14T04:05:26.249449', 'version': '1.0.0', 'service': 'vector-search-service', 'uptime': 0.001119, 'components': {'database': {'status': 'healthy', 'message': 'Database connection OK', 'response_time_ms': 1}, 'response_time_seconds': 0.001119}}

## Test 4: Check if collections exist

```python
import requests

try:
    response = requests.get(f"{SERVICE_URL}/api/v1/collections", timeout=10)
  
    if response.status_code == 200:
        collections = response.json()
        print(f"Collections: {collections}")
    else:
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
      
except Exception as e:
    print(f"Cannot list collections: {e}")
```

    Status: 405
    Response: {"detail":"Method Not Allowed"}

## Test 5: Use kubectl/oc to check pods (if available)

```python
import subprocess

# Try to run oc command
try:
    result = subprocess.run(
        ["oc", "get", "pods", "-n", NAMESPACE],
        capture_output=True,
        text=True,
        timeout=10
    )
  
    if result.returncode == 0:
        print("Pods in namespace:")
        print(result.stdout)
    else:
        print("oc command failed or not available")
        print(result.stderr)
      
except FileNotFoundError:
    print("oc/kubectl command not available in this environment")
except Exception as e:
    print(f"Error: {e}")
```

    Pods in namespace:
    NAME                                                                   READY   STATUS      RESTARTS      AGE
    ai-poc-0                                                               2/2     Running     0             72m
    doc-ingest-service-587c66f6-brbdp                                      1/1     Running     0             9h
    document-ingestion-pipeline-4g9jc-system-container-driver-1536953863   0/2     Completed   0             6h3m
    document-ingestion-pipeline-4g9jc-system-container-driver-2271643386   0/2     Completed   0             6h2m
    document-ingestion-pipeline-4g9jc-system-container-driver-2759241689   0/2     Completed   0             6h2m
    document-ingestion-pipeline-4g9jc-system-container-driver-2807402198   0/2     Completed   0             6h2m
    document-ingestion-pipeline-4g9jc-system-dag-driver-1356581177         0/2     Completed   0             6h3m
    document-ingestion-pipeline-4g9jc-system-dag-driver-3100529394         0/2     Completed   0             6h3m
    document-ingestion-pipeline-9sbb8-system-container-driver-2601906468   0/2     Completed   0             8h
    document-ingestion-pipeline-9sbb8-system-container-driver-3641608698   0/2     Completed   0             8h
    document-ingestion-pipeline-9sbb8-system-container-driver-3750591811   0/2     Completed   0             8h
    document-ingestion-pipeline-9sbb8-system-container-driver-3946126897   0/2     Completed   0             8h
    document-ingestion-pipeline-9sbb8-system-container-impl-1779384554     0/2     Error       0             8h
    document-ingestion-pipeline-9sbb8-system-container-impl-1802388997     0/2     Error       0             8h
    document-ingestion-pipeline-9sbb8-system-dag-driver-3067024733         0/2     Completed   0             8h
    document-ingestion-pipeline-9sbb8-system-dag-driver-3894615962         0/2     Completed   0             8h
    document-ingestion-pipeline-bnrqz-system-container-driver-2181216904   0/2     Completed   0             8h
    document-ingestion-pipeline-bnrqz-system-container-driver-2340098587   0/2     Completed   0             8h
    document-ingestion-pipeline-bnrqz-system-container-driver-2514838709   0/2     Completed   0             8h
    document-ingestion-pipeline-bnrqz-system-container-driver-612233868    0/2     Completed   0             8h
    document-ingestion-pipeline-bnrqz-system-container-impl-2310835966     0/2     Completed   0             8h
    document-ingestion-pipeline-bnrqz-system-container-impl-3787046765     0/2     Error       0             8h
    document-ingestion-pipeline-bnrqz-system-dag-driver-1549242827         0/2     Completed   0             8h
    document-ingestion-pipeline-bnrqz-system-dag-driver-866623116          0/2     Completed   0             8h
    document-ingestion-pipeline-kfz7j-system-container-driver-1221572676   0/2     Completed   0             8h
    document-ingestion-pipeline-kfz7j-system-container-driver-4077636305   0/2     Completed   0             8h
    document-ingestion-pipeline-kfz7j-system-container-driver-4249650714   0/2     Completed   0             8h
    document-ingestion-pipeline-kfz7j-system-container-driver-833457763    0/2     Completed   0             8h
    document-ingestion-pipeline-kfz7j-system-container-impl-2443947813     0/2     Error       0             8h
    document-ingestion-pipeline-kfz7j-system-container-impl-3448517130     0/2     Error       0             8h
    document-ingestion-pipeline-kfz7j-system-dag-driver-1378706874         0/2     Completed   0             8h
    document-ingestion-pipeline-kfz7j-system-dag-driver-3200008829         0/2     Completed   0             8h
    document-ingestion-pipeline-mgpfv-system-container-driver-2058975841   0/2     Completed   0             6h9m
    document-ingestion-pipeline-mgpfv-system-container-driver-2164359667   0/2     Completed   0             6h9m
    document-ingestion-pipeline-mgpfv-system-container-driver-2516303924   0/2     Completed   0             6h9m
    document-ingestion-pipeline-mgpfv-system-container-driver-3247826154   0/2     Completed   0             6h9m
    document-ingestion-pipeline-mgpfv-system-dag-driver-449253610          0/2     Completed   0             6h9m
    document-ingestion-pipeline-mgpfv-system-dag-driver-707995373          0/2     Completed   0             6h9m
    document-ingestion-pipeline-qmggd-system-container-driver-2082026445   0/2     Completed   0             144m
    document-ingestion-pipeline-qmggd-system-container-driver-2215038023   0/2     Completed   0             144m
    document-ingestion-pipeline-qmggd-system-container-driver-612687800    0/2     Completed   0             144m
    document-ingestion-pipeline-qmggd-system-container-driver-729955310    0/2     Completed   0             144m
    document-ingestion-pipeline-qmggd-system-dag-driver-2561816417         0/2     Completed   0             144m
    document-ingestion-pipeline-qmggd-system-dag-driver-3567376958         0/2     Completed   0             144m
    document-ingestion-pipeline-szqgt-system-container-driver-2183277301   0/2     Completed   0             7h13m
    document-ingestion-pipeline-szqgt-system-container-driver-2225480755   0/2     Completed   0             7h14m
    document-ingestion-pipeline-szqgt-system-container-driver-632836102    0/2     Completed   0             7h13m
    document-ingestion-pipeline-szqgt-system-container-driver-647065738    0/2     Completed   0             7h13m
    document-ingestion-pipeline-szqgt-system-container-impl-1372119987     0/2     Completed   0             7h13m
    document-ingestion-pipeline-szqgt-system-dag-driver-1562604654         0/2     Completed   0             7h14m
    document-ingestion-pipeline-szqgt-system-dag-driver-2553406981         0/2     Completed   0             7h14m
    document-ingestion-pipeline-szssb-system-container-driver-1051677951   0/2     Completed   0             107m
    document-ingestion-pipeline-szssb-system-container-driver-4020175102   0/2     Completed   0             106m
    document-ingestion-pipeline-szssb-system-container-driver-4032523121   0/2     Completed   0             106m
    document-ingestion-pipeline-szssb-system-container-driver-903402578    0/2     Completed   0             107m
    document-ingestion-pipeline-szssb-system-container-impl-1059536764     0/2     Completed   0             106m
    document-ingestion-pipeline-szssb-system-container-impl-134966097      0/2     Completed   0             107m
    document-ingestion-pipeline-szssb-system-container-impl-297837375      0/2     Completed   0             105m
    document-ingestion-pipeline-szssb-system-container-impl-3904315736     0/2     Completed   0             106m
    document-ingestion-pipeline-szssb-system-dag-driver-49759658           0/2     Completed   0             107m
    document-ingestion-pipeline-szssb-system-dag-driver-570490929          0/2     Completed   0             107m
    ds-pipeline-dspa-6f479b69dd-kmsn9                                      2/2     Running     3 (9h ago)    10h
    ds-pipeline-metadata-envoy-dspa-6c8475dfd6-rkg7s                       2/2     Running     0             9h
    ds-pipeline-metadata-grpc-dspa-f544976d5-kqfmk                         1/1     Running     2 (9h ago)    9h
    ds-pipeline-persistenceagent-dspa-5d4d768745-8bq9f                     1/1     Running     0             9h
    ds-pipeline-scheduledworkflow-dspa-5486fb9d65-jg568                    1/1     Running     0             9h
    ds-pipeline-workflow-controller-dspa-6c449b6947-nbjdc                  1/1     Running     0             9h
    mariadb-dspa-5697f9b64d-n98wl                                          1/1     Running     0             9h
    neo4j-0                                                                1/1     Running     0             9h
    postgres-pgvector-0                                                    1/1     Running     0             9h
    redis-0                                                                1/1     Running     0             9h
    test-minio-access-c2mrt                                                0/1     Completed   0             8h
    vector-search-service-6d7957f84c-7shbb                                 1/1     Running     1 (19m ago)   9h

## Summary

Based on the tests above:

**If DNS fails**: The database service doesn't exist or is in a different namespace

**If DNS works but TCP connection fails**: The service exists but isn't listening on that port

**If PostgreSQL connection fails**: Wrong credentials, or database not fully initialized

**If vector-search health check fails**: Service crashed during startup (usually due to database connection issues)

**Next steps:**

1. Fix any DNS/network issues first
2. Ensure PostgreSQL is running and has the correct schema
3. Restart vector-search-service if needed
4. Then try the ingestion notebook again

## Test 6: Check Pod Logs

This will show us what error caused the service to crash.

```python
import subprocess

# Get logs from the PREVIOUS container (the one that crashed)
print("Getting logs from crashed container instance...")
print("=" * 80)

try:
    # First try to get previous container logs (shows crash)
    result = subprocess.run(
        ["oc", "logs", "deployment/vector-search-service", "-n", NAMESPACE, "--previous", "--tail=200"],
        capture_output=True,
        text=True,
        timeout=30
    )
  
    if result.returncode == 0:
        print("PREVIOUS CONTAINER LOGS (crashed instance):")
        print(result.stdout)
        print("=" * 80)
      
        # Look for critical errors
        if "oom" in result.stdout.lower() or "memory" in result.stdout.lower():
            print("\n⚠️  MEMORY ISSUE DETECTED")
        if "error" in result.stdout.lower() or "exception" in result.stdout.lower():
            print("\n⚠️  ERRORS/EXCEPTIONS FOUND")
    else:
        print("Could not get previous container logs (may not exist if no restart)")
        print(result.stderr)
        print()
      
        # Fallback to current logs
        print("Trying current container logs...")
        result2 = subprocess.run(
            ["oc", "logs", "deployment/vector-search-service", "-n", NAMESPACE, "--tail=100"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result2.returncode == 0:
            print("CURRENT CONTAINER LOGS:")
            print(result2.stdout)
        else:
            print("Failed to get logs:", result2.stderr)
      
except FileNotFoundError:
    print("oc command not available in this environment")
except Exception as e:
    print(f"Error getting logs: {e}")

print("\n" + "=" * 80)

# Also check for OOMKilled events
print("\nChecking for OOM/crash events...")
try:
    result = subprocess.run(
        ["oc", "get", "events", "-n", NAMESPACE, "--sort-by=.lastTimestamp"],
        capture_output=True,
        text=True,
        timeout=30
    )
  
    if result.returncode == 0:
        lines = result.stdout.split('\n')
        # Filter for relevant events
        for line in lines:
            if any(keyword in line.lower() for keyword in ['oom', 'killed', 'error', 'crash', 'restart', 'vector-search']):
                print(line)
    else:
        print("Could not get events")
      
except Exception as e:
    print(f"Error getting events: {e}")
```

    Getting logs from crashed container instance...
    ================================================================================
    Could not get previous container logs (may not exist if no restart)
    Error from server (Forbidden): deployments.apps "vector-search-service" is forbidden: User "system:serviceaccount:servicenow-ai-poc:ai-poc" cannot get resource "deployments" in API group "apps" in the namespace "servicenow-ai-poc"

    Trying current container logs...
    Failed to get logs: Error from server (Forbidden): deployments.apps "vector-search-service" is forbidden: User "system:serviceaccount:servicenow-ai-poc:ai-poc" cannot get resource "deployments" in API group "apps" in the namespace "servicenow-ai-poc"

    ================================================================================

    Checking for OOM/crash events...
    Could not get events
