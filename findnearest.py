## Como obtener la clave de un diccionario mas proxima a un valor o array de valores
## https://stackoverflow.com/a/29094961
from scipy.spatial import cKDTree

class KDDict(dict):
    def __init__(self, ndims, regenOnAdd=False):
        super(KDDict, self).__init__()
        self.ndims = ndims
        self.regenOnAdd = regenOnAdd
        self.__keys = []
        self.__tree = None
        self.__stale = False
        
    # Enforce dimensionality
    def __setitem__(self, key, val):
        if not isinstance(key, tuple): key = (key,)
        if len(key) != self.ndims: raise KeyError("key must be %d dimensions" % self.ndims)
        self.__keys.append(key)
        self.__stale = True
        if self.regenOnAdd: self.regenTree()
        super(KDDict, self).__setitem__(key, val)

    def regenTree(self):
        self.__tree = cKDTree(self.__keys)
        self.__stale = False

    # Helper method and might be of use
    def nearest_key(self, key):
        if not isinstance(key, tuple): key = (key,)
        if self.__stale: self.regenTree()
        _, idx = self.__tree.query(key, 1)
        return self.__keys[idx]

    def __missing__(self, key):
        if not isinstance(key, tuple): key = (key,)
        if len(key) != self.ndims: raise KeyError("key must be %d dimensions" % self.ndims)
        return self[self.nearest_key(key)]

##Example
# b = KDDict(2)
# b[4, 5] = 4
# b[10,0] = 10
# # b.regenTree()
# print b.nearest_key([2,2])

