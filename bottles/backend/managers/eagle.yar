// Eagle YARA Rules Database
// Copyright 2026 mirkobrombin <brombin94@gmail.com>
// SPDX-License-Identifier: GPL-3.0-only

// Game Engines
rule Unity_Mono {
    meta:
        category = "Engines"
        name = "Unity"
        description = "Unity Engine with Mono runtime"
    strings:
        $mono = "mono-2.0-bdwgc.dll" nocase
        $assembly = "Assembly-CSharp.dll" nocase
        $managed = "\\Managed\\" nocase
    condition:
        any of them
}

rule Unity_IL2CPP {
    meta:
        category = "Engines"
        name = "Unity IL2CPP"
        description = "Unity Engine with IL2CPP runtime"
    strings:
        $gameassembly = "GameAssembly.dll" nocase
        $il2cpp = "il2cpp" nocase
        $metadata = "global-metadata.dat" nocase
    condition:
        any of them
}

rule Unreal_Engine {
    meta:
        category = "Engines"
        name = "Unreal"
        description = "Unreal Engine 4/5"
    strings:
        $ue4 = "UE4-" nocase
        $ue5 = "UE5-" nocase
        $unrealcef = "UnrealCEFSubProcess" nocase
        $engine = "Engine\\Binaries" nocase
        $unrealgame = "UnrealGame" nocase
        $uproject = ".uproject" nocase
    condition:
        2 of them
}

rule Godot_Engine {
    meta:
        category = "Engines"
        name = "Godot"
        description = "Godot Game Engine"
    strings:
        $godot = "GODOT" nocase
        $godot_project = "project.godot" nocase
        $gdscript = "GDScript" nocase
        $godot_pck = "Godot Engine" nocase
    condition:
        2 of them
}

rule Source_Engine {
    meta:
        category = "Engines"
        name = "Source Engine"
        description = "Valve Source Engine"
    strings:
        $tier0 = "tier0.dll" nocase
        $vstdlib = "vstdlib.dll" nocase
        $vphysics = "vphysics.dll" nocase
        $source = "hl2.exe" nocase
    condition:
        2 of them
}

rule CryEngine {
    meta:
        category = "Engines"
        name = "CryEngine"
        description = "CryEngine"
    strings:
        $crysystem = "CrySystem.dll" nocase
        $cryrender = "CryRenderD3D" nocase
        $cryaction = "CryAction.dll" nocase
    condition:
        any of them
}

rule REDengine {
    meta:
        category = "Engines"
        name = "REDengine"
        description = "CD Projekt RED Engine"
    strings:
        $red = "REDengine" nocase
        $witcher = "witcher" nocase
        $cyberpunk = "Cyberpunk" nocase
        $archive = ".archive" nocase
    condition:
        2 of them
}

rule RPGMaker {
    meta:
        category = "Engines"
        name = "RPG Maker"
        description = "RPG Maker engine"
    strings:
        $rgss_header = "RGSSAD" nocase
        $rpg_rt = "RPG_RT.exe" nocase
        $rvdata = ".rvdata" nocase
        $rvdata2 = ".rvdata2" nocase
        $rgss3a = ".rgss3a" nocase
        $rpgmv_core = "js/rpg_core.js" nocase
        $rpgmv_managers = "js/rpg_managers.js" nocase
    condition:
        any of them
}

rule RenPy {
    meta:
        category = "Engines"
        name = "Ren'Py"
        description = "Ren'Py Visual Novel Engine"
    strings:
        $renpy = "renpy" nocase
        $rpa = ".rpa"
        $rpyc = ".rpyc"
    condition:
        any of them
}

// Frameworks
rule Electron {
    meta:
        category = "Frameworks"
        name = "Electron"
        description = "Electron/Chromium framework"
    strings:
        $electron = "electron.dll" nocase
        $asar = "app.asar" nocase
        $chromium = "libcef.dll" nocase
        $nwjs = "nw.dll" nocase
    condition:
        any of them
}

rule Qt_Framework {
    meta:
        category = "Frameworks"
        name = "Qt"
        description = "Qt Framework"
    strings:
        $qt5core = "Qt5Core.dll" nocase
        $qt6core = "Qt6Core.dll" nocase
        $qml = "Qt5Qml.dll" nocase
    condition:
        any of them
}


rule CEF {
    meta:
        category = "Frameworks"
        name = "CEF"
        description = "Chromium Embedded Framework"
    strings:
        $libcef = "libcef.dll" nocase
        $cef = "cef_" nocase
    condition:
        any of them
}


