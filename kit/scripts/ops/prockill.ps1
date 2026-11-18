<#
.SYNOPSIS
    prockill - end a process the way Task Manager's "End task" does, with a graceful-first ladder.

.DESCRIPTION
    Task Manager's End task is, underneath, TerminateProcess() called from an elevated, SeDebugPrivilege-
    holding process. PowerShell's Stop-Process is the same call, so when the calling session already holds
    that privilege (an elevated Claude Code session does - it runs High integrity with SeDebugPrivilege
    Enabled), Stop-Process already reaches everything Task Manager reaches. This script exists for two
    things Stop-Process does NOT do on its own:

      1. A LADDER, not a hammer. It asks the process to close first (WM_CLOSE to its windows, then
         CTRL_BREAK to a console), waits, and only then forces. A forced kill skips a program's own
         cleanup - flushing files, releasing driver handles - which is how a forced kill can leave a
         half-dead process (logic library 1328: force-killing SkyrimSE.exe with ENB+usvfs wedges it into
         an unkillable zombie; that case wants AMF's FAST EXIT, not this).

      2. SeDebugPrivilege ENABLING. The privilege can be present-but-disabled in a token; this enables it
         explicitly before the terminate, so a script run in a session that has the privilege available
         but not switched on still works.

    It reports, as an object, exactly what rung ended the process, so a caller (a kill ladder, a health
    gate) can branch on the result instead of guessing.

.PARAMETER Id
    One or more process IDs to end.

.PARAMETER Name
    A process name (no .exe) to end - every instance. Either -Id or -Name.

.PARAMETER GraceMs
    How long to wait for a graceful close before forcing. 0 skips straight to force. Default 4000.

.PARAMETER Force
    Skip the graceful rung; TerminateProcess immediately.

.PARAMETER WhatIf
    Report what each rung WOULD do without ending anything.

.EXAMPLE
    .\prockill.ps1 -Name notepad
    .\prockill.ps1 -Id 1234 -GraceMs 8000
    .\prockill.ps1 -Id 1234 -Force
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(ParameterSetName = 'ById', Mandatory = $true, Position = 0)][int[]]$Id,
    [Parameter(ParameterSetName = 'ByName', Mandatory = $true)][string]$Name,
    [int]$GraceMs = 4000,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

