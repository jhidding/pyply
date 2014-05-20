#!/usr/bin/env python2
from __future__ import print_function

import sys, itertools, struct

from exceptions import RuntimeError, TypeError, NotImplementedError
from collections import namedtuple

def partition(pred, data,
		tee  = itertools.tee, 
		fit = itertools.ifilter, 
		fif = itertools.ifilterfalse):
	t1, t2 = itertools.tee(data)
	return fit(pred, t1), fif(pred, t2)

class ReaderIterator:
	def __init__(self, readers, data, offset):
		self.readers = readers
		self.data = data
		self.offset = offset

	def __iter__(self):
		return self

	def next(self):
		r = self.readers.next()
		result, self.offset = r(self.data, self.offset)
		return result

class PlyElement:
	def __init__(self, name, count, properties):
		self.name = name
		self.count = count
		self.properties = properties
	
	def __str__(self):
		return "element: {obj.name} [{obj.count}]\n\t".format(obj=self) + \
			   "\n\t".join([str(p) for p in self.properties])

	def make_reader(self, file_format):
		readers     = [p.make_reader(file_format) for p in self.properties]
		field_names = [p.name for p in self.properties]
		Element     = namedtuple(self.name, field_names)

		def read_item(data, offset):
			i = ReaderIterator(iter(readers), data, offset)
			result = Element(*i)
			return result, i.offset

		def reader(data, offset, n = self.count):
			i = ReaderIterator(itertools.repeat(read_item, n), data, offset)
			result = list(i)
			return result, i.offset

		return reader
		
class PlyProperty:
	def __init__(self, name, dtype):
		self.name = name
		self.dtype = dtype

	def __str__(self):
		if self.is_list():
			return "property: {obj.name} [list of {ltype}]".format(
                    obj=self, ltype=self.dtype[-1])
		else:
			return "property: {obj.name} [{dtype}]".format(
                    obj=self, dtype=self.dtype[0])

	def is_list(self):
		return self.dtype[0] == 'list'

	def make_reader(self, file_format):
		ff = file_format.split('_')
		if ff[0] == 'binary' and ff[1] in ['little', 'big']:
			if self.is_list():
				return self.make_binary_list_reader(self.dtype[1], self.dtype[2], ff[1])
			else:
				return self.make_binary_reader(self.dtype[0], ff[1])
		
		if ff[0] == 'ascii':
			return self.make_ascii_reader()

		raise RuntimeError("Invalid file format specifier: " + file_format)

	def make_binary_reader(self, dtype, endianness, varsize = False):
		tr = { 'little': '<', 'big':    '>',
			   'uchar':  'B', 'char':   'b',
			   'ushort': 'H', 'short':  'h',
			   'uint':   'I', 'int':    'i',
			   'float':  'f', 'double': 'd'  }

		if varsize:		
			fmt  = "{endianness}{count}{dtype}".format(endianness = tr[endianness], count = '{count}', dtype = tr[dtype])

			def reader(data, offset, count = 1):
				_fmt = fmt.format(count = count)
				size = struct.calcsize(_fmt)
				return list(struct.unpack(_fmt, data[offset:offset+size])), offset+size

			return reader

		else:
			fmt  = "{endianness}{dtype}".format(endianness = tr[endianness], dtype = tr[dtype])
			size = struct.calcsize(fmt)

			def reader(data, offset):
				return struct.unpack(fmt, data[offset:offset+size])[0], offset+size
				
			return reader

	def make_binary_list_reader(self, stype, dtype, endianness):
		size_reader = self.make_binary_reader(stype, endianness)
		list_reader = self.make_binary_reader(dtype, endianness, varsize=True)

		def reader(data, offset):
			count, offset = size_reader(data, offset)
			return list_reader(data, offset, count)

		return reader
			
	def make_ascii_reader(self):
		raise NotImplementedError("For the moment this module reads binary only.")

class PlyReader:
	def __init__(self, f, verbose = False):
		self.verbose = verbose
		
		if isinstance(f, str):
			self.f = open(f, 'rb')
		elif isinstance(f, file):
			self.f = f
		else:
			raise TypeError("PlyReader accepts only string or file argument.")

		self.read_header()
			
	def _read_header_lines(self):
		while True:
			l = self.f.readline()[:-1]
			if l == "end_header":
				return
			else:
				yield l

	def _parse_header_elements(self, lines):
		while lines:
			line = lines.pop(0)
			if line[0] != "element" and len(line[1]) == 2:
				raise RuntimeError("Invalid .ply file: expected keyword 'element'"
                        " with two arguments.")

			ptys = []
			while lines and lines[0][0] == "property":
				p_line = lines.pop(0)[1]
				ptys.append(PlyProperty(p_line[-1], p_line[:-1]))

			yield PlyElement(line[1][0], int(line[1][1]), ptys)

	def read_header(self):
		# the first line of a .ply file is 'ply\n'
		first_line = self.f.readline()
		if first_line != "ply\n":
			raise RuntimeError("This is not a valid .ply file.")
		
		# read other lines
		all_lines = [l for l in self._read_header_lines()]
		parted_lines = [l.partition(" ") for l in all_lines]

		# comments
		comment_lines = [l[2] for l in parted_lines if l[0] == "comment"]
		if self.verbose:
			for l in comment_lines:
				print("comment:  ", l)

		other_lines = [(l[0], l[2].split()) for l in parted_lines if l[0] != "comment"]

		# file format
		fmt = other_lines.pop(0)
		if fmt[0] != "format":
			raise RuntimeError("The first non-comment line should specify a format.")

		self.file_format = fmt[1][0]
		self.file_format_version = float(fmt[1][1])
		if self.verbose:
			print("format:   ", self.file_format, self.file_format_version)

		# elements
		self.elements = [e for e in self._parse_header_elements(other_lines)]
		if self.verbose:
			for e in self.elements:
				print(e)

	def read_data(self, name = 'PLY'):
		readers     = [e.make_reader(self.file_format) for e in self.elements]
		field_names = [e.name for e in self.elements]
		PLY = namedtuple(name, field_names)

		data = self.f.read()
		return PLY(*ReaderIterator(iter(readers), data, 0))

if __name__ == "__main__":
	fn = sys.argv[1]
	P = PlyReader(fn, True)
	data = P.read_data()
	
	for v in vars(data):
		print(v, len(vars(data)[v]))

# vim:sw=4:ts=4
