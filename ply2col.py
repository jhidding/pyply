#!/usr/bin/env python2
from __future__ import print_function

import sys
import numpy as np

import ply, collada, quat

def _norm(a):
	return np.sqrt(np.square(a).sum())

def cilindrify(V, edges_, radius, n = 5):
	angles = np.arange(n) * (2*np.pi / n)

	X = np.arange(n)
	rectangles = np.c_[X, (X + 1) % n, (X + n), (X + 1) % n + n, X + n, (X + 1) % n]

	edges = np.array([e for e in edges_ if _norm(V[e[0]] - V[e[1]]) > 0])
	N = len(edges)
	p = np.zeros(shape=[N*2*n, 3], dtype=float)
	r = np.random.normal(0, 1, 3)

	for i, e in enumerate(edges):
		p1 = V[e[0]]
		p2 = V[e[1]]

		l = p2 - p1 ; l /= _norm(l)
		t = np.cross(r, l) ; t /= _norm(t)

		bi = i * 2 * n
		vertex_offsets = np.array([quat.rotation(l, a)(t) for a in angles]) * radius[i]
		p[bi:bi+2*n] = np.r_[(p1 + vertex_offsets), (p2 + vertex_offsets)]

	f = rectangles[np.newaxis,:,:] + (np.arange(N)*n*2)[:,np.newaxis,np.newaxis]
	return p, f

def test():
	V = np.random.normal(0, 1, [2,3])
	E = [[0, 1]]
	V, F = cilindrify(V, E, [1], 7)

	print(V, F)

	mesh = collada.Collada()

	vert_src = collada.source.FloatSource("filament-vertices", V, ('X', 'Y', 'Z'))
	geom = collada.geometry.Geometry(mesh, "filaments", "Filaments", [vert_src])
	input_list = collada.source.InputList()
	input_list.addInput(0, 'VERTEX', "#filament-vertices")

	edge_set = geom.createTriangleSet(F, input_list, "materialref")
	geom.primitives.append(edge_set)
	mesh.geometries.append(geom)

	# add material
	effect = collada.material.Effect("effect0", [], "phong", diffuse=(1, 0, 0))
	mat = collada.material.Material("material0", "mymaterial", effect)
	mesh.effects.append(effect)
	mesh.materials.append(mat)

	# collect stuff into scene
	matnode = collada.scene.MaterialNode("materialref", mat, inputs=[])
	geomnode = collada.scene.GeometryNode(geom, [matnode])
	node = collada.scene.Node("filament_node", children = [geomnode])

	myscene = collada.scene.Scene("LSS", [node])
	mesh.scenes.append(myscene)
	mesh.scene = myscene

	mesh.write('test.dae')

def convert_filaments():
	fn1 = sys.argv[1] + ".walls.ply"
	fn2 = sys.argv[1] + ".filam.ply"

	filament_data = ply.PlyReader(fn2, verbose=True).read_data()
	
	# data source for edges
	vertex_data = np.array(filament_data.vertex) 
	index_data = np.array([[e.vertex1, e.vertex2] for e in filament_data.edge if e.density > 200])
	density_data = np.array([e.density for e in filament_data.edge if e.density > 200])
	print("cilindrifying edges ...", end='')
	c_verts, f = cilindrify(vertex_data, index_data, np.sqrt(density_data) / 100, 10)
	print("done")

	mesh = collada.Collada()

	vert_src = collada.source.FloatSource("filament-vertices", c_verts, ('X', 'Y', 'Z'))
	geom = collada.geometry.Geometry(mesh, "filaments", "Filaments", [vert_src])
	input_list = collada.source.InputList()
	input_list.addInput(0, 'VERTEX', "#filament-vertices")

	edge_set = geom.createTriangleSet(f, input_list, "materialref")
	geom.primitives.append(edge_set)
	mesh.geometries.append(geom)

	# add material
	effect = collada.material.Effect("effect0", [], "phong", diffuse=(1, 0, 0), specular=(0, 1, 0))
	mat = collada.material.Material("material0", "mymaterial", effect)
	mesh.effects.append(effect)
	mesh.materials.append(mat)

	# collect stuff into scene
	matnode = collada.scene.MaterialNode("materialref", mat, inputs=[])
	geomnode = collada.scene.GeometryNode(geom, [matnode])
	node = collada.scene.Node("filament_node", children = [geomnode])

	myscene = collada.scene.Scene("LSS", [node])
	mesh.scenes.append(myscene)
	mesh.scene = myscene

	mesh.write('test.dae')

