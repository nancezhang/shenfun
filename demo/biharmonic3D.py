r"""
Solve Biharmonic equation in 3D with periodic bcs in two directions
and homogeneous Dirichlet and Neumann in the remaining third

    \nabla^4 u = f,

Use Fourier basis for the periodic direction and Shen's Biharmonic
basis for the non-periodic direction.

Note that we are solving

    (v, \nabla^4 u) = (v, f)

with the Chebyshev basis, and

    (div(grad(v), div(grad(u)) = -(v, f)

for the Legendre basis.

"""
import sys
import os
import importlib
from sympy import symbols, cos, sin, lambdify
import numpy as np
from mpi4py import MPI
from shenfun import inner, div, grad, TestFunction, TrialFunction, Array, \
    Basis, TensorProductSpace, Function

comm = MPI.COMM_WORLD

# Collect basis and solver from either Chebyshev or Legendre submodules
family = sys.argv[-1].lower() if len(sys.argv) == 2 else 'chebyshev'
base = importlib.import_module('.'.join(('shenfun', family)))
BiharmonicSolver = base.la.Biharmonic

# Use sympy to compute a rhs, given an analytical solution
x, y, z = symbols("x,y,z")
ue = (sin(4*np.pi*x)*sin(6*z)*cos(4*y))*(1-x**2)
fe = ue.diff(x, 4) + ue.diff(y, 4) + ue.diff(z, 4) + 2*ue.diff(x, 2, y, 2) + 2*ue.diff(x, 2, z, 2) + 2*ue.diff(y, 2, z, 2)

# Lambdify for faster evaluation
ul = lambdify((x, y, z), ue, 'numpy')
fl = lambdify((x, y, z), fe, 'numpy')

# Size of discretization
N = (36, 36, 36)

if family == 'chebyshev':
    assert N[0] % 2 == 0, "Biharmonic solver only implemented for even numbers"

SD = Basis(N[0], family=family, bc='Biharmonic')
K1 = Basis(N[1], family='F', dtype='D')
K2 = Basis(N[2], family='F', dtype='d')
T = TensorProductSpace(comm, (SD, K1, K2), axes=(0, 1, 2))

X = T.local_mesh(True) # With broadcasting=True the shape of X is local_shape, even though the number of datapoints are still the same as in 1D
u = TrialFunction(T)
v = TestFunction(T)

# Get f on quad points
fj = Array(T, buffer=fl(*X))

# Compute right hand side of biharmonic equation
f_hat = inner(v, fj)

# Get left hand side of biharmonic equation
if family == 'chebyshev': # No integration by parts due to weights
    matrices = inner(v, div(grad(div(grad(u)))))
else: # Use form with integration by parts. Note that Biharmonic operator used for Chebyshev also works for Legendre
    matrices = inner(div(grad(v)), div(grad(u)))

# Create linear algebra solver
H = BiharmonicSolver(*matrices)

# Solve and transform to real space
u_hat = Function(T)             # Solution spectral space
u_hat = H(u_hat, f_hat)         # Solve
uq = u_hat.backward()
#uh = uq.forward()

# Compare with analytical solution
uj = ul(*X)
print(abs(uj-uq).max())
assert np.allclose(uj, uq)

points = np.array([[0.2, 0.3], [0.1, 0.5], [0.3, 0.6]])
p = T.eval(points, u_hat, method=2)
assert np.allclose(p, ul(*points))

if 'pytest' not in os.environ:
    import matplotlib.pyplot as plt
    plt.figure()
    plt.contourf(X[0][:, :, 0], X[1][:, :, 0], uq[:, :, 8])
    plt.colorbar()

    plt.figure()
    plt.contourf(X[0][:, :, 0], X[1][:, :, 0], uj[:, :, 8])
    plt.colorbar()

    plt.figure()
    plt.contourf(X[0][:, :, 0], X[1][:, :, 0], uq[:, :, 8]-uj[:, :, 8])
    plt.colorbar()
    plt.title('Error')

    #plt.show()
