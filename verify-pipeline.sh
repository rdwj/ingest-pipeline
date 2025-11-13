#!/bin/bash
# Helper script to compile and verify the pipeline

set -e

echo "🔧 KubeFlow Pipeline Verification"
echo "=================================="

# Check Python version
echo "Checking Python version..."
python --version

# Check if kfp is installed
echo ""
echo "Checking KubeFlow SDK..."
if python -c "import kfp" 2>/dev/null; then
    python -c "import kfp; print(f'✅ kfp version: {kfp.__version__}')"
else
    echo "❌ kfp not found. Installing..."
    pip install -r requirements.txt
fi

# Compile pipeline
echo ""
echo "Compiling pipeline..."
python pipeline.py

# Check if YAML was created
if [ -f "doc_ingestion_pipeline.yaml" ]; then
    SIZE=$(wc -c < doc_ingestion_pipeline.yaml)
    echo "✅ Pipeline compiled successfully"
    echo "   File: doc_ingestion_pipeline.yaml"
    echo "   Size: ${SIZE} bytes"
else
    echo "❌ Pipeline compilation failed"
    exit 1
fi

# Validate YAML structure
echo ""
echo "Validating YAML structure..."
if python -c "import yaml; yaml.safe_load(open('doc_ingestion_pipeline.yaml'))" 2>/dev/null; then
    echo "✅ YAML structure is valid"
else
    echo "❌ YAML structure is invalid"
    exit 1
fi

# Count pipeline components
echo ""
echo "Pipeline components:"
COMPONENT_COUNT=$(grep -c "name: " doc_ingestion_pipeline.yaml || echo "0")
echo "   Total components: ${COMPONENT_COUNT}"

# Show pipeline structure
echo ""
echo "Pipeline structure:"
grep "  name: " doc_ingestion_pipeline.yaml | sed 's/^/   - /'

echo ""
echo "✅ Pipeline is ready for upload to OpenShift AI"
echo ""
echo "Next steps:"
echo "1. Open OpenShift AI console"
echo "2. Navigate to your Data Science Project"
echo "3. Go to Pipelines → Import pipeline"
echo "4. Upload: doc_ingestion_pipeline.yaml"
echo "5. Configure parameters from example-parameters.yaml"
