import os
from copy import deepcopy
import pydicom
import numpy as np
import pandas as pd
from .. import utilities, functions
import dbdicom as db


class DbDicom():
    """Abstract base class for methods that are shared between records and datasets"""

    def instances(self, index=None, **kwargs): 
        """A list of instances of the object"""

        if self.generation == 4: 
            return
        if self.generation == 3:
            return self.children(index=index, **kwargs)
        instances = []
        for child in self.children():
            inst = child.instances(**kwargs)
            instances.extend(inst)
        if index is not None:
            if index >= len(instances):
                return
            else:
                return instances[index]
        return instances 


class DataSet(DbDicom):

    def __init__(self, parent=None):

        self.parent = parent
        # For Database, Patient, Study or Series: list of dbdicom DataSet instances
        # For Instance: pydicom DataSet instance
        self._ds = None 

    @property
    def generation(self):
        if self._ds is None:
            return
        if self.is_an_instance():
            return 4
        else:
            return self._ds[0].generation - 1

    def is_an_instance(self):

        if isinstance(self._ds, list):
            return False
        else:
            return True

    def to_pydicom(self): # instances only

        if self.is_an_instance():
            return self._ds

    def set_pydicom(self, ds):
        
        if self.is_an_instance():
            self._ds = ds

    def empty(self):
        return self._ds is None

    def __getattr__(self, tag):
        """Gets the value of the data element with given tag.
        
        Arguments
        ---------
        tag : str
            DICOM KeyWord String

        Returns
        -------
        Value of the corresponding DICOM data element
        """
        return self[tag]

    def __getitem__(self, tags):
        """Gets the value of the data elements with specified tags.
        
        Arguments
        ---------
        tags : a string, hexadecimal tuple, or a list of strings and hexadecimal tuples

        Returns
        -------
        A value or a list of values
        """
        if self.empty():
            return None
        if self.is_an_instance():
            return utilities._read_tags(self, tags)
        else:
            return self._ds[0][tags]



    def __setattr__(self, tag, value):
        """Sets the value of the data element with given tag."""

        if tag in ['parent', '_ds']:
            self.__dict__[tag] = value
        else:
            self[tag] = value

    def __setitem__(self, tags, values):
        """Sets the value of the data element with given tag."""

        if self.is_an_instance():
            utilities._set_tags(self, tags, values)
        else:
            for instance in self.instances():
                utilities._set_tags(instance, tags, values)

    def children(self, index=None, **kwargs):
        """List of children"""

        if self.is_an_instance(): 
            return []
        objects = utilities._filter(self._ds, **kwargs)
        if index is not None:
            if index >= len(objects): 
                return []
            else:
                return objects[index]
        return objects

  

class Record(DbDicom):

    def __init__(self, folder, UID=[], generation=0, **attributes):

        objUID = [] + UID
