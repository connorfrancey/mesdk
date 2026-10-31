// Layout checks against the offsets recorded in the generated headers. The static_asserts are the
// important part: if this file compiles, the SDK's packing matches the game's memory with this
// compiler. The test case only makes them show up in the test report.

#include <mesdk/mesdk.hpp>

#include <catch2/catch_test_macros.hpp>

#include <cstddef>

using namespace Classes;

#if defined(__GNUC__)
#pragma GCC diagnostic ignored "-Winvalid-offsetof"
#endif

static_assert(sizeof(void *) == 4, "Mirror's Edge is 32-bit");

static_assert(sizeof(FVector) == 0x0C, "FVector");
static_assert(sizeof(FRotator) == 0x0C, "FRotator");
static_assert(sizeof(FName) == 0x08, "FName");
static_assert(sizeof(TArray<int>) == 0x0C, "TArray");

static_assert(sizeof(UObject) == 0x3C, "UObject");
static_assert(offsetof(UObject, Outer) == 0x28, "UObject::Outer");
static_assert(offsetof(UObject, Name) == 0x2C, "UObject::Name");
static_assert(offsetof(UObject, Class) == 0x34, "UObject::Class");

static_assert(sizeof(AActor) == 0x1C0, "AActor");
static_assert(offsetof(AActor, WorldInfo) == 0x9C, "AActor::WorldInfo");
static_assert(offsetof(AActor, Location) == 0xE8, "AActor::Location");
static_assert(offsetof(AActor, Velocity) == 0x100, "AActor::Velocity");

static_assert(sizeof(APawn) == 0x3C4, "APawn");
static_assert(offsetof(APawn, LandMovementState) == 0x330, "APawn::LandMovementState");

static_assert(sizeof(ATdPlayerPawn) == 0x9E4, "ATdPlayerPawn");

TEST_CASE("SDK layout matches the game", "[layout]") {
    STATIC_CHECK(sizeof(void *) == 4);
    STATIC_CHECK(sizeof(UObject) == 0x3C);
    STATIC_CHECK(sizeof(AActor) == 0x1C0);
    STATIC_CHECK(sizeof(APawn) == 0x3C4);
    STATIC_CHECK(sizeof(ATdPlayerPawn) == 0x9E4);
}
