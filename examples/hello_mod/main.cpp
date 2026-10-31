#include <mesdk/mesdk.hpp>

#include <windows.h>

#include <cmath>
#include <cstdio>
#include <string>

namespace {

FILE *logFile = nullptr;
mesdk::ProcessEventFn originalProcessEvent = nullptr;

void Log(const std::string &message) {
    OutputDebugStringA(("[hello_mod] " + message + "\n").c_str());
    if (logFile) {
        std::fprintf(logFile, "%s\n", message.c_str());
        std::fflush(logFile);
    }
}

// Runs for every UnrealScript function call in the game. Returning the original's result lets the
// call through; return 0 without calling it to block one.
int __fastcall ProcessEventDetour(Classes::UObject *object, void *edx, Classes::UFunction *function,
                                  void *params, void *result) {
    static Classes::UFunction *possessed = nullptr;
    if (!possessed) {
        possessed = Classes::UObject::FindObject<Classes::UFunction>(
            "Function Engine.PlayerController.Possess");
    }

    if (function == possessed) {
        Log("PlayerController.Possess called on " + object->GetFullName());
    }

    return originalProcessEvent(object, edx, function, params, result);
}

DWORD WINAPI Run(LPVOID) {
    logFile = std::fopen("hello_mod.log", "w");
    Log("hello_mod " MESDK_VERSION " loaded, SDK from " MESDK_MMULTIPLAYER_REPOSITORY "@" MESDK_MMULTIPLAYER_REF);

    const auto status = mesdk::Initialize();
    if (status != mesdk::Status::Ok) {
        Log(std::string("mesdk::Initialize failed: ") + mesdk::ToString(status));
        return 1;
    }

    Log("GObjects holds " + std::to_string(Classes::UObject::GetGlobalObjects().Num()) + " objects");

    if (const auto engine = mesdk::FindEngine()) {
        Log("Engine: " + engine->GetFullName());
    }

    if (!mesdk::HookProcessEvent(ProcessEventDetour, &originalProcessEvent)) {
        Log("Failed to hook ProcessEvent");
    }

    for (;;) {
        Sleep(5000);

        if (const auto pawn = mesdk::FindFirstObject<Classes::ATdPlayerPawn>()) {
            const auto &location = pawn->Location;
            char line[128];
            std::snprintf(line, sizeof(line), "Player at %.0f %.0f %.0f (%.1f m/s)", location.X,
                          location.Y, location.Z,
                          std::sqrt(pawn->Velocity.X * pawn->Velocity.X +
                                    pawn->Velocity.Y * pawn->Velocity.Y) / 100.0f);
            Log(line);
        }
    }
}

} // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        if (const auto thread = CreateThread(nullptr, 0, Run, nullptr, 0, nullptr)) {
            CloseHandle(thread);
        }
    }

    return TRUE;
}
