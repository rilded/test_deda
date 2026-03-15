"""
Модуль управления процессами Windows
Расширенный диспетчер задач с заморозкой процессов и снятием флага "критический"
"""

import ctypes
from ctypes import wintypes
import subprocess
import logging

# Константа для скрытия окна консоли
CREATE_NO_WINDOW = 0x08000000

# Константы для работы с процессами
PROCESS_TERMINATE = 0x0001
PROCESS_SUSPEND_RESUME = 0x0800
PROCESS_SET_INFORMATION = 0x0200
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_DUP_HANDLE = 0x0040

# Приоритеты процессов
IDLE_PRIORITY_CLASS = 0x00000040
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
NORMAL_PRIORITY_CLASS = 0x00000020
ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000
HIGH_PRIORITY_CLASS = 0x00000080
REALTIME_PRIORITY_CLASS = 0x00000100

# Настройка логирования
logger = logging.getLogger(__name__)


def run_hidden_command(cmd: str, capture_output: bool = False) -> subprocess.CompletedProcess:
    """Выполнить команду без показа окна консоли"""
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    return subprocess.run(
        cmd,
        shell=True,
        capture_output=capture_output,
        text=True,
        startupinfo=startupinfo,
        creationflags=CREATE_NO_WINDOW
    )


def run_hidden_powershell(ps_command: str, capture_output: bool = True) -> subprocess.CompletedProcess:
    """Выполнить PowerShell команду без показа окна"""
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    return subprocess.run(
        ['powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_command],
        capture_output=capture_output,
        text=True,
        startupinfo=startupinfo,
        creationflags=CREATE_NO_WINDOW
    )


class ProcessManager:
    """Класс для управления процессами"""
    
    def __init__(self):
        self.kernel32 = ctypes.windll.kernel32
        self.ntdll = ctypes.windll.ntdll
        self.psapi = ctypes.windll.psapi
    
    def get_processes(self) -> list:
        """Получить список всех процессов"""
        processes = []

        try:
            # Используем tasklist для получения информации
            result = run_hidden_command('tasklist /fo CSV /nh /v', capture_output=True)

            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line:
                    # Парсим CSV
                    parts = line.split('","')
                    if len(parts) >= 7:
                        try:
                            pid = int(parts[1].strip('"'))
                            processes.append({
                                'name': parts[0].strip('"'),
                                'pid': pid,
                                'memory': parts[4].strip('"'),
                                'status': parts[6].strip('"'),
                                'user': parts[5].strip('"')
                            })
                        except (ValueError, IndexError):
                            pass
        except Exception:
            pass

        return processes
    
    def open_process(self, pid: int, access: int = PROCESS_QUERY_INFORMATION) -> int:
        """Открыть дескриптор процесса"""
        try:
            handle = self.kernel32.OpenProcess(access, False, pid)
            return handle
        except Exception:
            return 0
    
    def close_process(self, handle: int) -> bool:
        """Закрыть дескриптор процесса"""
        try:
            self.kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    
    def terminate_process(self, pid: int) -> bool:
        """Завершить процесс"""
        try:
            handle = self.open_process(pid, PROCESS_TERMINATE)
            if handle:
                result = self.kernel32.TerminateProcess(handle, 0)
                self.close_process(handle)
                return result != 0
            return False
        except Exception:
            return False
    
    def suspend_process(self, pid: int) -> bool:
        """
        Заморозить процесс (suspend)
        Примечание: требует дополнительных вызовов для потоков
        """
        try:
            # Получаем все потоки процесса
            ps_command = f'''
            Get-WmiObject Win32_Thread | Where-Object {{ $_.ProcessHandle -eq {pid} }} | ForEach-Object {{
                $h = [VirusBypass.ProcessManager]::OpenProcess(0x0800, $false, {pid})
                if ($h -ne 0) {{
                    [VirusBypass.ProcessManager]::SuspendThreadById($h)
                    [VirusBypass.ProcessManager]::CloseHandle($h)
                }}
            }}
            '''
            # Упрощённая версия через NtSuspendProcess
            handle = self.open_process(pid, PROCESS_SUSPEND_RESUME)
            if handle:
                result = self.ntdll.NtSuspendProcess(handle)
                self.close_process(handle)
                return result == 0
            return False
        except Exception:
            return False
    
    def resume_process(self, pid: int) -> bool:
        """Разморозить процесс (resume)"""
        try:
            handle = self.open_process(pid, PROCESS_SUSPEND_RESUME)
            if handle:
                result = self.ntdll.NtResumeProcess(handle)
                self.close_process(handle)
                return result == 0
            return False
        except Exception:
            return False
    
    def set_priority(self, pid: int, priority: int) -> bool:
        """Установить приоритет процесса"""
        try:
            handle = self.open_process(pid, PROCESS_SET_INFORMATION)
            if handle:
                result = self.kernel32.SetPriorityClass(handle, priority)
                self.close_process(handle)
                return result != 0
            return False
        except Exception:
            return False
    
    def get_process_details(self, pid: int) -> dict:
        """Получить детальную информацию о процессе"""
        details = {
            'pid': pid,
            'name': '',
            'path': '',
            'memory_usage': 0,
            'thread_count': 0,
            'is_critical': False
        }
        
        try:
            # Получаем имя и путь через WMI
            ps_command = f'''
            Get-CimInstance Win32_Process -Filter "ProcessId = {pid}" | Select-Object Name, ExecutablePath, WorkingSetSize, ThreadCount | ConvertTo-Json
            '''
            result = run_hidden_powershell(ps_command)

            import json
            try:
                data = json.loads(result.stdout)
                if data:
                    details['name'] = data.get('Name', '')
                    details['path'] = data.get('ExecutablePath', '')
                    details['memory_usage'] = data.get('WorkingSetSize', 0)
                    details['thread_count'] = data.get('ThreadCount', 0)
            except json.JSONDecodeError:
                pass

            # Проверяем, является ли процесс критическим
            details['is_critical'] = self._is_critical_process(pid)

        except Exception:
            pass

        return details
    
    def _is_critical_process(self, pid: int) -> bool:
        """Проверить, является ли процесс критическим"""
        # Список критических системных процессов
        critical_processes = [
            'system', 'smss.exe', 'csrss.exe', 'wininit.exe',
            'services.exe', 'lsass.exe', 'lsm.exe', 'svchost.exe',
            'explorer.exe', 'winlogon.exe'
        ]
        
        processes = self.get_processes()
        for proc in processes:
            if proc['pid'] == pid:
                return proc['name'].lower() in critical_processes
        
        return False
    
    def remove_critical_flag(self, pid: int) -> bool:
        """
        Снять флаг "критический процесс"
        ВНИМАНИЕ: Может привести к нестабильности системы!
        Использует прямой вызов через C# код
        """
        try:
            # Используем C# код для прямого вызова API
            ps_script = f'''
            $code = @'
            using System;
            using System.Runtime.InteropServices;
            public class ProcessUtils {{
                [DllImport("kernel32.dll", SetLastError = true)]
                public static extern IntPtr OpenProcess(int dwDesiredAccess, bool bInheritHandle, int dwProcessId);
                
                [DllImport("kernel32.dll", SetLastError = true)]
                public static extern bool CloseHandle(IntPtr hObject);
                
                [DllImport("ntdll.dll")]
                public static extern int NtSetInformationProcess(IntPtr hProcess, int processInformationClass, ref int processInformation, int processInformationLength);
                
                public static bool RemoveCriticalFlag(int pid) {{
                    const int PROCESS_QUERY_INFORMATION = 0x0400;
                    const int PROCESS_SET_INFORMATION = 0x0200;
                    const int PROCESS_VM_READ = 0x0010;
                    const int ProcessBreakOnTermination = 0x1D;
                    
                    int access = PROCESS_QUERY_INFORMATION | PROCESS_SET_INFORMATION | PROCESS_VM_READ;
                    IntPtr hProcess = OpenProcess(access, false, pid);
                    
                    if (hProcess == IntPtr.Zero) {{
                        Console.WriteLine("ERROR: Cannot open process");
                        return false;
                    }}
                    
                    int value = 0; // 0 = не критический
                    int result = NtSetInformationProcess(hProcess, ProcessBreakOnTermination, ref value, 4);
                    CloseHandle(hProcess);
                    
                    if (result == 0) {{
                        Console.WriteLine("SUCCESS");
                        return true;
                    }} else {{
                        Console.WriteLine($"ERROR: NTSTATUS={{result:X8}}");
                        return false;
                    }}
                }}
            }}
'@

            Add-Type -TypeDefinition $code -Language CSharp -Force
            [ProcessUtils]::RemoveCriticalFlag({pid})
            '''
            
            result = run_hidden_powershell(ps_script)
            return 'SUCCESS' in result.stdout or result.returncode == 0
        except Exception as e:
            print(f"Ошибка снятия флага критичности: {e}")
            return False

    def kill_process_tree(self, pid: int) -> bool:
        """Убить процесс и все его дочерние процессы"""
        try:
            # Получаем все дочерние процессы
            ps_command = f'''
            Get-CimInstance Win32_Process | Where-Object {{ $_.ParentProcessId -eq {pid} }} | ForEach-Object {{
                Stop-Process -Id $_.ProcessId -Force
            }}
            '''
            run_hidden_powershell(ps_command)

            # Убиваем основной процесс
            return self.terminate_process(pid)
        except Exception:
            return False

    def find_process_by_name(self, name: str) -> list:
        """Найти процессы по имени"""
        result = []
        processes = self.get_processes()
        name_lower = name.lower()

        for proc in processes:
            if name_lower in proc['name'].lower():
                result.append(proc)

        return result

    def get_process_handles(self, pid: int) -> list:
        """Получить список открытых файловых дескрипторов процесса"""
        handles = []

        try:
            # Используем handle.exe от Sysinternals (если доступен)
            result = run_hidden_command('handle -p {} -accepteula'.format(pid), capture_output=True)

            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'File' in line or 'Directory' in line:
                        handles.append(line.strip())
        except Exception:
            pass

        return handles
    
    def close_process_handle(self, pid: int, handle_value: int) -> bool:
        """Закрыть конкретный дескриптор процесса"""
        try:
            # Требуются права отладки
            handle = self.open_process(pid, PROCESS_DUP_HANDLE)
            if handle:
                self.kernel32.CloseHandle(handle_value)
                self.close_process(handle)
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка закрытия дескриптора {handle_value}: {e}")
            return False


# Функции для быстрого доступа
def get_processes():
    """Получить список процессов"""
    manager = ProcessManager()
    return manager.get_processes()


def terminate_process(pid: int):
    """Завершить процесс"""
    manager = ProcessManager()
    return manager.terminate_process(pid)


def suspend_process(pid: int):
    """Заморозить процесс"""
    manager = ProcessManager()
    return manager.suspend_process(pid)


def resume_process(pid: int):
    """Разморозить процесс"""
    manager = ProcessManager()
    return manager.resume_process(pid)
