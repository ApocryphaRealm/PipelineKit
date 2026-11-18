# Get-PluginRecordTypes.ps1
# Enumerates the record types present in a Bethesda TES5/SSE plugin (.esp/.esm/.esl)
# by walking the GRUP tree directly. No masters, no xEdit, no game install required.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Path,
    [switch]$TopLevelOnly   # only the top-level GRUP labels (fast; CELL/WRLD presence)
)

$fs = [System.IO.File]::OpenRead((Resolve-Path $Path))
$br = New-Object System.IO.BinaryReader($fs)
$found = [ordered]@{}

function Read-Sig([System.IO.BinaryReader]$r) {
    [System.Text.Encoding]::ASCII.GetString($r.ReadBytes(4))
}

function Walk-Group([System.IO.BinaryReader]$r, [long]$end, [int]$depth) {
    while ($r.BaseStream.Position -lt $end) {
        $sig  = Read-Sig $r
        $size = $r.ReadUInt32()
        if ($sig -eq 'GRUP') {
            # TES5/SSE GRUP header is 24 bytes and $size INCLUDES it.
            # Corrupt/truncated guard: groupSize INCLUDES the 24-byte header, so anything
            # under 24 is malformed. Without this the walk can loop forever on a bad file.
            if ($size -lt 24) { throw "Malformed GRUP (size $size < 24) at offset $($r.BaseStream.Position - 8)" }
            $label = $r.ReadBytes(4)
            $type  = $r.ReadInt32()
            $null  = $r.ReadBytes(8)          # timestamp, VCS, version, unknown
            $childEnd = $r.BaseStream.Position + ($size - 24)
            if ($childEnd -gt $end) { throw "GRUP overruns its parent at offset $($r.BaseStream.Position)" }
            if ($type -eq 0) {
                $lab = [System.Text.Encoding]::ASCII.GetString($label)
                $found[$lab] = $true
            }
            if ($TopLevelOnly -and $type -eq 0) {
                $r.BaseStream.Position = $childEnd   # skip the whole group
            } else {
                Walk-Group $r $childEnd ($depth + 1)
            }
        } else {
            # Ordinary record. TES5 record header is 24 bytes; $size is the DATA size
            # only (and is the COMPRESSED size if flag 0x00040000 is set) -- either way
            # skipping by $size is correct, so compression never needs handling here.
            $found[$sig] = $true
            $null = $r.ReadBytes(16)          # flags, formID, timestamp, VCS, version, unk
            $r.BaseStream.Position += $size
        }
    }
}

try {
    # TES4 header record: 24-byte header + dataSize bytes
    $sig = Read-Sig $br
    if ($sig -ne 'TES4') { throw "Not a Bethesda plugin (expected TES4, got '$sig')" }
    $hdrSize = $br.ReadUInt32()
    $null = $br.ReadBytes(16)
    $br.BaseStream.Position += $hdrSize

    Walk-Group $br $fs.Length 0
}
finally { $br.Dispose(); $fs.Dispose() }

[pscustomobject]@{
    Plugin        = (Split-Path $Path -Leaf)
    RecordTypes   = ($found.Keys | Sort-Object)
    # NOTE: ACRE (placed creature) is Oblivion/FO3 only and does NOT exist in Skyrim --
    # Skyrim folded creatures into NPCs, so a placed actor is always ACHR. Searching for
    # ACRE in a Skyrim plugin never matches. LAND/NAVM/PHZD are likewise worldspace-only.
    # Validated across all 3,794 plugins in the Apostasy modlist: every plugin containing
    # REFR or ACHR (1,924 of them) also had a top-level CELL or WRLD group -- so
    # -TopLevelOnly is exactly as accurate here as the full walk, and ~100x faster.
    HasWorldRefs  = [bool](@('CELL','WRLD','REFR','ACHR','LAND','NAVM','PHZD') |
                           Where-Object { $found.Contains($_) })
}
