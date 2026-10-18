#!/usr/bin/env bash
# ==============================================================================
# UTM Linux SWE-bench Execution Harness
# Run this script INSIDE your UTM Linux virtual machine to execute real
# dockerized SWE-bench test suites with zero risk to your host macOS SSD.
# ==============================================================================
set -euo pipefail

INSTANCE_ID="${1:-pytest-dev__pytest-5221}"
OUTPUT_DIR="${2:-./swebench_eval_output}"
PREDICTIONS_PATH="${3:-./predictions.json}"

echo "================================================================="
echo " UTM Linux SWE-bench Evaluation Harness"
echo " Target Instance:   ${INSTANCE_ID}"
echo " Output Directory:  ${OUTPUT_DIR}"
echo " Predictions Path:  ${PREDICTIONS_PATH}"
echo "================================================================="

# Trap cleanup on interrupt or error
cleanup() {
    local exit_code=$?
    if [ ${exit_code} -ne 0 ]; then
        echo "[!] Runner exited with error code ${exit_code}."
    fi
}
trap cleanup EXIT

# 1. Check prerequisites
if ! command -v docker &>/dev/null; then
    echo "[!] Docker is not installed in this Linux VM."
    echo "    Install with: sudo apt-get update && sudo apt-get install -y docker.io"
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "[!] Docker daemon is not running or accessible without sudo."
    echo "    Ensure docker daemon is started and current user is in the docker group:"
    echo "    sudo systemctl start docker && sudo usermod -aG docker \$USER && newgrp docker"
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "[!] Python 3 is required."
    exit 1
fi

mkdir -p "${OUTPUT_DIR}"

# 2. Check or scaffold predictions file
if [ ! -f "${PREDICTIONS_PATH}" ]; then
    echo "[*] Predictions file not found at '${PREDICTIONS_PATH}'. Generating template..."
    cat <<EOF > "${PREDICTIONS_PATH}"
[
  {
    "instance_id": "${INSTANCE_ID}",
    "model_name_or_path": "kairos-14b-adapter-v4",
    "model_patch": ""
  }
]
EOF
    echo "    Created template at '${PREDICTIONS_PATH}'. Provide a non-empty 'model_patch' to test a fix."
fi

# 3. Install SWE-bench runner if not present
if ! python3 -c "import swebench" &>/dev/null; then
    echo "[*] Installing official SWE-bench evaluation harness..."
    pip3 install --quiet swebench
fi

# 4. Execute official SWE-bench runner with cache bounding
RUN_ID="utm_eval_$(date +%s)"
echo "[*] Pulling evaluation container and running regression test assertions..."
python3 -m swebench.harness.run_evaluation \
    --dataset_name princeton-nlp/SWE-bench_Lite \
    --instance_ids "${INSTANCE_ID}" \
    --predictions_path "${PREDICTIONS_PATH}" \
    --max_workers 1 \
    --run_id "${RUN_ID}" \
    --cache_level instance \
    --output_dir "${OUTPUT_DIR}"

echo "[✓] Evaluation complete. Results sealed in: ${OUTPUT_DIR}"
if [ -f "${OUTPUT_DIR}/${RUN_ID}.json" ]; then
    echo "[*] Evaluation summary:"
    cat "${OUTPUT_DIR}/${RUN_ID}.json"
fi
