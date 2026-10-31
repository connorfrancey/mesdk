#include <mesdk/mesdk.hpp>

#include <windows.h>

DWORD WINAPI Run(LPVOID) {
    const auto status = mesdk::Initialize();
    if (status != mesdk::Status::Ok) {
        MessageBoxA(nullptr, mesdk::ToString(status), "my_mod", MB_ICONERROR);
        return 1;
    }

    // The generated SDK is in namespace Classes
    if (const auto pawn = mesdk::FindFirstObject<Classes::ATdPlayerPawn>()) {
        OutputDebugStringA(("Player: " + pawn->GetFullName() + "\n").c_str());
    }

    return 0;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        CloseHandle(CreateThread(nullptr, 0, Run, nullptr, 0, nullptr));
    }

    return TRUE;
}
