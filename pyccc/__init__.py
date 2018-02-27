# Copyright 2016-2018 Autodesk Inc.
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
from __future__ import print_function, unicode_literals, absolute_import, division
from future import standard_library
standard_library.install_aliases()
from future.builtins import *

import os as _os
PACKAGE_PATH = _os.path.dirname(_os.path.abspath(__file__))

from pyccc.exceptions import *
from pyccc.job import *
from pyccc.python import *
from pyccc.engines import *
from pyccc.ui import *
from pyccc.files import *


# Package metadata
from pyccc import _version
__version__ = _version.get_versions()['version']
__copyright__ = "Copyright 2016-2018 Autodesk Inc."
__license__ = "Apache 2.0"