// Protection / Anti-Cheat
rule Denuvo {
    meta:
        category = "Protection"
        name = "Denuvo"
        description = "Denuvo Anti-Tamper"
    strings:
        $denuvo = "denuvo" nocase
        $steam_stub = "steam_api_o.dll" nocase
        $protect = "Protection-Steam.dll" nocase
    condition:
        any of them
}

rule VMProtect {
    meta:
        category = "Protection"
        name = "VMProtect"
        description = "VMProtect packer/virtualizer"
    strings:
        $vmp0 = ".vmp0"
        $vmp1 = ".vmp1"
        $vmprotect = "VMProtect" nocase
        $vmpsdk = "VMProtectSDK" nocase
    condition:
        any of them
}

rule Themida {
    meta:
        category = "Protection"
        name = "Themida"
        description = "Themida/WinLicense protector"
    strings:
        $themida = ".themida"
        $winlicense = "WinLicense" nocase
        $oreans = "Oreans" nocase
    condition:
        any of them
}

rule EasyAntiCheat {
    meta:
        category = "Protection"
        name = "EasyAntiCheat"
        description = "EAC Anti-Cheat"
    strings:
        $eac_dll = "EasyAntiCheat.dll" nocase
        $eac_x64 = "EasyAntiCheat_x64.dll" nocase
        $eac_sys = "EasyAntiCheat.sys" nocase
        $eac_setup = "EasyAntiCheat_Setup.exe" nocase
    condition:
        any of them
}

rule BattlEye {
    meta:
        category = "Protection"
        name = "BattlEye"
        description = "BattlEye Anti-Cheat"
    strings:
        $be_dll = "BEClient.dll" nocase
        $be_x64 = "BEClient_x64.dll" nocase
        $be_service = "BEService.exe" nocase
        $be_sys = "BattlEye.sys" nocase
        $be_core = "BattlEye Core" nocase
    condition:
        any of them
}

// Packers
rule UPX {
    meta:
        category = "Packers"
        name = "UPX"
        description = "UPX Packer"
    strings:
        $upx0 = "UPX0"
        $upx1 = "UPX1"
        $upx2 = "UPX!"
    condition:
        any of them
}

rule Enigma {
    meta:
        category = "Packers"
        name = "Enigma"
        description = "Enigma Protector"
    strings:
        $enigma = ".enigma"
        $enigma1 = "ENIGMA" nocase
    condition:
        any of them
}

rule ASPack {
    meta:
        category = "Packers"
        name = "ASPack"
        description = "ASPack Packer"
    strings:
        $aspack = ".aspack"
        $adata = ".adata"
    condition:
        any of them
}

// Runtimes
rule DotNet_Core {
    meta:
        category = "Runtimes"
        name = ".NET Core/5+"
        description = "Modern .NET Runtime"
    strings:
        $hostfxr = "hostfxr.dll" nocase
        $coreclr = "coreclr.dll" nocase
        $dotnet = "dotnet" nocase
        $runtimeconfig = ".runtimeconfig.json" nocase
    condition:
        any of them
}

rule DotNet_Framework {
    meta:
        category = "Runtimes"
        name = ".NET Framework"
        description = "Classic .NET Framework"
    strings:
        $mscoree = "mscoree.dll" nocase
        $mscorlib = "mscorlib.dll" nocase
        $clr = "clrjit.dll" nocase
    condition:
        any of them
}

rule Mono_Runtime {
    meta:
        category = "Runtimes"
        name = "Mono"
        description = "Mono Runtime"
    strings:
        $mono = "mono-2.0" nocase
        $mono_bdwgc = "mono-2.0-bdwgc.dll" nocase
        $monolib = "libmono" nocase
    condition:
        any of them
}

rule Java_Runtime {
    meta:
        category = "Runtimes"
        name = "Java"
        description = "Java Runtime Environment"
    strings:
        $jvm = "jvm.dll" nocase
        $java = "java.exe" nocase
        $jar = ".jar"
        $jni = "JNI_CreateJavaVM" nocase
    condition:
        any of them
}

rule Python_Embedded {
    meta:
        category = "Runtimes"
        name = "Python"
        description = "Embedded Python"
    strings:
        $python3 = "python3" nocase
        $python_dll = "python3" nocase
        $pyc = ".pyc"
    condition:
        any of them
}

// Media / Middleware
rule Bink_Video {
    meta:
        category = "Media"
        name = "Bink"
        description = "RAD Game Tools Bink Video"
    strings:
        $binkw32 = "binkw32.dll" nocase
        $binkw64 = "binkw64.dll" nocase
        $bink2 = "bink2w64.dll" nocase
        $bik = ".bik"
    condition:
        any of them
}

