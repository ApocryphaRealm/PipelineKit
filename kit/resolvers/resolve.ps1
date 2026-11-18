param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest)
& py -3 (Join-Path $PSScriptRoot 'resolve.py') @Rest
exit $LASTEXITCODE
