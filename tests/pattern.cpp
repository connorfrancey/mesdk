// Pattern scanning over local buffers.

#include <mesdk/mesdk.hpp>

#include <catch2/catch_test_macros.hpp>

namespace {

unsigned char buffer[] = {0x90, 0x8B, 0x0D, 0x11, 0x22, 0x33, 0x44, 0xC3};

} // namespace

TEST_CASE("FindPattern matches with wildcards", "[pattern]") {
    const auto match =
        Pattern::FindPattern(buffer, sizeof(buffer), "\x8B\x0D\x00\x00\x00\x00\xC3", "xx????x");
    CHECK(match == buffer + 1);
}

TEST_CASE("FindPattern matches at the start of the buffer", "[pattern]") {
    CHECK(Pattern::FindPattern(buffer, sizeof(buffer), "\x90\x8B", "xx") == buffer);
}

TEST_CASE("FindPattern returns nullptr without a match", "[pattern]") {
    CHECK(Pattern::FindPattern(buffer, sizeof(buffer), "\x8B\x0D\x11\x22\x33\x44\xCC",
                               "xxxxxxx") == nullptr);
}
