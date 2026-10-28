"""Shared small-vehicle detailing helpers."""
from original_compacts import TARP, IRON


def stowage(v, name, lo, hi):
    v.box(name, lo, hi, TARP, bevel=.18)
    x,y,z=lo;xx,yy,zz=hi
    for f in (.25,.75):
        at=x+(xx-x)*f
        # These straps run across Y; the generic beam helper only rotates in XZ.
        v.box(name+'STRAP', (at-.18,y-.02,zz-.16),
              (at+.18,yy+.02,zz+.20), IRON)
