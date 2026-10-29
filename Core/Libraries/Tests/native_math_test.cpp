// Native simulation must retain the float rounding used by existing replays.
#include <WWMath/wwmath.h>
#include <bit>
#include <cstdint>
#include <cstdio>

static bool same(const char *name, float actual, float expected)
{
	if (std::bit_cast<uint32_t>(actual) == std::bit_cast<uint32_t>(expected)) return true;
	std::fprintf(stderr, "%s changed native rounding: %a != %a\n", name, actual, expected);
	return false;
}

int main()
{
	unsigned checks = 0;
	for (int i = -4096; i <= 4096; ++i)
	{
		const float x = i / 4097.0f;
		const float angle = x * 31.0f;
		if (!same("acos", WWMath::Acos(x), rts_acosf(x)) ||
			!same("asin", WWMath::Asin(x), rts_asinf(x)) ||
			!same("atan", WWMath::Atan(angle), rts_atanf(angle)) ||
			!same("atan2", WWMath::Atan2(x, 0.37f), rts_atan2f(x, 0.37f)) ||
			!same("cos", WWMath::Cos(angle), rts_cosf(angle)) ||
			!same("sin", WWMath::Sin(angle), rts_sinf(angle)) ||
			!same("tan", WWMath::Tan(angle), rts_tanf(angle))) return 1;
		checks += 7;
		if (WWMath::Float_To_Int_Chop(x) != (int)x ||
			WWMath::Float_To_Int_Floor(x) != (int)floorf(x)) return 2;
		checks += 2;
	}
	std::printf("%u native math compatibility checks passed\n", checks);
	return 0;
}
