#!/usr/bin/env python2
from __future__ import print_function

import sys
import numpy as np
import ply, collada

if __name__ == "__main__":
	fn1 = sys.argv[1] + ".walls.ply"
	fn2 = sys.argv[1] + ".filam.ply"

	filament_data = ply.PlyReader(fn2, verbose=True).read_data()
	
	mesh = collada.Collada()
	vertex_data = np.array(filament_data.vertex)
	vert_src = collada.source.FloatSource("filement-vertices", vertex_data, ('X', 'Y', 'Z'))

# vim:sw=4:ts=4
