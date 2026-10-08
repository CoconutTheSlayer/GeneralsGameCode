"""Paints the Tornado's textures (eutor.tga, eutor_d.tga) with the jets' painter (typhoon_paint.py): its splinter
camouflage and marks come in the layout file tornado.py writes.

    python3 scripts/models/tornado_paint.py build/models/EUTORN_layout.json OUT_DIR [OCCLUSION.png]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import typhoon_paint  # noqa: E402

if __name__ == "__main__":
    typhoon_paint.main()