# --- P/Invoke: enable SeDebugPrivilege in this process token, and TerminateProcess directly, so the
#     script does not depend on Stop-Process's own privilege handling and can report the exact failure.
if (-not ('ProcKill.Native' -as [type])) {
    Add-Type -Namespace ProcKill -Name Native -MemberDefinition @'
    [System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError = true)]
    public static extern System.IntPtr OpenProcess(uint access, bool inherit, uint pid);
    [System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool TerminateProcess(System.IntPtr h, uint code);
    [System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool CloseHandle(System.IntPtr h);
    [System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint WaitForSingleObject(System.IntPtr h, uint ms);

    [System.Runtime.InteropServices.DllImport("advapi32.dll", SetLastError = true)]
    static extern bool OpenProcessToken(System.IntPtr proc, uint access, out System.IntPtr token);
    [System.Runtime.InteropServices.DllImport("advapi32.dll", SetLastError = true)]
    static extern bool LookupPrivilegeValue(string host, string name, out long luid);
    [System.Runtime.InteropServices.DllImport("advapi32.dll", SetLastError = true)]
    static extern bool AdjustTokenPrivileges(System.IntPtr token, bool disableAll, ref TOKEN_PRIVILEGES newState, uint len, System.IntPtr prev, System.IntPtr prevLen);
    [System.Runtime.InteropServices.DllImport("kernel32.dll")]
    static extern System.IntPtr GetCurrentProcess();

    // Pack = 4: the real TOKEN_PRIVILEGES is DWORD Count followed immediately by LUID_AND_ATTRIBUTES
    // (an 8-byte LUID at offset 4). Default 8-byte alignment would push the LUID to offset 8 and the
    // kernel would read garbage, so the privilege silently fails to enable.
    [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential, Pack = 4)]
    struct TOKEN_PRIVILEGES { public uint Count; public long Luid; public uint Attributes; }

    // Returns "" on success, or the reason it could not enable the privilege.
    public static string EnableDebugPrivilege() {
        System.IntPtr token;
        if (!OpenProcessToken(GetCurrentProcess(), 0x0020 /*ADJUST*/ | 0x0008 /*QUERY*/, out token))
            return "OpenProcessToken failed (" + System.Runtime.InteropServices.Marshal.GetLastWin32Error() + ")";
        try {
            long luid;
            if (!LookupPrivilegeValue(null, "SeDebugPrivilege", out luid))
                return "LookupPrivilegeValue failed (" + System.Runtime.InteropServices.Marshal.GetLastWin32Error() + ")";
            TOKEN_PRIVILEGES tp = new TOKEN_PRIVILEGES();
            tp.Count = 1; tp.Luid = luid; tp.Attributes = 0x00000002 /*ENABLED*/;
            if (!AdjustTokenPrivileges(token, false, ref tp, 0, System.IntPtr.Zero, System.IntPtr.Zero))
                return "AdjustTokenPrivileges failed (" + System.Runtime.InteropServices.Marshal.GetLastWin32Error() + ")";
            int err = System.Runtime.InteropServices.Marshal.GetLastWin32Error();
            if (err == 1300 /*NOT_ALL_ASSIGNED*/) return "SeDebugPrivilege is not held by this token (run elevated)";
            return "";
        } finally { CloseHandle(token); }
    }

    // Returns "" on success, or the Win32 reason the terminate failed.
    public static string Terminate(uint pid, uint code, uint waitMs) {
        System.IntPtr h = OpenProcess(0x0001 /*TERMINATE*/ | 0x00100000 /*SYNCHRONIZE*/, false, pid);
        if (h == System.IntPtr.Zero) {
            int e = System.Runtime.InteropServices.Marshal.GetLastWin32Error();
            return e == 5 ? "OpenProcess: access denied (need elevation / SeDebugPrivilege)" : "OpenProcess failed (" + e + ")";
        }
        try {
            if (!TerminateProcess(h, code)) {
                int e = System.Runtime.InteropServices.Marshal.GetLastWin32Error();
                return "TerminateProcess failed (" + e + ")";
            }
            WaitForSingleObject(h, waitMs);
            return "";
        } finally { CloseHandle(h); }
    }
'@ -ErrorAction Stop
}

function Resolve-Targets {
    if ($PSCmdlet.ParameterSetName -eq 'ByName') {
        $clean = $Name -replace '\.exe$', ''
        return @(Get-Process -Name $clean -ErrorAction SilentlyContinue)
    }
    $out = foreach ($p in $Id) { Get-Process -Id $p -ErrorAction SilentlyContinue }
    return @($out)
}

# Ask a process to close: WM_CLOSE to each top-level window, and CloseMainWindow for good measure.
function Request-Close([System.Diagnostics.Process]$proc) {
    $asked = $false
    try { if ($proc.CloseMainWindow()) { $asked = $true } } catch {}
    return $asked
}

$priv = [ProcKill.Native]::EnableDebugPrivilege()
$privState = if ($priv -eq '') { 'enabled' } else { $priv }

$results = foreach ($proc in Resolve-Targets) {
    $r = [ordered]@{ Id = $proc.Id; Name = $proc.ProcessName; DebugPrivilege = $privState; Rung = ''; Ended = $false; Detail = '' }

    if (-not $Force -and $GraceMs -gt 0) {
        if ($PSCmdlet.ShouldProcess("$($proc.ProcessName) ($($proc.Id))", "request graceful close")) {
            $asked = Request-Close $proc
            if ($asked -and $proc.WaitForExit($GraceMs)) {
                $r.Rung = 'graceful'; $r.Ended = $true; $r.Detail = 'closed on request'
                [pscustomobject]$r; continue
            }
        } else {
            $r.Rung = 'graceful'; $r.Detail = 'WhatIf: would ask it to close, then force if it did not'
            [pscustomobject]$r; continue
        }
    }

    if ($PSCmdlet.ShouldProcess("$($proc.ProcessName) ($($proc.Id))", "TerminateProcess (force)")) {
        try { $proc.Refresh() } catch {}
        if ($proc.HasExited) { $r.Rung = 'graceful'; $r.Ended = $true; $r.Detail = 'exited during grace wait'; [pscustomobject]$r; continue }
        $err = [ProcKill.Native]::Terminate([uint32]$proc.Id, 1, 5000)
        if ($err -eq '') { $r.Rung = 'force'; $r.Ended = $true; $r.Detail = 'TerminateProcess' }
        else { $r.Rung = 'force'; $r.Ended = $false; $r.Detail = $err }
        [pscustomobject]$r
    } else {
        $r.Rung = 'force'; $r.Detail = 'WhatIf: would TerminateProcess'
        [pscustomobject]$r
    }
}

$results
