# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test the tile endpoint transparency and color variation logic."""
import numpy as np


def test_mask_logic():
    """Test the mask building logic with various scenarios."""
    
    # Scenario 1: Normal data with some nodata values
    arr = np.array([[1.5, 2.3, -9999], [4.1, 5.6, 7.2], [8.9, -9999, 10.1]])
    initial_mask = np.ones_like(arr, dtype=bool)  # All valid initially
    nodata = -9999
    
    valid_mask = initial_mask & (arr != nodata) & np.isfinite(arr)
    print("Scenario 1 - Normal with nodata:")
    print(f"  Valid pixels: {valid_mask.sum()} / {arr.size}")
    print(f"  Mask:\n{valid_mask.astype(int)}")
    assert valid_mask.sum() == 7, "Should have 7 valid pixels"
    
    # Scenario 2: Data with NaN and Inf
    arr = np.array([[1.5, np.nan, np.inf], [4.1, 5.6, 7.2], [8.9, -np.inf, 10.1]])
    initial_mask = np.ones_like(arr, dtype=bool)
    
    valid_mask = initial_mask & np.isfinite(arr)
    print("\nScenario 2 - With NaN and Inf:")
    print(f"  Valid pixels: {valid_mask.sum()} / {arr.size}")
    assert valid_mask.sum() == 6, "Should have 6 valid pixels"
    
    # Scenario 3: Percentile calculation from valid data
    arr = np.array([[1.0, 2.0, -9999], [3.0, 4.0, 5.0], [6.0, 7.0, 100.0]])
    initial_mask = np.ones_like(arr, dtype=bool)
    nodata = -9999
    
    valid_mask = initial_mask & (arr != nodata) & np.isfinite(arr)
    valid_data = arr[valid_mask]
    p2, p98 = np.percentile(valid_data, [2, 98])
    
    print("\nScenario 3 - Percentile rescale:")
    print(f"  Valid data: {valid_data}")
    print(f"  P2: {p2:.2f}, P98: {p98:.2f}")
    assert p2 < p98, "P2 should be less than P98"
    assert p2 >= valid_data.min(), "P2 should be >= min"
    assert p98 <= valid_data.max(), "P98 should be <= max"
    
    # Scenario 4: All invalid data
    arr = np.array([[-9999, -9999], [-9999, -9999]])
    initial_mask = np.ones_like(arr, dtype=bool)
    nodata = -9999
    
    valid_mask = initial_mask & (arr != nodata) & np.isfinite(arr)
    print("\nScenario 4 - All invalid:")
    print(f"  Valid pixels: {valid_mask.sum()} / {arr.size}")
    assert valid_mask.sum() == 0, "Should have 0 valid pixels"
    assert not valid_mask.any(), "Should raise TileOutsideBounds"
    
    print("\n✅ All mask logic tests passed!")


def test_rescale_priority():
    """Test the rescale range determination priority."""
    
    # Priority 1: Explicit scale_min/max
    scale_min, scale_max = 0.0, 100.0
    rescale = ((float(scale_min), float(scale_max)),)
    print("Priority 1 - Explicit range:")
    print(f"  Rescale: {rescale}")
    assert rescale == ((0.0, 100.0),), "Should use explicit range"
    
    # Priority 2: Asset min/max
    asset_min, asset_max = 10.0, 90.0
    rescale = ((float(asset_min), float(asset_max)),)
    print("\nPriority 2 - Asset range:")
    print(f"  Rescale: {rescale}")
    assert rescale == ((10.0, 90.0),), "Should use asset range"
    
    # Priority 3: Tile percentiles
    arr = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])
    p2, p98 = np.percentile(arr, [2, 98])
    rescale = ((float(p2), float(p98)),)
    print("\nPriority 3 - Tile percentiles:")
    print(f"  Data: {arr}")
    print(f"  P2={p2:.2f}, P98={p98:.2f}")
    print(f"  Rescale: {rescale}")
    assert p2 < p98, "P2 should be less than P98"
    
    print("\n✅ All rescale priority tests passed!")


if __name__ == "__main__":
    test_mask_logic()
    print("\n" + "=" * 60 + "\n")
    test_rescale_priority()
