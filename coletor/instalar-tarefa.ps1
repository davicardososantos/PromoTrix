# Registra (ou remove) a tarefa "PromoTrix" no Agendador de Tarefas do Windows.
# A tarefa checa 2 min depois do logon e depois a cada N minutos (padrao 30), so com o usuario logado,
# porque a janela de alerta precisa da sessao dele.
#
# Uso (na pasta do projeto):
#   powershell -ExecutionPolicy Bypass -File instalar-tarefa.ps1              instala ou atualiza
#   powershell -ExecutionPolicy Bypass -File instalar-tarefa.ps1 -Minutos 60  outro intervalo
#   powershell -ExecutionPolicy Bypass -File instalar-tarefa.ps1 -Remover     remove a tarefa
#
# Arquivo sem acento de proposito: o PowerShell 5.1 le .ps1 sem BOM como ANSI.

param([int]$Minutos = 30, [switch]$Remover, [string]$Nome = 'PromoTrix')

if ($Remover) {
    Unregister-ScheduledTask -TaskName $Nome -Confirm:$false
    "Tarefa '$Nome' removida."
    exit 0
}
if ($Minutos -lt 15) { throw 'Use 15 minutos ou mais: o PromoTrix le um site publico e nao deve sobrecarregar.' }

$pythonw = (Get-Command pythonw.exe -ErrorAction Stop).Source
$script  = Join-Path $PSScriptRoot 'promotrix.py'
$acao    = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`"" -WorkingDirectory $PSScriptRoot

$noLogon = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$noLogon.Delay = 'PT2M'
$repetir = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $Minutos)

$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
          -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $Nome -Action $acao -Trigger $noLogon, $repetir -Settings $config -Force `
    -Description 'PromoTrix: le o Pelando e avisa quando aparece promocao dentro dos alvos do config.json.' | Out-Null

"Tarefa '$Nome' instalada: 2 min depois do logon e a cada $Minutos min. Proxima: $((Get-ScheduledTaskInfo -TaskName $Nome).NextRunTime)"
