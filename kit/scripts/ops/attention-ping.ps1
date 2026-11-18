<#
.SYNOPSIS
    The owner's "I need your attention" signal: three Windows notification sounds, about one second apart.

.DESCRIPTION
    The owner, 2026-09-30: "your signal to get my attention, which should be recorded for every session, to know is
    three of those sounds in a row, about one second apart." Play it whenever Claude is blocked on him - a question,
    an approval before a public or irreversible step, something only he can do (a login, a dialog in his Chrome) -
    so he can work on something else meanwhile. Not for routine progress.

.EXAMPLE
    & (& py -3 '<ROOT>\.MD\resolvers\resolve.py' find attention-ping)
#>
$wav = Join-Path $env:WINDIR 'Media\Windows Notify System Generic.wav'
for ($i = 0; $i -lt 3; $i++) {
    if (Test-Path -LiteralPath $wav) { (New-Object System.Media.SoundPlayer $wav).PlaySync() }
    else { [System.Media.SystemSounds]::Exclamation.Play() }
    if ($i -lt 2) { Start-Sleep -Milliseconds 700 }
}
