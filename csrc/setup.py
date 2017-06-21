from distutils.core import setup
from Cython.Build import cythonize

setup(
    name="ArtPanda3D",
    ext_modules=cythonize('cmain.py'),  # accepts a glob pattern
)