#        for i in range(generation-len(UID)):
        while generation > len(objUID):
            newUID = pydicom.uid.generate_uid()
            objUID.append(newUID)    

        self.UID = objUID
        self.folder = folder
        self.status = folder.status
        self.dialog = folder.dialog
        self.dicm = folder.dicm
        # placeholder DICOM attributes
        # these will populate the dataset and dataframe when data are created
        self.attributes = attributes

    def is_an_instance(self):
        return self.generation == 4

    def to_pydicom(self): # instances only

        if self.is_an_instance():
            return self.read().to_pydicom()

    def __getattr__(self, tag):
        """Gets the value of the data element with given tag.
        
        Arguments
        ---------
        tag : str
            DICOM KeyWord String

        Returns
        -------
        Value of the corresponding DICOM data element
        """
        return self[tag]

    def __getitem__(self, tags):
        """Gets the value of the data elements with specified tags.
        
        Arguments
        ---------
        tags : a string, hexadecimal tuple, or a list of strings and hexadecimal tuples

        Returns
        -------
        A value or a list of values
        """
        if self.is_an_instance():
            ds = self.read()
            return utilities._read_tags(ds, tags)
        instances = self.instances()
        if instances == []:
            return
        if not isinstance(tags, list):
            values = []
            for instance in instances:
                ds = instance.read()
                v = utilities._read_tags(ds, tags)
                values.append(v)
            return list(set(values))

        # For each tag, get a list of values, one for each instance
        # Return a list of unique items per tag
        values = [[] for _ in range(len(tags))]
        for instance in instances:
            ds = instance.read()
            v = utilities._read_tags(ds, tags)
            for t in range(len(tags)):
                values[t].append(v[t])
        for v, value in enumerate(values):
            values[v] = list(set(value))
        return values

    def __setattr__(self, tag, value):
        """Sets the value of the data element with given tag."""

        if tag in ['UID', 'folder', 'status', 'dialog', 'dicm', 'attributes']:
            self.__dict__[tag] = value
        else:
            self[tag] = value

    def __setitem__(self, tags, values):
        """Sets the value of the data element with given tag."""

        # FASTER but needs testing
        # This also means __setitem__ can be removed from instance class
        #
        # db.set_value(self.instances(), dict(zip(tags, values)))
        
        # LAZY - SLOW
        if self.is_an_instance():
            instances = [self]
        else:
            instances = self.instances()
        for i, instance in enumerate(instances):
            ds = instance.read()
            utilities._set_tags(ds, tags, values)
            instance.write(ds)
            self.status.progress(i, len(instances))
        self.status.hide()

    def read(self, message = 'Reading..'):

        if self.is_an_instance():
            return self._read_instance()
        dataset = DataSet()
        children = self.children()
        if len(children) == 0:
            return dataset
        dataset._ds = []
        for i, child in enumerate(children):
            self.status.progress(i, len(children), 'Reading data..')
            child_dataset = child.read()
            child_dataset.parent = self
            dataset._ds.append(child_dataset)
        self.status.hide()
        return dataset

    def _read_instance(self):
        """Reads the dataset into memory."""

        dataset = DataSet()
        file = self.file
        if file is None: 
            return dataset
        try:
            ds = pydicom.dcmread(file)
        except:
            message = "Failed to read " + file
            message += "\n Please read the DICOM folder again via File->Read."
            self.dialog.information(message)         
            return dataset
        dataset._ds = ds
        return dataset 

    def write(self, dataset): # ds is a DataSet

        if dataset.is_an_instance():
            instances = [dataset]
        else:
            instances = dataset.instances()
        for instance in instances:
            self._copy_attributes_to(instance)
        self.status.message('Updating database..')
        self.folder._add(instances)
        self.status.hide()

    def _copy_attributes_to(self, dataset): # ds is an instance DataSet

        ds = dataset.to_pydicom() 

        if self.generation == 0:
            pass
        elif self.generation == 1:
            ds.PatientID = self.UID[0]
        elif self.generation == 2:
            ds.PatientID = self.UID[0]
            ds.StudyInstanceUID = self.UID[1]
        elif self.generation == 3:
            ds.PatientID = self.UID[0]
            ds.StudyInstanceUID = self.UID[1]
            ds.SeriesInstanceUID = self.UID[2]   
        elif self.generation == 4:
            ds.PatientID = self.UID[0]
            ds.StudyInstanceUID = self.UID[1]
            ds.SeriesInstanceUID = self.UID[2]   
            ds.SOPInstanceUID = self.UID[3]  

        utilities._set_tags(ds, list(self.attributes.keys()), list(self.attributes.values()))

    def children(self, index=None, **kwargs):
        """List of children"""

        if self.generation == 4: 
            return []
        return self.records(generation=self.generation+1, index=index, **kwargs) 

    def remove(self):
        """Deletes the object. """ 

        files = self.files
        if files == []: 
            return
        self.folder.dataframe.loc[self.data().index,'removed'] = True 

    @property
    def generation(self):
        return len(self.UID)

    @property
    def key(self):
        """The keywords describing the UID of the record"""

        key = ['PatientID', 'StudyInstanceUID', 'SeriesInstanceUID', 'SOPInstanceUID']
        return key[0:self.generation]

    def new_uid(self): # to utilities
        
        return pydicom.uid.generate_uid()

    def data(self):
        """Dataframe with current data - excluding those that were removed
        """

        # Note: this returns a copy - could be a view instead using .loc?

        if self.folder.path is None:
            return self.folder.dataframe
        current = self.folder.dataframe.removed == False
        data = self.folder.dataframe[current]
        if self.UID == []: 
            return data       
        rows = data[self.key[-1]] == self.UID[-1]
        return data[rows]

    def dataset(self, sortby=None, status=True): 
        """Sort instances by a list of attributes.
        
        Args:
            sortby: 
                List of DICOM keywords by which the series is sorted
        Returns:
            An ndarray holding the instances sorted by sortby.
        """
        if sortby is None:
            df = self.data()
            return self._dataset_from_df(df)
        else:
            if set(sortby) <= set(self.folder.dataframe):
                df = self.folder.dataframe.loc[self.data().index, sortby]
            else:
                df = utilities.dataframe(self.folder.path, self.files, sortby, self.status)
            df.sort_values(sortby, inplace=True) 
            return self._sorted_dataset_from_df(df, sortby, status=status)

    def _sorted_dataset_from_df(self, df, sortby, status=True): 

        data = []
        vals = df[sortby[0]].unique()
        for i, c in enumerate(vals):
            if status: self.status.progress(i, len(vals), message='Sorting..')
            dfc = df[df[sortby[0]] == c]
            if len(sortby) == 1:
                datac = self._dataset_from_df(dfc)
            else:
                datac = self._sorted_dataset_from_df(dfc, sortby[1:], status=False)
            data.append(datac)
        return utilities._stack_arrays(data, align_left=True)

    def _dataset_from_df(self, df): 
        """Return datasets as numpy array of object type"""

        data = np.empty(df.shape[0], dtype=object)
        cnt = 0
        for file, _ in df.iterrows(): # just enumerate over df.index
            #self.status.progress(cnt, df.shape[0])
            data[cnt] = self.folder.instance(file)
            cnt += 1
        #self.status.hide()
        return data

    def array(self, sortby=None, pixels_first=False): 
        """Pixel values of the object as an ndarray
        
        Args:
            sortby: 
                Optional list of DICOM keywords by which the volume is sorted
            pixels_first: 
                If True, the (x,y) dimensions are the first dimensions of the array.
                If False, (x,y) are the last dimensions - this is the default.

        Returns:
            An ndarray holding the pixel data.

            An ndarry holding the datasets (instances) of each slice.

        Examples:
            ``` ruby
            # return a 3D array (z,x,y)
            # with the pixel data for each slice
            # in no particular order (z)
            array, _ = series.array()    

            # return a 3D array (x,y,z)   
            # with pixel data in the leading indices                               
            array, _ = series.array(pixels_first = True)    

            # Return a 4D array (x,y,t,k) sorted by acquisition time   
            # The last dimension (k) enumerates all slices with the same acquisition time. 
            # If there is only one image for each acquision time, 
            # the last dimension is a dimension of 1                               
            array, data = series.array('AcquisitionTime', pixels_first=True)                         
            v = array[:,:,10,0]                 # First image at the 10th location
            t = data[10,0].AcquisitionTIme      # acquisition time of the same image

            # Return a 4D array (loc, TI, x, y) 
            sortby = ['SliceLocation','InversionTime']
            array, data = series.array(sortby) 
            v = array[10,6,0,:,:]            # First slice at 11th slice location and 7th inversion time    
            Loc = data[10,6,0][sortby[0]]    # Slice location of the same slice
            TI = data[10,6,0][sortby[1]]     # Inversion time of the same slice
            ```  
        """
        dataset = self.dataset(sortby)
        array = []
        ds = dataset.ravel()
        for i, im in enumerate(ds):
            self.status.progress(i, len(ds), 'Reading pixel data..')
            if im is None:
                array.append(np.zeros((1,1)))
            else:
                array.append(im.array())
        self.status.hide()
        #array = [im.array() for im in dataset.ravel() if im is not None]
        array = utilities._stack_arrays(array) #db.stack(array)
        array = array.reshape(dataset.shape + array.shape[1:])
        if pixels_first:
            array = np.moveaxis(array, -1, 0)
            array = np.moveaxis(array, -1, 0)
        return array, dataset # REPLACE BY DBARRAY

    def npy(self):

        path = os.path.join(self.folder.path, "dbdicom_npy")
        if not os.path.isdir(path): os.mkdir(path)
        file = os.path.join(path, self.UID[-1] + '.npy') 
        return file

    def load_npy(self):

        file = self.npy()
        if not os.path.exists(file):
            return
        with open(file, 'rb') as f:
            array = np.load(f)
        return array

    def save_npy(self, array=None, sortby=None, pixels_first=False):

        if array is None:
            array = self.array(sortby=sortby, pixels_first=pixels_first)
        file = self.npy() 
        with open(file, 'wb') as f:
            np.save(f, array)

    def set_array(self, array, dataset=None, pixels_first=False, inplace=False): 
        """
        Set pixel values of a series from a numpy ndarray.

        Since the pixel data do not hold any information about the 
        image such as geometry, or other metainformation,
        a dataset must be provided as well with the same 
        shape as the array except for the slice dimensions. 

        If a dataset is not provided, header info is 
        derived from existing instances in order.

        Args:
            array: 
                numpy ndarray with pixel data.

            dataset: 
                numpy ndarray

                Instances holding the header information. 
                This *must* have the same shape as array, minus the slice dimensions.

            pixels_first: 
                bool

                Specifies whether the pixel dimensions are the first or last dimensions of the series.
                If not provided it is assumed the slice dimensions are the last dimensions
                of the array.

            inplace: 
                bool

                If True (default) the current pixel values in the series 
                are overwritten. If set to False, the new array is added to the series.
        
        Examples:
            ```ruby
            # Invert all images in a series:
            array, _ = series.array()
            series.set_array(-array)

            # Create a maximum intensity projection of the series.
            # Header information for the result is taken from the first image.
            # Results are saved in a new sibling series.
            array, data = series.array()
            array = np.amax(array, axis=0)
            data = np.squeeze(data[0,...])
            series.new_sibling().set_array(array, data)

            # Create a 2D maximum intensity projection along the SliceLocation direction.
            # Header information for the result is taken from the first slice location.
            # Current data of the series are overwritten.
            array, data = series.array('SliceLocation')
            array = np.amax(array, axis=0)
            data = np.squeeze(data[0,...])
            series.set_array(array, data)

            # In a series with multiple slice locations and inversion times,
            # replace all images for each slice location with that of the shortest inversion time.
            array, data = series.array(['SliceLocation','InversionTime']) 
            for loc in range(array.shape[0]):               # loop over slice locations
                slice0 = np.squeeze(array[loc,0,0,:,:])     # get the slice with shortest TI 
                TI0 = data[loc,0,0].InversionTime           # get the TI of that slice
                for TI in range(array.shape[1]):            # loop over TIs
                    array[loc,TI,0,:,:] = slice0            # replace each slice with shortest TI
                    data[loc,TI,0].InversionTime = TI0      # replace each TI with shortest TI
            series.set_array(array, data)
            ```
        """
        if pixels_first:    # Move to the end (default)
            array = np.moveaxis(array, 0, -1)
            array = np.moveaxis(array, 0, -1)
        if dataset is None:
            dataset = self.dataset()
        # Return with error message if dataset and array do not match.
        nr_of_slices = np.prod(array.shape[:-2])
        if nr_of_slices != np.prod(dataset.shape):
            message = 'Error in set_array(): array and dataset do not match'
            message += '\n Array has ' + str(nr_of_slices) + ' elements'
            message += '\n dataset has ' + str(np.prod(dataset.shape)) + ' elements'
            message += '\n Check if the keyword pixels_first is set correctly.'
            self.dialog.error(message)
            raise ValueError(message)
        # If self is not a series, create a new series.
        if self.generation != 3:
            series = self.new_series()
        else:
            series = self
        # Reshape, copy instances and save slices.
        array = array.reshape((nr_of_slices, array.shape[-2], array.shape[-1])) # shape (i,x,y)
        dataset = dataset.reshape(nr_of_slices) # shape (i,)

        dataset = db.copy(dataset.tolist(), series, status=self.status)
        for i, instance in enumerate(dataset):
            self.status.progress(i, len(dataset), 'Writing array to file..')
            instance.set_array(array[i,...])
            if inplace: instance.remove() # delete?
           
        #for i, instance in enumerate(dataset):
        #    self.status.progress(i, len(dataset), 'Saving data..')
        #    instance.copy_to(series).set_array(array[i,...])
            # instance.set_array(array[i,...])
        #    if inplace: instance.remove() # delete?

        return series

