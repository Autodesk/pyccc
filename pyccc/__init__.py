# Copyright 2016 Autodesk Inc.
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
import os as _os
PACKAGE_PATH = _os.path.dirname(_os.path.abspath(__file__))

from pyccc.job import *
from pyccc.python import *
from pyccc.engines import *
from pyccc.ui import *
from pyccc.files import *


# Other package metadata
__copyright__ = "Copyright 2016 Autodesk Inc."
__license__ = "Apache 2.0"
import os as _os
with open(_os.path.join(PACKAGE_PATH, 'VERSION')) as versionfile:
    __version__ = versionfile.read().strip()