#pragma once

/**
 * @file mesdk.hpp
 * @brief Runtime helpers for the Mirror's Edge (1.0) SDK from mmultiplayer.
 *
 * The generated SDK (`ME_SDK.hpp`, namespace `Classes`) mirrors the game's classes, but its two
 * globals, `Classes::FName::GNames` and `Classes::UObject::GObjects`, are null until something
 * locates them in the running game. mesdk::Initialize() does that with the same signatures the
 * mmultiplayer client uses, so code running inside MirrorsEdge.exe (an injected DLL) can call
 * `StaticClass()`, `FindObject()` and the script function wrappers.
 *
 * @code
 * #include <mesdk/mesdk.hpp>
 *
 * if (mesdk::Initialize() == mesdk::Status::Ok) {
 *     auto engine = mesdk::FindEngine();
 * }
 * @endcode
 */

#include <ME_SDK.hpp>

#include <mesdk/hook.h>
#include <mesdk/pattern.h>
#include <mesdk/version.hpp>

namespace mesdk {

/// Result of Initialize().
enum class Status {
    Ok,               ///< GNames and GObjects were found
    ModuleNotFound,   ///< The module passed to Initialize() is not loaded
    GNamesNotFound,   ///< The GNames signature did not match (not Mirror's Edge 1.0?)
    GObjectsNotFound, ///< The GObjects signature did not match (not Mirror's Edge 1.0?)
};

/// Human readable name of a Status, for logs and message boxes.
const char *ToString(Status status);

/**
 * @brief Locates GNames and GObjects in a loaded module and stores them in the SDK.
 *
 * @param module Module to scan, as passed to GetModuleHandleA. nullptr scans the process
 *               executable (MirrorsEdge.exe), which is what you want from an injected DLL.
 *
 * Safe to call more than once; later calls rescan. Call it from inside the game process only.
 */
Status Initialize(const char *module = nullptr);

/// True once Initialize() has succeeded.
bool IsInitialized();

/**
 * @brief Address of UObject::ProcessEvent in the game, or nullptr if not found.
 *
 * Every script function call goes through ProcessEvent, so hooking it (see HookProcessEvent())
 * lets you observe or block game events.
 */
void *FindProcessEvent(const char *module = nullptr);

/**
 * @brief Signature of UObject::ProcessEvent (a __thiscall, hooked through __fastcall).
 *
 * `edx` is unused; it is there so a __fastcall function can stand in for the __thiscall original.
 */
using ProcessEventFn = int(__fastcall *)(Classes::UObject *object, void *edx,
                                         Classes::UFunction *function, void *params,
                                         void *result);

/**
 * @brief Detours UObject::ProcessEvent to @p detour.
 *
 * @param detour   Your replacement. Call @p original from it to let the event through.
 * @param original Receives the trampoline to the original function.
 * @return false if ProcessEvent was not found or the hook could not be installed.
 */
bool HookProcessEvent(ProcessEventFn detour, ProcessEventFn *original);

/// Removes a hook installed by HookProcessEvent().
bool UnhookProcessEvent(ProcessEventFn original);

/**
 * @brief Calls @p fn for every live object that IsA @p T, skipping class default objects.
 *
 * Stops early when @p fn returns false. Requires Initialize().
 */
template <class T, class Fn>
void ForEachObject(Fn &&fn) {
    if (!IsInitialized()) {
        return;
    }

    const auto cls = T::StaticClass();
    const auto &objects = Classes::UObject::GetGlobalObjects();
    for (size_t i = 0; i < objects.Num(); ++i) {
        const auto object = objects.GetByIndex(i);
        if (!object || !object->IsA(cls) || object->GetName().rfind("Default__", 0) == 0) {
            continue;
        }

        if (!fn(static_cast<T *>(object))) {
            return;
        }
    }
}

/// First live object that IsA @p T (class default objects excluded), or nullptr.
template <class T>
T *FindFirstObject() {
    T *found = nullptr;
    ForEachObject<T>([&](T *object) {
        found = object;
        return false;
    });

    return found;
}

/// The running UTdGameEngine (the one outered to "Transient"), or nullptr. Not cached.
Classes::UTdGameEngine *FindEngine();

} // namespace mesdk
