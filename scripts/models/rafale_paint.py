"""Paints the Rafale's textures (euraf.tga, euraf_d.tga) with the jets' painter (typhoon_paint.py): its dark
grey low-visibility scheme and marks come in the layout file rafale.py writes.

    python3 scripts/models/rafale_paint.py build/models/EURAF_layout.json OUT_DIR [OCCLUSION.png]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import typhoon_paint  # noqa: E402

if __name__ == "__main__":
    typhoon_paint.main()
