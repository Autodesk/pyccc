from __future__ import print_function, absolute_import, division
from future.builtins import *
from future import standard_library

standard_library.install_aliases()

# Copyright 2017 Autodesk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import io
import pickle
import weakref

_weakmemos = weakref.WeakValueDictionary()


class DepartingPickler(pickle.Pickler):
    """ Pickler for objects on the DEPARTURE leg of the roundtrip

    Note: this will _probably_ only handle a single layer round trip for now, and will
    fail in weird ways otherwise.
    """

    def persistent_id(self, obj):
        """ Tags objects with a persistent ID, but do NOT emit it
        """
        if getattr(obj, '_PERSIST_REFERENCES', None):
            objid = id(obj)
            obj._persistent_ref = objid
            _weakmemos[objid] = obj
        return None


class ReturningPickler(pickle.Pickler):
    """ Pickler for objects on the RETURN leg of the roundtrip
    """
    def persistent_id(self, obj):
        """ Replaces object reference
        """
        if getattr(obj, '_persistent_ref', None) is not None:
            return obj._persistent_ref


class ReturningUnpickler(pickle.Unpickler):
    """ Pickler for RETURNING objects that will retain references on roundtrip
    """
    def persistent_load(self, pid):
        return _weakmemos[pid]


def departure_dumps(obj, **kwargs):
    buff = io.BytesIO()
    pickler = DepartingPickler(buff, **kwargs)
    pickler.dump(obj)
    result = buff.getvalue()
    buff.close()
    return result


def return_loads(b, **kwargs):
    buff = io.BytesIO(b)
    unpickler = ReturningUnpickler(buff, **kwargs)
    obj = unpickler.load()
    buff.close()
    return obj
