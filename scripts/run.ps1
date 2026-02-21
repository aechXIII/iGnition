param(
  [Parameter(Mandatory = $false)]
  [switch]$Background,

  [Parameter(Mandatory = $false)]
  [switch]$Headless
)

$env:PYTHONPATH = (Resolve-Path .\src).Path

$argsList = @("-m", "ignition")
if ($Background) { $argsList += "--background" }
if ($Headless) { $argsList += "--headless" }

& .\.venv\Scripts\python.exe @argsList

