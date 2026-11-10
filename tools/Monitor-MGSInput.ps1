param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot 'logs')
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$logPath = Join-Path $OutputDirectory ("input-{0}.csv" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

$source = @'
using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

public static class MgsInputMonitor
{
    private const int WH_KEYBOARD_LL = 13;
    private const int WM_KEYDOWN = 0x0100;
    private const int WM_KEYUP = 0x0101;
    private const int WM_SYSKEYDOWN = 0x0104;
    private const int WM_SYSKEYUP = 0x0105;
    private const uint WM_QUIT = 0x0012;
    private static readonly object Gate = new object();
    private static StreamWriter Writer;
    private static Thread HookThread;
    private static uint HookThreadId;
    private static IntPtr HookHandle;
    private static LowLevelKeyboardProc HookProc;
    private static readonly ManualResetEvent HookReady = new ManualResetEvent(false);
    private static XInputGetStateDelegate XInputGetState;

    [StructLayout(LayoutKind.Sequential)]
    private struct KBDLLHOOKSTRUCT { public uint vkCode, scanCode, flags, time; public IntPtr dwExtraInfo; }
    [StructLayout(LayoutKind.Sequential)]
    private struct POINT { public int x, y; }
    [StructLayout(LayoutKind.Sequential)]
    private struct MSG { public IntPtr hwnd; public uint message; public UIntPtr wParam; public IntPtr lParam; public uint time; public POINT pt; }
    [StructLayout(LayoutKind.Sequential)]
    private struct XINPUT_GAMEPAD { public ushort wButtons; public byte bLeftTrigger, bRightTrigger; public short sThumbLX, sThumbLY, sThumbRX, sThumbRY; }
    [StructLayout(LayoutKind.Sequential)]
    private struct XINPUT_STATE { public uint dwPacketNumber; public XINPUT_GAMEPAD Gamepad; }
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] private delegate IntPtr LowLevelKeyboardProc(int nCode, IntPtr wParam, IntPtr lParam);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] private delegate uint XInputGetStateDelegate(uint userIndex, out XINPUT_STATE state);

    [DllImport("user32.dll", SetLastError=true)] private static extern IntPtr SetWindowsHookEx(int idHook, LowLevelKeyboardProc callback, IntPtr module, uint threadId);
    [DllImport("user32.dll", SetLastError=true)] private static extern bool UnhookWindowsHookEx(IntPtr hook);
    [DllImport("user32.dll")] private static extern IntPtr CallNextHookEx(IntPtr hook, int nCode, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")] private static extern int GetMessage(out MSG msg, IntPtr hwnd, uint min, uint max);
    [DllImport("user32.dll")] private static extern bool TranslateMessage(ref MSG msg);
    [DllImport("user32.dll")] private static extern IntPtr DispatchMessage(ref MSG msg);
    [DllImport("user32.dll")] private static extern bool PostThreadMessage(uint threadId, uint message, UIntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")] private static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint processId);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int maxCount);
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)] private static extern IntPtr LoadLibrary(string name);
    [DllImport("kernel32.dll", CharSet=CharSet.Ansi, SetLastError=true)] private static extern IntPtr GetProcAddress(IntPtr module, string name);

    private static string Csv(string s) { return "\"" + (s ?? "").Replace("\"", "\"\"") + "\""; }
    private static string FocusInfo()
    {
        IntPtr hwnd = GetForegroundWindow();
        uint pid;
        GetWindowThreadProcessId(hwnd, out pid);
        string name = "";
        if (pid != 0) { try { name = Process.GetProcessById((int)pid).ProcessName; } catch {} }
        StringBuilder title = new StringBuilder(512);
        GetWindowText(hwnd, title, title.Capacity);
        return Csv(pid.ToString()) + "," + Csv(name) + "," + Csv(title.ToString());
    }
    private static void Log(string source, string action, string detail)
    {
        string line = Csv(DateTimeOffset.Now.ToString("o")) + "," + Csv(source) + "," + Csv(action) + "," + Csv(detail) + "," + FocusInfo();
        lock (Gate) { if (Writer != null) { Writer.WriteLine(line); Writer.Flush(); } }
    }

    public static void Start(string path)
    {
        Writer = new StreamWriter(path, false, new UTF8Encoding(true));
        Writer.WriteLine("timestamp,source,event,detail,foreground_pid,foreground_process,foreground_title");
        Writer.Flush();
        LoadXInput();
        HookThread = new Thread(HookLoop);
        HookThread.IsBackground = true;
        HookThread.Name = "MGS input keyboard hook";
        HookThread.Start();
        HookReady.WaitOne(5000);
        Log("monitor", "START", XInputGetState == null ? "XInput unavailable; keyboard Q/E capture active" : "keyboard Q/E and XInput trigger capture active");
    }

    private static void LoadXInput()
    {
        string[] names = { "xinput1_4.dll", "xinput1_3.dll", "xinput9_1_0.dll" };
        foreach (string name in names)
        {
            IntPtr module = LoadLibrary(name);
            if (module == IntPtr.Zero) continue;
            IntPtr proc = GetProcAddress(module, "XInputGetState");
            if (proc != IntPtr.Zero) { XInputGetState = (XInputGetStateDelegate)Marshal.GetDelegateForFunctionPointer(proc, typeof(XInputGetStateDelegate)); return; }
        }
    }

    private static void HookLoop()
    {
        HookThreadId = (uint)AppDomain.GetCurrentThreadId();
        HookProc = KeyboardCallback;
        HookHandle = SetWindowsHookEx(WH_KEYBOARD_LL, HookProc, IntPtr.Zero, 0);
        if (HookHandle == IntPtr.Zero) { Log("keyboard", "HOOK_ERROR", Marshal.GetLastWin32Error().ToString()); HookReady.Set(); return; }
        HookReady.Set();
        MSG msg;
        while (GetMessage(out msg, IntPtr.Zero, 0, 0) > 0) { TranslateMessage(ref msg); DispatchMessage(ref msg); }
        UnhookWindowsHookEx(HookHandle);
        HookHandle = IntPtr.Zero;
    }

    private static IntPtr KeyboardCallback(int code, IntPtr wParam, IntPtr lParam)
    {
        if (code >= 0)
        {
            int message = wParam.ToInt32();
            bool down = message == WM_KEYDOWN || message == WM_SYSKEYDOWN;
            bool up = message == WM_KEYUP || message == WM_SYSKEYUP;
            if (down || up)
            {
                KBDLLHOOKSTRUCT key = (KBDLLHOOKSTRUCT)Marshal.PtrToStructure(lParam, typeof(KBDLLHOOKSTRUCT));
                if (key.vkCode == 0x51 || key.vkCode == 0x45)
                    Log("keyboard", down ? "KEY_DOWN" : "KEY_UP", "VK=" + key.vkCode + " (" + (key.vkCode == 0x51 ? "Q" : "E") + "); scan=" + key.scanCode);
                else if (down && key.vkCode == 0x77)
                    Log("keyboard", "MARK_Q_TEST", "F8 marker");
                else if (down && key.vkCode == 0x78)
                    Log("keyboard", "MARK_E_TEST", "F9 marker");
            }
        }
        return CallNextHookEx(HookHandle, code, wParam, lParam);
    }

    public static void PollXInput()
    {
        if (XInputGetState == null) return;
        bool[] connected = new bool[4];
        byte[] left = new byte[4], right = new byte[4];
        bool[] leftDown = new bool[4], rightDown = new bool[4];
        while (true)
        {
            for (uint i = 0; i < 4; i++)
            {
                XINPUT_STATE state;
                bool nowConnected = XInputGetState(i, out state) == 0;
                if (nowConnected != connected[i]) { connected[i] = nowConnected; Log("xinput", nowConnected ? "CONNECTED" : "DISCONNECTED", "controller=" + i); }
                if (!nowConnected) continue;
                byte l = state.Gamepad.bLeftTrigger, r = state.Gamepad.bRightTrigger;
                if (l != left[i]) { left[i] = l; Log("xinput", "LEFT_TRIGGER_VALUE", "controller=" + i + "; value=" + l); }
                if (r != right[i]) { right[i] = r; Log("xinput", "RIGHT_TRIGGER_VALUE", "controller=" + i + "; value=" + r); }
                bool ld = l >= 30, rd = r >= 30;
                if (ld != leftDown[i]) { leftDown[i] = ld; Log("xinput", ld ? "LEFT_TRIGGER_DOWN" : "LEFT_TRIGGER_UP", "controller=" + i + "; value=" + l); }
                if (rd != rightDown[i]) { rightDown[i] = rd; Log("xinput", rd ? "RIGHT_TRIGGER_DOWN" : "RIGHT_TRIGGER_UP", "controller=" + i + "; value=" + r); }
            }
            Thread.Sleep(10);
        }
    }

    public static void Stop()
    {
        if (HookThreadId != 0) PostThreadMessage(HookThreadId, WM_QUIT, UIntPtr.Zero, IntPtr.Zero);
        if (HookThread != null && HookThread.IsAlive) HookThread.Join(2000);
        Log("monitor", "STOP", "capture ended");
        lock (Gate) { if (Writer != null) { Writer.Dispose(); Writer = null; } }
    }
}
'@

Add-Type -TypeDefinition $source -Language CSharp
Write-Host "MGS 输入诊断已启动。日志：$logPath"
Write-Host '请切回游戏依次按 Q、E，再测试手柄左右扳机。结束时回到此窗口按 Ctrl+C。'
Write-Host '日志只记录系统键盘事件和 XInput 扳机状态，不会拦截按键或修改游戏。'
[MgsInputMonitor]::Start($logPath)
try {
    [MgsInputMonitor]::PollXInput()
}
finally {
    [MgsInputMonitor]::Stop()
    Write-Host "日志已保存：$logPath"
}
