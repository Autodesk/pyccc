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

QUEUED = 'Queued'
DOWNLOADING = 'Downloading'
RUNNING = 'Running'
FINISHING = 'Finishing'
FINISHED = 'Finished'

ERROR = 'Error'
TIMEOUT = 'Timeout'
KILLED = 'Killed'

DONE_STATES = (ERROR, KILLED, FINISHED, TIMEOUT)
ERROR_STATES = (ERROR, TIMEOUT)
