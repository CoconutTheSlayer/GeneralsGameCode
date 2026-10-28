"""Shared EU art direction: readable armour planes and restrained edge wear at the game camera.

Constants also load inside Blender; the building compositor imports NumPy only when called by a painter.
"""

ARMOUR = [(134, 150, 164), (88, 104, 120), (174, 186, 196)]
EDGE_SHADOW = (48, 59, 72)
EDGE_LIGHT = (164, 180, 192)
AIRFRAME_SHADOW = (66, 78, 92)
AIRFRAME_LIGHT = (180, 192, 204)


def building_light(colour, ao, height, stains):
    """Lift broad surfaces while keeping dark fittings and contact shadows distinct.

    Inputs are baked RGB colour in 0..255 and scalar masks in 0..1. Night windows,
    powered effects and damage are composed afterwards by each building's painter.
    """
    import numpy as np

    height = np.clip(height, 0, 1)
    # Slightly cleaner planes let the plaster, steel and concrete separate at normal zoom.
    lit = colour * (0.40 + 0.60 * ao) * (0.93 + 0.14 * stains) * (0.84 + 0.30 * np.sqrt(height))
    # Keep the established compensation for the game's warm, dim lighting.
    return lit * np.array([1.16, 1.20, 1.30])
