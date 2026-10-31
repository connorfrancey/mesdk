// The runtime helpers' behaviour outside the game: no signature can match, so nothing initialises.

#include <mesdk/mesdk.hpp>

#include <catch2/catch_test_macros.hpp>

#include <string>

TEST_CASE("Initialize fails outside the game", "[runtime]") {
    SECTION("unknown module") {
        CHECK(mesdk::Initialize("this_module_does_not_exist.dll") ==
              mesdk::Status::ModuleNotFound);
    }

    SECTION("module without the signatures") {
        CHECK(mesdk::Initialize("kernel32.dll") == mesdk::Status::GNamesNotFound);
    }

    CHECK_FALSE(mesdk::IsInitialized());
}

TEST_CASE("Lookups return nothing when not initialised", "[runtime]") {
    REQUIRE_FALSE(mesdk::IsInitialized());

    CHECK(mesdk::FindProcessEvent("kernel32.dll") == nullptr);
    CHECK(mesdk::FindEngine() == nullptr);
    CHECK(mesdk::FindFirstObject<Classes::ATdPlayerPawn>() == nullptr);

    int visited = 0;
    mesdk::ForEachObject<Classes::UObject>([&](Classes::UObject *) {
        ++visited;
        return true;
    });
    CHECK(visited == 0);
}

// HookProcessEvent() itself isn't called: it scans the test executable, whose .rdata holds the
// signature bytes, so it could "find" ProcessEvent in the pattern constant.
TEST_CASE("Unhooking without a hook fails", "[runtime]") {
    CHECK_FALSE(mesdk::UnhookProcessEvent(nullptr));
}

TEST_CASE("Status names", "[runtime]") {
    CHECK(std::string(mesdk::ToString(mesdk::Status::Ok)) == "Ok");
    CHECK(std::string(mesdk::ToString(mesdk::Status::ModuleNotFound)) == "Module not found");
    CHECK(std::string(mesdk::ToString(mesdk::Status::GNamesNotFound)) == "Failed to find GNames");
    CHECK(std::string(mesdk::ToString(mesdk::Status::GObjectsNotFound)) ==
          "Failed to find GObjects");
}

TEST_CASE("Version macros", "[runtime]") {
    CHECK_FALSE(std::string(MESDK_VERSION).empty());
    CHECK_FALSE(std::string(MESDK_MMULTIPLAYER_REPOSITORY).empty());
    CHECK_FALSE(std::string(MESDK_MMULTIPLAYER_REF).empty());
}