rule FMOD_Audio {
    meta:
        category = "Audio"
        name = "FMOD"
        description = "FMOD Audio Engine"
    strings:
        $fmod = "fmod.dll" nocase
        $fmod64 = "fmod64.dll" nocase
        $fmodstudio = "fmodstudio.dll" nocase
        $fev = ".fev"
        $fsb = ".fsb"
    condition:
        any of them
}

rule Wwise_Audio {
    meta:
        category = "Audio"
        name = "Wwise"
        description = "Audiokinetic Wwise"
    strings:
        $wwise = "AkSoundEngine" nocase
        $bnk = ".bnk"
        $wwisec = "wwise" nocase
    condition:
        any of them
}

rule Miles_Audio {
    meta:
        category = "Audio"
        name = "Miles"
        description = "RAD Game Tools Miles"
    strings:
        $miles32 = "miles32.dll" nocase
        $mss32 = "mss32.dll" nocase
        $miles64 = "miles64.dll" nocase
    condition:
        any of them
}

rule Havok {
    meta:
        category = "Physics"
        name = "Havok"
        description = "Havok Physics/Animation"
    strings:
        $havok = "hk" nocase
        $hkengine = "hkBase" nocase
        $hkanim = "hkaAnimation" nocase
    condition:
        2 of them
}

rule PhysX {
    meta:
        category = "Physics"
        name = "PhysX"
        description = "NVIDIA PhysX"
    strings:
        $physx = "PhysX" nocase
        $physx3 = "PhysX3" nocase
        $physxloader = "physxloader" nocase
        $physxcooking = "PhysXCooking" nocase
    condition:
        any of them
}

// Graphics
rule DirectX12 {
    meta:
        category = "Graphics"
        name = "DirectX 12"
        description = "DirectX 12 API"
    strings:
        $d3d12 = "d3d12.dll" nocase
        $dxil = "dxil.dll" nocase
        $d3d12core = "D3D12Core.dll" nocase
    condition:
        any of them
}

rule Vulkan_API {
    meta:
        category = "Graphics"
        name = "Vulkan"
        description = "Vulkan Graphics API"
    strings:
        $vulkan = "vulkan-1.dll" nocase
        $vk = "vkCreateInstance"
        $spirv = ".spv"
    condition:
        any of them
}

rule OpenGL {
    meta:
        category = "Graphics"
        name = "OpenGL"
        description = "OpenGL Graphics"
    strings:
        $opengl = "opengl32.dll" nocase
        $glew = "glew32.dll" nocase
        $glad = "gladLoadGL"
    condition:
        any of them
}

// DRM / Launchers
rule Steamworks {
    meta:
        category = "Social/DRM"
        name = "Steamworks"
        description = "Steam Integration"
    strings:
        $steam_api = "steam_api.dll" nocase
        $steam_api64 = "steam_api64.dll" nocase
        $steamclient = "steamclient.dll" nocase
        $steamappid = "steam_appid.txt" nocase
    condition:
        any of them
}

rule GOG_Galaxy {
    meta:
        category = "Social/DRM"
        name = "GOG Galaxy"
        description = "GOG Galaxy SDK"
    strings:
        $galaxy = "Galaxy.dll" nocase
        $galaxy64 = "Galaxy64.dll" nocase
        $galaxypeer = "GalaxyPeer" nocase
    condition:
        any of them
}

rule Epic_Online {
    meta:
        category = "Social/DRM"
        name = "Epic Online Services"
        description = "Epic Games SDK"
    strings:
        $eossdk = "EOSSDK" nocase
        $epic = "EpicOnlineServices" nocase
    condition:
        any of them
}

rule Discord_SDK {
    meta:
        category = "Social/DRM"
        name = "Discord"
        description = "Discord Game SDK"
    strings:
        $discord = "discord_game_sdk" nocase
        $discord_rpc = "discord-rpc" nocase
    condition:
        any of them
}

// Crypto
rule OpenSSL {
    meta:
        category = "Crypto"
        name = "OpenSSL"
        description = "OpenSSL Library"
    strings:
        $openssl = "OpenSSL" nocase
        $libssl = "libssl" nocase
        $libcrypto = "libcrypto" nocase
        $ssleay = "ssleay32.dll" nocase
    condition:
        any of them
}

// Installers
rule NSIS_Installer {
    meta:
        category = "Installer"
        name = "NSIS"
        description = "Nullsoft Scriptable Install System"
    strings:
        $nsis = "NSIS" nocase
        $nullsoft = "Nullsoft" nocase
        $nsisbi = "NSIS.Library" nocase
    condition:
        any of them
}

