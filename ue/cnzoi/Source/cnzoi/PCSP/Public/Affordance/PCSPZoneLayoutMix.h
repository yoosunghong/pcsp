#pragma once

#include "CoreMinimal.h"

/** Seeded spatial mixing: preserve every authored zone, remove category rows. */
namespace PCSPZoneLayoutMix
{
	inline int32 NeighborPenalty(const TArray<int32>& Order,
		const TArray<int32>& Categories, const int32 Columns)
	{
		int32 Penalty = 0;
		for (int32 Index = 0; Index < Order.Num(); ++Index)
		{
			if (Index % Columns > 0 && Categories[Order[Index]] == Categories[Order[Index - 1]])
			{
				++Penalty;
			}
			if (Index >= Columns && Categories[Order[Index]] == Categories[Order[Index - Columns]])
			{
				++Penalty;
			}
		}
		return Penalty;
	}

	inline TArray<int32> BuildOrder(const TArray<int32>& Categories, const int32 Columns,
		const int32 Seed)
	{
		TArray<int32> Order;
		for (int32 Index = 0; Index < Categories.Num(); ++Index) { Order.Add(Index); }
		if (Columns <= 0) { return Order; }
		FRandomStream Random(Seed);
		for (int32 Index = Order.Num() - 1; Index > 0; --Index)
		{
			Order.Swap(Index, Random.RandRange(0, Index));
		}
		// Repair adjacent matches without re-sampling or losing rare categories.
		// The random permutation remains the tie-breaker, so seeds stay meaningful.
		int32 Penalty = NeighborPenalty(Order, Categories, Columns);
		for (int32 Pass = 0; Pass < 4 && Penalty > 0; ++Pass)
		{
			bool bImproved = false;
			for (int32 Left = 0; Left < Order.Num() && Penalty > 0; ++Left)
			{
				for (int32 Right = Left + 1; Right < Order.Num(); ++Right)
				{
					if (Categories[Order[Left]] == Categories[Order[Right]]) { continue; }
					Order.Swap(Left, Right);
					const int32 CandidatePenalty = NeighborPenalty(Order, Categories, Columns);
					if (CandidatePenalty < Penalty)
					{
						Penalty = CandidatePenalty;
						bImproved = true;
						break;
					}
					Order.Swap(Left, Right);
				}
			}
			if (!bImproved) { break; }
		}
		return Order;
	}
}
