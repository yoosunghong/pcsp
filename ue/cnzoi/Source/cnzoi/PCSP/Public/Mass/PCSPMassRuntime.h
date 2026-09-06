#pragma once

#include "CoreMinimal.h"

namespace PCSPMassRuntime
{
	inline float ScaleFromAgentRadius(const float AgentRadius)
	{
		constexpr float BaseAgentRadius = 35.f;
		return FMath::Max(0.1f, AgentRadius / BaseAgentRadius);
	}

	/** Movement preserves body-lengths per second when representation size changes. */
	inline float ScaledSpeed(const float BaseSpeed, const float AgentRadius)
	{
		return FMath::Max(10.f, BaseSpeed) * ScaleFromAgentRadius(AgentRadius);
	}

	/**
	 * AnimToTexture playback follows body-relative speed, not raw world speed.
	 * Scaling a mesh already scales its stride length, so multiplying playback by
	 * the representation scale a second time produces rapid, tiny-looking steps.
	 */
	inline float WalkAnimationPlayRate(const float WorldSpeed, const float AgentRadius,
		const float ReferenceSpeed = 260.f, const float ReferencePlayRate = 1.2f)
	{
		const float BodyRelativeSpeed = FMath::Max(0.f, WorldSpeed)
			/ ScaleFromAgentRadius(AgentRadius);
		return FMath::Clamp(ReferencePlayRate * BodyRelativeSpeed
			/ FMath::Max(10.f, ReferenceSpeed), 0.1f, 3.f);
	}

	inline bool IsInDecisionWindow(const int32 StableIndex, const int32 Start,
		const int32 Budget, const int32 Population)
	{
		return Population > 0 && ((StableIndex - Start + Population) % Population)
			< FMath::Min(Budget, Population);
	}

	inline float ZoneScore(const float Distance, const int32 Occupied, const int32 Capacity,
		const float TieBreak = 0.f)
	{
		if (Capacity <= 0 || Occupied >= Capacity) { return TNumericLimits<float>::Max(); }
		return Distance + static_cast<float>(FMath::Max(0, Occupied))
			/ static_cast<float>(Capacity) * 3000.f + TieBreak;
	}

	inline float InteractionDuration(const float AuthoredDuration, const float Scale,
		const int32 StableIndex)
	{
		return FMath::Clamp(AuthoredDuration * FMath::Max(0.f, Scale)
			+ (StableIndex % 5) * 0.04f, 0.65f, 1.6f);
	}
}
