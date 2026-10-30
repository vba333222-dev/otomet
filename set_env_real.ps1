$env:JAVA_HOME="C:\tools\jdk17"
$env:ANDROID_HOME="$env:LOCALAPPDATA\Android\Sdk"
$env:ANDROID_SDK_ROOT="$env:LOCALAPPDATA\Android\Sdk"
$env:PATH="C:\tools\jdk17\bin;$env:LOCALAPPDATA\Android\Sdk\platform-tools;$env:LOCALAPPDATA\Android\Sdk\emulator;C:\nvm4w\nodejs;$env:PATH"
Write-Host "JAVA_HOME=$env:JAVA_HOME"
& "$env:JAVA_HOME\bin\java.exe" -version
& "$env:ANDROID_HOME\platform-tools\adb.exe" devices -l
