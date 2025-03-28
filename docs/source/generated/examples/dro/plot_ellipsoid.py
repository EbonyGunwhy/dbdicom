"""
=========
Ellipsoid
=========

A simple reference object for testing, demonstrations or debugging. 

The ellipsoid is generated by the function `dbdicom.dro.ellipsoid()` which has the same arguments as the `skimage.draw.ellipsoid` function from which it is derived.
"""

# Choose this image as a thumbnail for the gallery
# sphinx_gallery_thumbnail_number = 1

from dbdicom import dro

# Define the half-width dimensions of the ellipsoid in mm
width = (
    12, # x half width (mm)
    20, # y half width (mm)
    32, # z half width (mm)
)

# Define the spacing between points (same units)
spacing = (
    2, # x spacing (mm)
    3, # y spacing (mm)
    1, # z spacing (mm)
)

# Generate the ellipsoid as a DICOM series
ellipsoid = dro.ellipsoid(width[0], width[1], width[2], spacing=spacing, levelset=True)

# %%
# The function returns a `dbdicom.Series` object *ellipsoid* which retains not only the array but also other important information about the volume. Some examples:

# Extract the numpy array in 3 dimensions (columns, row, slice):
print('Shape of the ellipsoid array:')
print(ellipsoid.pixel_values().shape)

# Extract the 4x4 affine array as a nympy ndarray:
print('\nAffine of the ellipsoid:')
print(ellipsoid.affine())

# Extract the value for any standard DICOM header element using its keyword
print('\nSome typical DICOM header information:')
print('-> Patient name: ', ellipsoid.PatientName)
print('-> Study date: ', ellipsoid.StudyDate)
print('-> Series description: ', ellipsoid.SeriesDescription)
print('-> Slice location: ', ellipsoid.SliceLocation)

# %%
# Since the ellipsoid was generated using `levelset=True`, the array represents a range of levels, as can be seen by displaying the array as a mosaic using the `.plot_mosaic()` function from the :ref:`extension-matplotlib` extension:

from dbdicom.extensions.matplotlib import plot_mosaic

plot_mosaic(ellipsoid)


# %%
# The triangulated surface of the ellipsoid can be visualised using the `.plot_surface()` function from the `dbdicom` extension :ref:`extension-matplotlib`. This displays the surface as a triangulated mesh, using the voxel spacing to ensure proper scaling of axes in the 3D plot:


from dbdicom.extensions.matplotlib import plot_surface

plot_surface(ellipsoid)