rule InnoSetup_Installer {
    meta:
        category = "Installer"
        name = "Inno Setup"
        description = "Inno Setup Installer"
    strings:
        $inno = "Inno Setup" nocase
        $inno_sig = "innosetup" nocase
        $iscc = "iscc.exe" nocase
    condition:
        any of them
}

rule InstallShield_Installer {
    meta:
        category = "Installer"
        name = "InstallShield"
        description = "InstallShield Installer"
    strings:
        $is = "InstallShield" nocase
        $flexera = "Flexera" nocase
        $is_cab = "_isetup/_setup.dll" nocase
    condition:
        any of them
}

rule MSI_Installer {
    meta:
        category = "Installer"
        name = "MSI"
        description = "Windows Installer Package"
    strings:
        $msi = "Windows Installer" nocase
        $msiexec = "msiexec" nocase
        $msidb = ".msi" nocase
    condition:
        any of them
}

// UI Frameworks
rule WPF_Framework {
    meta:
        category = "Frameworks"
        name = "WPF"
        description = "Windows Presentation Foundation"
    strings:
        $wpf = "PresentationFramework" nocase
        $wpf_core = "PresentationCore" nocase
        $wpf_ui = "WindowsBase" nocase
        $xaml = ".xaml" nocase
    condition:
        2 of them
}

rule WinForms_Framework {
    meta:
        category = "Frameworks"
        name = "WinForms"
        description = "Windows Forms"
    strings:
        $winforms = "System.Windows.Forms" nocase
        $forms_dll = "System.Windows.Forms.dll" nocase
    condition:
        any of them
}

rule MFC_Runtime {
    meta:
        category = "Runtimes"
        name = "MFC"
        description = "Microsoft Foundation Classes"
    strings:
        $mfc140 = "mfc140" nocase
        $mfc120 = "mfc120" nocase
        $mfc100 = "mfc100" nocase
        $mfcm = "mfcm140u.dll" nocase
    condition:
        any of them
}

rule ATL_Runtime {
    meta:
        category = "Runtimes"
        name = "ATL"
        description = "Active Template Library"
    strings:
        $atl140 = "atl140.dll" nocase
        $atl120 = "atl120.dll" nocase
        $atl = "ATL::CComObject" nocase
    condition:
        any of them
}

// Input Systems
rule XInput {
    meta:
        category = "Input"
        name = "XInput"
        description = "Xbox Controller API"
    strings:
        $xinput1_4 = "xinput1_4.dll" nocase
        $xinput1_3 = "xinput1_3.dll" nocase
        $xinput9 = "xinput9_1_0.dll" nocase
        $xinputget = "XInputGetState"
    condition:
        any of them
}

rule DirectInput {
    meta:
        category = "Input"
        name = "DirectInput"
        description = "Legacy DirectInput API"
    strings:
        $dinput = "dinput.dll" nocase
        $dinput8 = "dinput8.dll" nocase
        $dicreate = "DirectInputCreate"
    condition:
        any of them
}

rule RawInput {
    meta:
        category = "Input"
        name = "RawInput"
        description = "Raw Input API"
    strings:
        $rawinput = "GetRawInputData"
        $rawinputdev = "RegisterRawInputDevices"
    condition:
        any of them
}

// Problematic Technologies (Wine warnings)
rule UWP_App {
    meta:
        category = "Warning"
        name = "UWP/Modern API"
        description = "Uses Modern Windows APIs - Requires WinMetadata"
        severity = "high"
    strings:
        $uwp_core = "Windows.ApplicationModel.Core" nocase
        $uwp_activation = "Windows.ApplicationModel.Activation" nocase
        $uwp_package = "Windows.ApplicationModel.Package" nocase
        $appx_manifest = "AppxManifest.xml" nocase
        $msix_package = "MSIX Package" nocase
        $uwp_store = "Windows.Services.Store" nocase
    condition:
        2 of them
}

rule SecuROM_DRM {
    meta:
        category = "Warning"
        name = "SecuROM"
        description = "SecuROM DRM - Often problematic"
        severity = "high"
    strings:
        $securom = "SecuROM" nocase
        $sony_dadc = "Sony DADC" nocase
        $uaservice = "uaservice7.exe" nocase
    condition:
        2 of them
}

rule SafeDisc_DRM {
    meta:
        category = "Warning"
        name = "SafeDisc"
        description = "SafeDisc DRM - Will NOT work"
        severity = "critical"
    strings:
        $safedisc = "SafeDisc" nocase
        $macrovision = "Macrovision" nocase
        $secdrv = "secdrv.sys" nocase
        $drvmgt = "drvmgt.sys" nocase
    condition:
        ($secdrv or $drvmgt) or all of ($safedisc, $macrovision)
}