#    def write_array(self, array, dataset): 
#        """
#        Set and array and write it to disk.
#        """
#        series = self.set_array(array, dataset)
#        series.write()
#        return series

    @property
    def _SOPClassUID(self):
        """The SOP Class UID of the first instance"""

        data = self.data()
        if data.empty: return None
        return self.data().iloc[0].SOPClassUID

    @property
    def files(self):
        """Returns the filepath to the instances in the object."""
 
        relpaths = self.data().index.tolist()
        return [os.path.join(self.folder.path, p) for p in relpaths]

    @property
    def file(self):
        """Returns the filepath to the first file."""
 
        files = self.files
        if len(files) != 0:  
            return files[0]

    @property
    def parent(self):
        "Returns the parent object"

        return self.dicm.parent(self)
        
    def records(self, generation=0, index=None, **kwargs):
        """A list of all records of a given generation corresponding to the record.

        If generation is lower then that of the object, 
        all offspring of the given generation are returned.

        If the generation is higher than that of the object,
        the correspondong ancestor is return as a 1-element list.

        Optionally the list can be filtered by index, or by providing a 
        list of DICOM KeyWords and values. In that case only objects
        a returned that fulfill all criteria.
        
        Parameters
        ----------
        generation : int
            The generation to be returned (0 to 4)
        index : int
            Index of the single object to be return
        kwargs : (Key, Value)
            Conditions to filter the objects
        """
        objects = []
        if generation == 0:
            obj = self.dicm.object(self.folder, generation=0)
            objects.append(obj)
        else:
            key = self.folder._columns[0:generation]
            data = self.data()
            if data.empty: 
                if index is None:
                    return objects
                else:
                    return
            column = data[key[-1]]
            rec_list = column.unique()
            if index is not None:
                rec_list = [rec_list[index]]
            for rec in rec_list:
                rec_data = data[column == rec]
                row = rec_data.iloc[0]
                obj = self.dicm.object(self.folder, row, generation)
                objects.append(obj)
        objects = utilities._filter(objects, **kwargs)
        if index is not None: return objects[0]
        return objects

    def patients(self, index=None,  **kwargs):
        """A list of patients of the object"""

        if self.generation==4: 
            return self.parent.parent.parent
        if self.generation==3:
            return self.parent.parent
        if self.generation==2:
            self.parent
        if self.generation==1:
            return
        return self.children(index=index, **kwargs)

    def studies(self, index=None, **kwargs):
        """A list of studies of the object"""

        if self.generation==4: 
            return self.parent.parent
        if self.generation==3:
            return self.parent
        if self.generation==2:
            return
        if self.generation==1:
            return self.children(index=index, **kwargs)
        objects = []
        for child in self.children():
            inst = child.studies(**kwargs)
            objects.extend(inst)
        if index is not None:
            if index >= len(objects):
                return
            else:
                return objects[index]
        return objects

    def series(self, index=None, **kwargs):
        """A list of series of the object"""

        if self.generation==4: 
            return self.parent
        if self.generation==3:
            return
        if self.generation==2:
            kids = self.children(index=index, **kwargs)
            return kids
        series = []
        for child in self.children():
            inst = child.series(**kwargs)
            series.extend(inst)
        if index is not None:
            if index >= len(series):
                return
            else:
                return series[index]
        return series

    def new_child(self, **attributes):
        """Creates a new child object"""

        obj = self.dicm.new_child(self, **attributes)
        return obj

    def new_sibling(self, **attributes):
        """
        Creates a new sibling under the same parent.
        """
        if self.generation == 0:
            return
        else:
            return self.parent.new_child(**attributes)

    def new_pibling(self, **attributes):
        """
        Creates a new sibling of parent.
        """
        if self.generation <= 1:
            return
        else:
            return self.parent.new_sibling(**attributes)

    def new_cousin(self, **attributes):
        """
        Creates a new sibling of parent.
        """
        if self.generation <= 1:
            return
        else:
            return self.new_pibling().new_child(**attributes)

    def new_series(self, **attributes):
        """
        Creates a new series under the same parent
        """ 
        if self.generation <= 1: 
            return self.new_child().new_series(**attributes)
        if self.generation == 2:
            return self.new_child(**attributes)
        if self.generation == 3:
            return self.new_sibling(**attributes)
        if self.generation == 4:
            return self.new_pibling(**attributes) 

    def remove(self):
        """Deletes the object. """ 

        files = self.files
        if files == []: 
            return
        self.folder.dataframe.loc[self.data().index,'removed'] = True

    def move_to(self, ancestor):
        """move object to a new parent.
        
        ancestor:any DICOM Class
            If the object is not a parent, the missing 
            intermediate generations are automatically created.
        """
        copy = self.copy_to(ancestor)
        self.remove()
        return copy
    
    def copy(self):
        """Returns a copy in the same parent"""

        copy = self.copy_to(self.parent)
        return copy

    def _copy_to_OBSOLETE(self, ancestor, message=None): # functional but slow
        """copy object to a new ancestor.
        
        ancestor: Root, Patient or Study
        If the object is not a study, the missing 
        intermediate generations are automatically created.
        """
        if self.generation == 0: return
