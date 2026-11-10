param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot 'logs'),
    [string]$ProcessName = 'MGS MC2 Bonus Content',
    [switch]$CompileOnly
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$logPath = Join-Path $OutputDirectory ("emulator-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

$source = @'
using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

public static class MgsEmulatorDebugCapture
{
    private const uint PAGE_READWRITE = 0x04;
    private const uint FILE_MAP_READ = 0x0004;
    private const uint WAIT_OBJECT_0 = 0;
    private const uint WAIT_TIMEOUT = 0x102;
    private static volatile bool StopRequested;
    private static ConsoleCtrlHandler CtrlHandler;

    private delegate bool ConsoleCtrlHandler(uint ctrlType);

    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    private static extern IntPtr CreateEvent(IntPtr attributes, bool manualReset, bool initialState, string name);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    private static extern IntPtr CreateFileMapping(IntPtr file, IntPtr attributes, uint protect, uint high, uint low, string name);
    [DllImport("kernel32.dll", SetLastError=true)]
    private static extern IntPtr MapViewOfFile(IntPtr mapping, uint access, uint high, uint low, UIntPtr count);
    [DllImport("kernel32.dll")] private static extern bool SetEvent(IntPtr handle);
    [DllImport("kernel32.dll")] private static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);
    [DllImport("kernel32.dll")] private static extern bool UnmapViewOfFile(IntPtr view);
    [DllImport("kernel32.dll")] private static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll")] private static extern bool SetConsoleCtrlHandler(ConsoleCtrlHandler handler, bool add);

    public static void RequestStop() { StopRequested = true; }
    private static bool OnConsoleCtrl(uint ctrlType) { StopRequested = true; return true; }

    public static void Run(string path, string processName)
    {
        CtrlHandler = OnConsoleCtrl;
        SetConsoleCtrlHandler(CtrlHandler, true);
        IntPtr ready = CreateEvent(IntPtr.Zero, false, false, "DBWIN_BUFFER_READY");
        IntPtr data = CreateEvent(IntPtr.Zero, false, false, "DBWIN_DATA_READY");
        IntPtr mapping = CreateFileMapping(new IntPtr(-1), IntPtr.Zero, PAGE_READWRITE, 0, 4096, "DBWIN_BUFFER");
        if (ready == IntPtr.Zero || data == IntPtr.Zero || mapping == IntPtr.Zero)
            throw new InvalidOperationException("DBWIN channel setup failed: " + Marshal.GetLastWin32Error());
        IntPtr view = MapViewOfFile(mapping, FILE_MAP_READ, 0, 0, new UIntPtr(4096));
        if (view == IntPtr.Zero) throw new InvalidOperationException("DBWIN mapping failed: " + Marshal.GetLastWin32Error());
        try
        {
            using (var writer = new StreamWriter(path, false, new UTF8Encoding(true)))
            {
                writer.AutoFlush = true;
                writer.WriteLine("# timestamp | pid | debug output from " + processName);
                SetEvent(ready);
                while (!StopRequested)
                {
                    uint wait = WaitForSingleObject(data, 500);
                    if (wait == WAIT_TIMEOUT) continue;
                    if (wait != WAIT_OBJECT_0) throw new InvalidOperationException("DBWIN wait failed: " + wait);
                    int pid = Marshal.ReadInt32(view);
                    byte[] bytes = new byte[4092];
                    Marshal.Copy(IntPtr.Add(view, 4), bytes, 0, bytes.Length);
                    int end = Array.IndexOf(bytes, (byte)0);
                    if (end < 0) end = bytes.Length;
                    string message = Encoding.Default.GetString(bytes, 0, end).TrimEnd('\r', '\n');
                    bool game = false;
                    try { game = string.Equals(Process.GetProcessById(pid).ProcessName,
                        processName, StringComparison.OrdinalIgnoreCase); }
                    catch (ArgumentException) {}
                    if (game)
                    {
                        string line = DateTimeOffset.Now.ToString("o") + " | " + pid + " | " + message;
                        writer.WriteLine(line);
                        if (message.Contains("MGS_QE_DIAG") || message.Contains("setemukey_keyboard"))
                            Console.WriteLine(line);
                    }
                    SetEvent(ready);
                }
            }
        }
        finally
        {
            UnmapViewOfFile(view);
            CloseHandle(mapping);
            CloseHandle(data);
            CloseHandle(ready);
            SetConsoleCtrlHandler(CtrlHandler, false);
        }
    }
}
'@

Add-Type -TypeDefinition $source -Language CSharp
if ($CompileOnly) { Write-Host 'Capture code compiled successfully.'; return }
Write-Host "Emulator debug capture started: $logPath"
Write-Host 'Start the game; press Q, E, and controller triggers in gameplay. Press Ctrl+C here to finish.'
try {
    [MgsEmulatorDebugCapture]::Run($logPath, $ProcessName)
}
finally {
    Write-Host "Log saved: $logPath"
}
