"""
Модуль управления процессами Windows
Расширенный диспетчер задач с заморозкой процессов и снятием флага "критический"
Методы взяты из SimpleUnlocker (TMCore.cs)
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

# Импорты из ntdll (взято из SimpleUnlocker Utils.cs)
ntdll = ctypes.windll.ntdll

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
    """Класс для управления процессами (методы из SimpleUnlocker TMCore.cs)"""
    
    def __init__(self):
        self.kernel32 = ctypes.windll.kernel32
        self.ntdll = ntdll

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
        except Exception as e:
            logger.error(f"Ошибка получения процессов: {e}")

        return processes

    def open_process(self, pid: int, access: int = PROCESS_QUERY_INFORMATION) -> int:
        """Открыть дескриптор процесса"""
        try:
            handle = self.kernel32.OpenProcess(access, False, pid)
            return handle
        except Exception as e:
            logger.error(f"Ошибка открытия процесса {pid}: {e}")
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
                logger.info(f"Процесс {pid} завершён")
                return result != 0
            return False
        except Exception as e:
            logger.error(f"Ошибка завершения процесса {pid}: {e}")
            return False

    def suspend_process(self, pid: int) -> bool:
        """
        Заморозить процесс (метод из SimpleUnlocker)
        Использует NtSuspendProcess из ntdll.dll
        """
        try:
            handle = self.open_process(pid, PROCESS_SUSPEND_RESUME)
            if handle:
                # NtSuspendProcess из SimpleUnlocker
                result = self.ntdll.NtSuspendProcess(handle)
                self.close_process(handle)
                if result == 0:
                    logger.info(f"Процесс {pid} заморожен")
                    return True
            return False
        except Exception as e:
            logger.error(f"Ошибка заморозки процесса {pid}: {e}")
            return False

    def resume_process(self, pid: int) -> bool:
        """
        Разморозить процесс (метод из SimpleUnlocker)
        Использует NtResumeProcess из ntdll.dll
        """
        try:
            handle = self.open_process(pid, PROCESS_SUSPEND_RESUME)
            if handle:
                # NtResumeProcess из SimpleUnlocker
                result = self.ntdll.NtResumeProcess(handle)
                self.close_process(handle)
                if result == 0:
                    logger.info(f"Процесс {pid} разморожен")
                    return True
            return False
        except Exception as e:
            logger.error(f"Ошибка разморозки процесса {pid}: {e}")
            return False

    def is_process_critical(self, pid: int) -> bool:
        """
        Проверить является ли процесс критическим (метод из SimpleUnlocker TMCore.cs)
        Использует NtQueryInformationProcess с ProcessBreakOnTermination (29)
        """
        try:
            handle = self.open_process(pid, PROCESS_QUERY_INFORMATION)
            if handle:
                value = ctypes.c_uint(0)
                size = ctypes.c_int()
                # ProcessBreakOnTermination = 29
                result = self.ntdll.NtQueryInformationProcess(handle, 29, ctypes.byref(value), ctypes.sizeof(ctypes.c_uint), ctypes.byref(size))
                self.close_process(handle)
                if result == 0 and size.value == ctypes.sizeof(ctypes.c_uint):
                    is_critical = value.value != 0
                    logger.debug(f"Процесс {pid} критический: {is_critical}")
                    return is_critical
            return False
        except Exception as e:
            logger.error(f"Ошибка проверки критичности процесса {pid}: {e}")
            return False

    def remove_critical_flag(self, pid: int) -> bool:
        """
        Снять флаг "критический процесс" (метод из SimpleUnlocker TMCore.cs)
        Использует NtSetInformationProcess с ProcessBreakOnTermination (0x1D = 29)
        """
        try:
            # ProcessBreakOnTermination = 0x1D (29)
            BreakOnTermination = 0x1D
            
            handle = self.open_process(pid, PROCESS_SET_INFORMATION)
            if handle:
                is_critical = ctypes.c_int(0)  # 0 = не критический
                # NtSetInformationProcess из SimpleUnlocker
                result = self.ntdll.NtSetInformationProcess(handle, BreakOnTermination, ctypes.byref(is_critical), ctypes.sizeof(ctypes.c_int))
                self.close_process(handle)
                if result == 0:
                    logger.info(f"Критический флаг снят с процесса {pid}")
                    return True
                else:
                    logger.error(f"Ошибка снятия флага критичности. NTSTATUS: {result:X}")
            return False
        except Exception as e:
            logger.error(f"Ошибка снятия флага критичности: {e}")
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
        except Exception as e:
            logger.error(f"Ошибка установки приоритета: {e}")
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
        except Exception as e:
            logger.error(f"Ошибка удаления дерева процессов: {e}")
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