rule StarForce_DRM {
    meta:
        category = "Warning"
        name = "StarForce"
        description = "StarForce DRM - Will NOT work"
        severity = "critical"
    strings:
        $starforce = "StarForce" nocase
        $protect = "protect.dll" nocase
    condition:
        all of them
}

// Media
rule WMV_Codec {
    meta:
        category = "Media"
        name = "WMV/WMA"
        description = "Windows Media codecs"
    strings:
        $wmv = "wmvcore.dll" nocase
        $wma = "WMADEC" nocase
        $wmplayer = "Windows Media" nocase
    condition:
        any of them
}

rule QuickTime {
    meta:
        category = "Media"
        name = "QuickTime"
        description = "Apple QuickTime"
    strings:
        $qt = "QuickTime" nocase
        $qtcf = "QTCF.dll" nocase
        $mov = ".mov"
    condition:
        2 of them
}



rule Registry_Modifications {
    meta:
        description = "Contains Windows Registry modification strings"
        name = "Registry Keys"
        category = "Registry"
        severity = "info"
    strings:
        $reg1 = "REGEDIT4" ascii
        $reg2 = "Windows Registry Editor Version 5.00" ascii
        $key1 = "HKEY_LOCAL_MACHINE" ascii wide
        $key2 = "HKEY_CURRENT_USER" ascii wide
        $key3 = "HKLM\\" ascii wide
        $key4 = "HKCU\\" ascii wide
        $capture = /HK(LM|CU|EY_LOCAL_MACHINE|EY_CURRENT_USER)\\[a-zA-Z0-9_ \\-]{2,}/ ascii wide
    condition:
        $reg1 or $reg2 or 2 of ($key*) or $capture
}

rule Driver_Service {
    meta:
        description = "Attempts to install a Kernel Driver or Service"
        name = "Kernel Driver or Service"
        category = "Warning"
        severity = "high"
    strings:
        $svc1 = "CreateService" ascii wide
        $svc2 = "StartService" ascii wide
        $sys = ".sys" ascii wide
        $reg = "SYSTEM\\CurrentControlSet\\Services" ascii wide
    condition:
        ($svc1 and $svc2) or ($reg and $sys)
}

// Upscaling Technologies
rule Upscaling_Tech {
    meta:
        category = "Upscaling"
        name = "Upscaling Technology"
        description = "DLSS, FSR or XeSS detected"
    strings:
        $dlss = "nvngx_dlss.dll" nocase
        $dlss_framegen = "nvngx_dlssg.dll" nocase
        $fsr_dll = "ffx_fsr2_api_x64.dll" nocase
        $fsr_dx12 = "amd_fidelityfx_dx12.dll" nocase
        $fsr_vk = "amd_fidelityfx_vk.dll" nocase
        $xess = "libxess.dll" nocase
    condition:
        any of them
}

// Electron / Node.js Specifics
rule Node_Native_Module {
    meta:
        category = "System"
        name = "Native Modules"
        description = "Node.js Native Modules (FFI/Bindings)"
        severity = "info"
    strings:
        $ffi = "ffi-napi" nocase
        $ref = "ref-napi" nocase
        $bindings = "bindings" nocase
        $node_gyp = "node-gyp" nocase
        $koffi = "koffi" nocase
    condition:
        any of them
}

rule Node_System_Commands {
    meta:
        category = "System"
        name = "System Commands (Node)"
        description = "Executes system shell commands"
        severity = "high"
    strings:
        $exec = "child_process.exec"
        $spawn = "child_process.spawn"
        $execSync = "execSync"
        $spawnSync = "spawnSync"
        $cmd = "cmd.exe" nocase
        $powershell = "powershell" nocase
    condition:
        any of them
}

rule Node_Registry_Access {
    meta:
        category = "Registry"
        name = "Registry Access (Node)"
        description = "Accesses Windows Registry via Node.js"
        severity = "info"
    strings:
        $reg_query = "reg.exe query" nocase
        $reg_add = "reg.exe add" nocase
        $regedit = "regedit" nocase
    condition:
        any of them
}

rule Node_Kernel_Driver {
    meta:
        category = "System"
        name = "Kernel Driver (Node)"
        description = "Attempts to interact with Kernel Drivers"
        severity = "critical"
    strings:
        $create_file = "CreateFile"
        $device_io = "DeviceIoControl"
        $ioctl = "IOCTL_"
        $symbolic = "DefineDosDevice"
    condition:
        2 of them
}