def cut(x):
	if x < 0: 
		return 0
	if x > 1: 
		return 1
	return x

def pal1(x):
	return (cut(x),cut(2*(x-0.5)),cut(x**2-0.5))

def convert_walls():
	fn1 = sys.argv[1] + ".walls.ply"
	fn2 = sys.argv[1] + ".filam.ply"

	wall_data = ply.PlyReader(fn1, verbose=True).read_data()
	
	# data source for edges
	vertex_data = np.array(wall_data.vertex) 
	index_data = [np.array(e.vertex_index) for e in wall_data.face]
	density_data = np.array([e.density for e in wall_data.face])

	N_eff = 12
	levels = np.linspace(30, 200, N_eff-1)
	c0 = lambda x: x <= levels[0]
	cn = lambda x: x > levels[-1]
	criteria = [c0] + [(lambda x: levels[_i] < x <= levels[_i+1]) for _i in range(N_eff-2)] + [cn]

	mesh = collada.Collada()
	vert_src = collada.source.FloatSource("wall-vertices", vertex_data, ('X', 'Y', 'Z'))

	geom = collada.geometry.Geometry(mesh, "walls", "walls", [vert_src])
	input_list = collada.source.InputList()
	input_list.addInput(0, 'VERTEX', "#wall-vertices")

	for i in range(N_eff):
		subdata = [np.array(f.vertex_index) for f in wall_data.face if criteria[i](f.density)]
		face_set = geom.createPolygons(subdata, input_list, "materialref-{0}".format(i))
		geom.primitives.append(face_set)
	
	mesh.geometries.append(geom)
	# add material
	for i in range(N_eff):
		print(pal1(i/N_eff))

	effects = [collada.material.Effect("wall-effect-{0}".format(i), [], "phong", 
				diffuse=pal1(float(i)/N_eff), transparency=float(i)/N_eff)
		for i in range(N_eff)]
	materials = [collada.material.Material("wall-{0}".format(i), "level {0}".format(i), effects[i])
		for i in range(N_eff)]
	
	for i in range(N_eff):
		mesh.effects.append(effects[i])
		mesh.materials.append(materials[i])

	# collect stuff into scene
	matnode = [collada.scene.MaterialNode("materialref-{0}".format(i), materials[i], inputs=[])
		for i in range(N_eff)]

	geomnode = collada.scene.GeometryNode(geom, matnode)
	node = collada.scene.Node("wall_node", children = [geomnode])

	myscene = collada.scene.Scene("LSS", [node])
	mesh.scenes.append(myscene)
	mesh.scene = myscene

	mesh.write('test.dae')

def wall_hist():
	print("reading ...") ; sys.stdout.flush()
	fn1 = sys.argv[1] + ".walls.ply"
	fn2 = sys.argv[1] + ".filam.ply"

	wall_data = ply.PlyReader(fn1, verbose=True).read_data()
	print("done") ; sys.stdout.flush()

	# data source for edges
	vertex_data = np.array(wall_data.vertex) 
	index_data = [np.array(e.vertex_index) for e in wall_data.face if e.density > 25]
	density_data = np.array([e.density for e in wall_data.face if e.density > 25])


	hist, bin_edges = np.histogram(density_data, bins=1000)
	bins = (bin_edges[1:] + bin_edges[:-1]) / 2
	for i in np.c_[hist, bins]:
		print(" ".join([str(s) for s in i]))

if __name__ == "__main__":
	convert_walls()

# vim:sw=4:ts=4
