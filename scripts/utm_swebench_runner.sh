#!/usr/bin/env bash
# ==============================================================================
# UTM Linux SWE-bench Execution Harness
# Run this script INSIDE your UTM Linux virtual machine to execute real
# dockerized SWE-bench test suites with zero risk to your host macOS SSD.
# ==============================================================================
set -euo pipefail

INSTANCE_ID="${1:-pytest-dev__pytest-5221}"
OUTPUT_DIR="${2:-./swebench_eval_output}"

echo "================================================================="
echo " UTM Linux SWE-bench Evaluation Harness"
echo " Target Instance: ${INSTANCE_ID}"
echo " Output Directory: ${OUTPUT_DIR}"
echo "================================================================="

# 1. Check prerequisites
if ! command -v docker &>/dev/null; then
    echo "[!] Docker is not installed in this Linux VM."
    echo "    Install with: sudo apt-get update && sudo apt-get install -y docker.io"
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "[!] Python 3 is required."
    exit 1
fi

mkdir -p "${OUTPUT_DIR}"

# 2. Install SWE-bench runner if not present
if ! python3 -c "import swebench" &>/dev/null; then
    echo "[*] Installing official SWE-bench evaluation harness..."
    pip3 install --quiet swebench
fi

# 3. Execute official SWE-bench runner
echo "[*] Pulling evaluation container and running regression test assertions..."
python3 -m swebench.harness.run_evaluation \
    --dataset_name princeton-nlp/SWE-bench_Lite \
    --instance_ids "${INSTANCE_ID}" \
    --predictions_path ./predictions.json \
    --max_workers 1 \
    --run_id "utm_eval_$(date +%s)" \
    --output_dir "${OUTPUT_DIR}"

echo "[✓] Evaluation complete. Results sealed in: ${OUTPUT_DIR}"
