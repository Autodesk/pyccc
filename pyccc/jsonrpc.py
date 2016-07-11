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
import requests
import json
import funcsigs


class JsonRpcProxy(object):
    """Wraps function calls to JSON-RPC calls to the host.
    """

    def __init__(self, host):
        self.host = host
        self.debug = False

        # create python docstrings
        self._docstrings = {}
        self._funcnames = []
        self._sigs = {}
        response = requests.get(self.host.rstrip('/'))
        for funcjson in response.json():
            fname = funcjson['alias']
            self._funcnames.append(fname)
            dslist = [funcjson['doc']]
            funcargs = []

            if funcjson.get('args', None):
                dslist.append('\nArgs:')
                for arg in funcjson['args']:
                    funcargs.append(funcsigs.Parameter(arg['name'],
                                                       funcsigs.Parameter.POSITIONAL_OR_KEYWORD,
                                                       default=None))
                    dslist.append('  %s (%s): %s' % (
                        arg['name'], arg['type'], arg['doc']))

            self._sigs[fname] = funcsigs.Signature(funcargs)
            self._docstrings[fname] = '\n'.join(dslist)

    def __dir__(self):
        return self.__dict__.keys() + self._funcnames

    def __getattr__(self, *args):
        host = self.host
        method = args[0]

        def jsonRpcFunction(**kwargs):
            jsonRpcRequest = {
                'jsonrpc': '2.0',
                'id': '_',  # '_' means this client is not managing jsonrpc ids.
                'method': method,
                'params': {}
            }

            files = {}

            for key, value in kwargs.iteritems():
                if isinstance(value, file):
                    files[key] = value
                else:
                    jsonRpcRequest['params'][key] = value

            response = None
            if files:
                # Add the JSON-RPC message to the multipart message
                fileParts = {'jsonrpc': ('jsonrpc', json.dumps(jsonRpcRequest))}
                for key, value in files.iteritems():
                    fileParts[key] = (key, value, 'application/octet-stream')
                response = requests.post(host, files=fileParts)
            else:
                headers = {'Content-Type': 'application/json-rpc'}

                if self.debug:
                    print 'POST to %s' % host
                    print 'headers:', headers
                    print 'data:', json.dumps(jsonRpcRequest)

                response = requests.post(host, headers=headers, data=json.dumps(jsonRpcRequest))

            try:
                responseJson = response.json()
            except ValueError:
                raise ValueError('Non-json response (Status %s): %s' %
                                 (response.status_code, response.reason), response)

            if 'error' in responseJson:
                raise ValueError(responseJson['error'])

            if self.debug:
                try:
                    print 'link:', 'http://' + host.split('/')[2] + '/' + responseJson['result']['jobId']
                except KeyError:
                    pass
            return responseJson['result']

        jsonRpcFunction.__doc__ = self._docstrings[method]
        jsonRpcFunction.__signature__ = self._sigs[method]
        return jsonRpcFunction


if __name__ == '__main__':
    import sys
    if len(sys.argv) <= 2:
        print('    Creates JSON-RPC method calls from arguments:')
        print('        <HOST> <METHOD> [arg1=val1] [arg2=val2] ... [argn=valn]')
        print('        Returns: JSON-RPC method call result, or throws an error')
        print('')
        print('        For example:')
        print('            jsonrpc.py http://localhost:9000 test echo=foo')
    else:
        host = sys.argv[1]
        method = sys.argv[2]
        args = {}
        for arg in sys.argv[3:]:
            tokens = arg.split('=')
            args[tokens[0]] = tokens[1]
        proxy = JsonRpcProxy(host)
        methodToCall = getattr(proxy, method)
        print(methodToCall(**args))
