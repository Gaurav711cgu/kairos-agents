<# Pinned, optional Windows inference. No public listener. No paid API.
   Copy this script and evidence/build004/lenovo-profile.json to the Lenovo.
   Prepare and Serve are separate so hardware failures never trigger fallback.
#>
param(
  [Parameter(Mandatory=$true)][ValidateSet('Prepare','Serve','Inspect')][string]$Mode,
  [string]$ProfilePath = "$PSScriptRoot\..\evidence\build004\lenovo-profile.json",
  [string]$RuntimeRoot = "$env:LOCALAPPDATA\KairosInference-build004"
)
$ErrorActionPreference='Stop'
$modelProfile=Get-Content -Raw $ProfilePath | ConvertFrom-Json
$cap=6GB;$reserve=4GB
New-Item -ItemType Directory -Force $RuntimeRoot | Out-Null
function Assert-Storage([long]$Additional=0) {
  $owned=(Get-ChildItem -Recurse -File $RuntimeRoot | Measure-Object -Property Length -Sum).Sum
  if($null -eq $owned){$owned=0}
  $drive=Get-PSDrive -Name ([IO.Path]::GetPathRoot($RuntimeRoot).TrimEnd(':\'))
  if(($owned+$Additional) -gt $cap){throw 'Project-owned inference storage would exceed 6 GiB.'}
  if(($drive.Free-$Additional) -lt $reserve){throw 'Less than 4 GiB would remain free.'}
  return @{owned_bytes=$owned;free_bytes=$drive.Free}
}
function Fetch-Pinned([string]$Url,[string]$Path,[string]$Digest,[long]$Bytes) {
  if(Test-Path $Path) {
    if((Get-FileHash -Algorithm SHA256 $Path).Hash.ToLower() -ne $Digest){throw "Existing file differs; preserved: $Path"}
    return
  }
  Assert-Storage $Bytes | Out-Null
  $partial="$Path.partial"
  if(Test-Path $partial){throw "Partial download preserved. Inspect or move it before retrying: $partial"}
  Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $partial
  if((Get-FileHash -Algorithm SHA256 $partial).Hash.ToLower() -ne $Digest){throw "Downloaded hash mismatch; preserved: $partial"}
  Move-Item $partial $Path
}
$model=$modelProfile.model_files[0]
$modelPath=Join-Path $RuntimeRoot $model.rfilename
if($Mode -eq 'Prepare') {
  $bin=Join-Path $RuntimeRoot 'bin'
  if((Test-Path $bin) -and (Get-ChildItem -Recurse -File $bin | Select-Object -First 1)){throw 'Existing extracted runtime preserved. Use Inspect/Serve or a new RuntimeRoot.'}
  Fetch-Pinned "https://huggingface.co/$($modelProfile.model_repository)/resolve/$($modelProfile.model_revision)/$($model.rfilename)" $modelPath $model.lfs.sha256 $model.size
  $bin=Join-Path $RuntimeRoot 'bin';New-Item -ItemType Directory -Force $bin | Out-Null
  foreach($asset in $modelProfile.runtime_assets) {
    $zip=Join-Path $RuntimeRoot $asset.name
    Fetch-Pinned $asset.url $zip $asset.sha256.Replace('sha256:','') $asset.bytes
    # Measure uncompressed entries before extraction; archive size is not a reserve.
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive=[IO.Compression.ZipFile]::OpenRead($zip)
    try {$expanded=($archive.Entries | Measure-Object -Property Length -Sum).Sum}
    finally {$archive.Dispose()}
    Assert-Storage $expanded | Out-Null
    Expand-Archive -Path $zip -DestinationPath $bin -Force
  }
  $inventory=Get-ChildItem -Recurse -File $RuntimeRoot | ForEach-Object {@{path=$_.FullName.Substring($RuntimeRoot.Length+1);bytes=$_.Length;sha256=(Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower()}}
  @{profile=$modelProfile;inventory=$inventory;storage=(Assert-Storage);prepared=$true;inference_tested=$false} | ConvertTo-Json -Depth 20 | Set-Content (Join-Path $RuntimeRoot 'receipt.json')
}
if($Mode -eq 'Inspect'){Assert-Storage | ConvertTo-Json;nvidia-smi;exit}
if($Mode -eq 'Serve') {
  Assert-Storage | Out-Null
  if((Get-FileHash $modelPath -Algorithm SHA256).Hash.ToLower() -ne $model.lfs.sha256){throw 'Model digest changed.'}
  $receipt=Get-Content -Raw (Join-Path $RuntimeRoot 'receipt.json') | ConvertFrom-Json
  foreach($file in $receipt.inventory){if((Get-FileHash (Join-Path $RuntimeRoot $file.path) -Algorithm SHA256).Hash.ToLower() -ne $file.sha256){throw "Runtime file changed: $($file.path)"}}
  $server=Get-ChildItem -Recurse -File (Join-Path $RuntimeRoot 'bin') -Filter llama-server.exe | Select-Object -First 1
  if($null -eq $server){throw 'Pinned llama-server.exe missing.'}
  nvidia-smi
  & $server.FullName --model $modelPath --host 127.0.0.1 --port 8130 --ctx-size 4096 --parallel 1 --threads 4 --n-predict 1024 --n-gpu-layers 99 --jinja --no-webui
  if($LASTEXITCODE -ne 0){throw 'Inference exited unsuccessfully. Preserve output; do not silently change model or offload settings.'}
}
