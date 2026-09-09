#pragma once

#include "Math/UnrealMathUtility.h"
#include "Containers/UnrealString.h"

namespace CyclingPhysicsValidation
{
	inline bool CheckFinite(double Value, const FString& FieldName, FString& OutError)
	{
		if (!FMath::IsFinite(Value))
		{
			OutError = FString::Printf(TEXT("%s must be a finite number"), *FieldName);
			return false;
		}
		return true;
	}

	inline bool CheckPositive(double Value, const FString& FieldName, FString& OutError)
	{
		if (!CheckFinite(Value, FieldName, OutError))
		{
			return false;
		}
		if (Value <= 0.0)
		{
			OutError = FString::Printf(TEXT("%s must be greater than zero"), *FieldName);
			return false;
		}
		return true;
	}

	inline bool CheckNonNegative(double Value, const FString& FieldName, FString& OutError)
	{
		if (!CheckFinite(Value, FieldName, OutError))
		{
			return false;
		}
		if (Value < 0.0)
		{
			OutError = FString::Printf(TEXT("%s must not be negative"), *FieldName);
			return false;
		}
		return true;
	}

	inline bool CheckClosedUnitInterval(double Value, const FString& FieldName, FString& OutError)
	{
		if (!CheckFinite(Value, FieldName, OutError))
		{
			return false;
		}
		if (Value < 0.0 || Value > 1.0)
		{
			OutError = FString::Printf(TEXT("%s must be in the interval [0, 1]"), *FieldName);
			return false;
		}
		return true;
	}

	inline bool CheckOpenUpperUnitInterval(double Value, const FString& FieldName, FString& OutError)
	{
		if (!CheckFinite(Value, FieldName, OutError))
		{
			return false;
		}
		if (Value <= 0.0 || Value > 1.0)
		{
			OutError = FString::Printf(TEXT("%s must be in the interval (0, 1]"), *FieldName);
			return false;
		}
		return true;
	}
}
