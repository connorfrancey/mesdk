#include <mesdk/mesdk.hpp>

#include <windows.h>
#include <psapi.h>

namespace {

// Signatures from mmultiplayer's Engine::Initialize (Client/engine.cpp). Each matches an instruction
// that loads the global's address, which sits 2 bytes into the match: mov reg, [imm32].
constexpr char GNamesPattern[] = "\x8B\x0D\x00\x00\x00\x00\x8B\x84\x24\x00\x00\x00\x00\x8B\x04\x81";
constexpr char GNamesMask[] = "xx????xxx????xxx";

constexpr char GObjectsPattern[] = "\x8B\x15\x00\x00\x00\x00\x8B\x0C\xB2\x8D\x44\x24\x30";
constexpr char GObjectsMask[] = "xx????xxxxxxx";

constexpr char ProcessEventPattern[] = "\x56\x8B\xF1\x8B\x0D\x00\x00\x00\x00\x85\xC9\x74\x09";
constexpr char ProcessEventMask[] = "xxxxx????xxxx";

bool initialized = false;

// The hook overwrites the start of ProcessEvent, so its signature no longer matches afterwards
void *hookedProcessEvent = nullptr;

void *ReadOperand(void *match) {
    return *reinterpret_cast<void **>(reinterpret_cast<unsigned char *>(match) + 2);
}

} // namespace

const char *mesdk::ToString(Status status) {
    switch (status) {
    case Status::Ok:
        return "Ok";
    case Status::ModuleNotFound:
        return "Module not found";
    case Status::GNamesNotFound:
        return "Failed to find GNames";
    case Status::GObjectsNotFound:
        return "Failed to find GObjects";
    }

    return "Unknown status";
}

mesdk::Status mesdk::Initialize(const char *module) {
    initialized = false;

    if (!GetModuleHandleA(module)) {
        return Status::ModuleNotFound;
    }

    const auto names = Pattern::FindPattern(module, GNamesPattern, GNamesMask);
    if (!names) {
        return Status::GNamesNotFound;
    }

    const auto objects = Pattern::FindPattern(module, GObjectsPattern, GObjectsMask);
    if (!objects) {
        return Status::GObjectsNotFound;
    }

    Classes::FName::GNames = static_cast<decltype(Classes::FName::GNames)>(ReadOperand(names));
    Classes::UObject::GObjects =
        static_cast<decltype(Classes::UObject::GObjects)>(ReadOperand(objects));

    initialized = Classes::FName::GNames && Classes::UObject::GObjects;
    return Status::Ok;
}

bool mesdk::IsInitialized() {
    return initialized;
}

void *mesdk::FindProcessEvent(const char *module) {
    return Pattern::FindPattern(module, ProcessEventPattern, ProcessEventMask);
}

bool mesdk::HookProcessEvent(ProcessEventFn detour, ProcessEventFn *original) {
    const auto target = FindProcessEvent();
    if (!target || !original) {
        return false;
    }

    if (!Hook::TrampolineHook(reinterpret_cast<void *>(detour), target,
                              reinterpret_cast<void **>(original))) {
        return false;
    }

    hookedProcessEvent = target;
    return true;
}

bool mesdk::UnhookProcessEvent(ProcessEventFn original) {
    if (!hookedProcessEvent || !original) {
        return false;
    }

    if (!Hook::UnTrampolineHook(hookedProcessEvent, reinterpret_cast<void *>(original))) {
        return false;
    }

    hookedProcessEvent = nullptr;
    return true;
}

Classes::UTdGameEngine *mesdk::FindEngine() {
    Classes::UTdGameEngine *engine = nullptr;
    ForEachObject<Classes::UTdGameEngine>([&](Classes::UTdGameEngine *candidate) {
        if (candidate->Outer && candidate->Outer->GetName() == "Transient") {
            engine = candidate;
            return false;
        }

        return true;
    });

    return engine;
}
