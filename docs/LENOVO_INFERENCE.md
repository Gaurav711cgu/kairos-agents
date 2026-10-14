# Optional Lenovo inference

Hardware provided: Windows, 8 GB RAM, RTX 3050 with 4 GB VRAM. This machine has not been connected or tested in this session. The Mac profile remains the working fallback. No evaluation may switch profiles halfway through an investigation.

Official Qwen2.5-Coder-3B-Instruct Q4_K_M and llama.cpp b11552 CUDA 12.4 assets are pinned in `evidence/build004/lenovo-profile.json`. The model is 2,104,932,800 bytes. CUDA libraries and executable archives add about 657 MB before extraction. Driver compatibility, actual VRAM use and speed remain unmeasured.

Copy the PowerShell script and profile JSON to the Lenovo. Pass the copied JSON path explicitly if not preserving the repository layout:

```powershell
powershell -File .\lenovo_inference.ps1 -Mode Prepare -ProfilePath .\lenovo-profile.json
powershell -File .\lenovo_inference.ps1 -Mode Inspect -ProfilePath .\lenovo-profile.json
powershell -File .\lenovo_inference.ps1 -Mode Serve -ProfilePath .\lenovo-profile.json
```

Preparation downloads official assets, verifies their published SHA-256 values and records hashes of extracted files. Existing mismatched files and partial downloads are preserved and cause refusal. Inference binds only to Lenovo loopback. Project-owned inference files have a 6 GiB ceiling and a 4 GiB free-space reserve. The storage guard does not account for unrelated Windows files or establish a filesystem quota.

Use Windows OpenSSH Server with a dedicated account and key authentication. Confirm the Lenovo SSH host fingerprint locally before accepting it on the Mac. Keep the SSH service restricted to the private network. Do not open port 8130 in Windows Firewall or on the router. From the Mac:

```sh
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -L 127.0.0.1:8132:127.0.0.1:8130 USER@LENOVO_PRIVATE_ADDRESS
```

Set `KAIROS_INVESTIGATION_MODEL_URL=http://127.0.0.1:8132` and an explicit candidate runtime manifest for a separate pilot. A disconnected tunnel produces an unknown dispatch if inference may have started; never resend it to the Mac. Do not use a reverse tunnel, public listener or public hosting.

Before selecting the candidate, capture the actual driver/runtime version, GPU memory, free storage, 4096-context rendering, nested schema enforcement, maximum-output behavior, ten sequential inference requests and a development-case repair pilot. Compare verified repairs first, invalid responses second and elapsed time third. Freeze the chosen manifest and generation settings. A successful server startup alone does not establish memory stability or better repairs.

Sources: [official model](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF), [official CUDA build guidance](https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md), [pinned runtime release](https://github.com/ggml-org/llama.cpp/releases/tag/b11552).
