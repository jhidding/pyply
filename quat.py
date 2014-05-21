import numpy as np

class Quat:
	def __init__(self, scalar, vector):
		self.s = scalar
		self.v = vector
		
	def __mul__(self, quat):
		s = self.s * quat.s - np.dot(self.v, quat.v)
		v = quat.v * self.s + self.v * quat.s + np.cross(self.v, quat.v)
		return Quat(s, v)

	def conj(self):
		return Quat(self.s, -self.v)

	def sqr(self):
		return self.s**2 + np.square(self.v).sum()

	def scale(self, a):
		return Quat(a * self.s, a * self.v)

	def inv(self):
		return self.conj().scale(1./self.sqr())

	def __call__(self, vector):
		return (self * Quat(0, vector) * self.conj()).v

def scalar(a):
	return Quat(a, np.zeros(3))

def rotation(v, th):
	w = v * np.sin(th/2)
	s = np.cos(th/2)
	return Quat(s, w)

