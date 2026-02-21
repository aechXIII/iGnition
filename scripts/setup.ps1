param(
  [Parameter(Mandatory = $false)]
  [string]$Python = "python"
)

& $Python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