#        if ancestor.generation == 0: return
        copy = self.__class__(self.folder, UID=ancestor.UID)
        children = self.children()
        if message is None:
            message = "Copying " + self.__class__.__name__ + ' ' + self.label()
        self.status.message(message)
        for i, child in enumerate(children):
            child.copy_to(copy)
            self.status.progress(i, len(children))
        self.status.hide()
        return copy

    def _initialize(self, ds, ref=None): # ds is a pydicom dataset

        if self.generation == 4:
            ds = utilities.initialize(ds, UID=self.UID, ref=ref)
        else:
            for i, obj in enumerate(ds):
                if ref is not None:
                    obj._initialize(ds[i])
                else:
                    obj._initialize()

    def merge_with(self, obj, message=None): 

        if self.generation == 0: return
        if message is None:
            message = "Merging " + self.__class__.__name__ + ' ' + self.label()
        # replace by db.merge()
        return self._merge_with(obj, message=message)

    def copy_to(self, ancestor, message=None):

        if self.generation == 0: return
        if message is None:
            message = "Copying " + self.__class__.__name__ + ' ' + self.label()
        copy = self.__class__(self.folder, UID=ancestor.UID)
        # replace by db.merge()
        return self._merge_with(copy, message=message)

    def _merge_with(self, obj, message=None): # obsolete - replace by db.merge()

        # Extend dataframe & create new files
        dfsource = self.data()
        sourcefiles = [os.path.join(self.folder.path, p) for p in dfsource.index.tolist()]
        df = dfsource.copy(deep=True)
        df['files'] = [self.folder.new_file() for _ in range(df.shape[0])]
        df.set_index('files', inplace=True)
        for key in self.folder._columns[self.generation:3]:
            for id in df[key].unique():
                uid = self.folder.new_uid()
                rows = df[key] == id
                df.loc[rows.index, key] = uid
            #    for file in rows.index:
            #        df.at[file, key] = uid
        df.SOPInstanceUID = self.folder.new_uid(df.shape[0])
        df.removed = False
        df.created = True
        copyfiles = df.index.tolist()

        for i, file in enumerate(copyfiles):
            self.status.progress(i, len(copyfiles), message=message)
            df.loc[file, self.folder._columns[0:self.generation]] = obj.UID 
            ds = pydicom.dcmread(sourcefiles[i])
            ds = utilities._initialize(ds, UID=df.loc[file, self.folder._columns[:4]].values.tolist())
            if obj.attributes is not None:
                for key, value in obj.attributes.items():
                    utilities._set_tags(ds, key, value)
                    if key in self.folder._columns[4:]:
                        df.at[file, key] = value  
            ds.save_as(os.path.join(self.folder.path, file))

        self.folder.__dict__['dataframe'] = pd.concat([self.folder.dataframe, df])
        self.status.hide()

        return obj

    def export(self, path):
        """Export instances to an external folder.

        The instance itself will not be removed from the DICOM folder.
        Instead a copy of the file will be copied to the external folder.
        
        Arguments
        ---------
        path : str
            path to an external folder. If not provided,
            a window will prompt the user to select one.
        """
        if self.is_an_instance():
            instances = [self]
        else:
            instances = self.instances()
        
        for i, instance in enumerate(instances):
            filename = os.path.basename(instance.file)
            destination = os.path.join(path, filename)
            ds = instance.read().to_pydicom()
            functions.write(ds, destination, self.dialog)
            self.status.progress(i,len(instances), message='Exporting..')
        self.status.hide()

        
    def save(self, message = "Saving changes.."):
        """Save all instances of the record."""

        self.status.message(message)
        if self.generation == 0:
            data = self.folder.dataframe
        else:
            rows = self.folder.dataframe[self.key[-1]] == self.UID[-1]
            data = self.folder.dataframe[rows] 

        created = data.created[data.created]   
        removed = data.removed[data.removed]

        files = [os.path.join(self.folder.path, p) for p in removed.index.tolist()]
        for i, file in enumerate(files): 
            self.status.progress(i, len(files), message='Deleting removed files..')
            if os.path.exists(file): os.remove(file)
        #self.status.message('Clearing rapid access storage..')
        #npyfile = self.npy()
        #if os.path.exists(npyfile): os.remove(npyfile)
        self.status.message('Done saving..')
        self.folder.dataframe.loc[created.index, 'created'] = False
        self.folder.dataframe.drop(removed.index, inplace=True)

    def restore(self, message = "Restoring saved state.."):
        """
        Restore all instances.
        """
        self.status.message(message)

        if self.generation == 0:
            data = self.folder.dataframe
        else:
            rows = self.folder.dataframe[self.key[-1]] == self.UID[-1]
            data = self.folder.dataframe[rows] 
        created = data.created[data.created]   
        removed = data.removed[data.removed]

        files = [os.path.join(self.folder.path, p) for p in created.index.tolist()]
        for i, file in enumerate(files): 
            self.status.progress(i, len(files), message='Deleting new files..')
            if os.path.exists(file): os.remove(file)
        self.status.hide()
        self.folder.dataframe.loc[removed.index, 'removed'] = False
        self.folder.dataframe.drop(created.index, inplace=True)

        return self
        

    def read_dataframe(self, tags):

        return utilities.dataframe(self.folder.path, self.files, tags, self.status)

