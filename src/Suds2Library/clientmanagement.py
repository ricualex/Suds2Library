# Copyright 2012 Kevin Ormbrek
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

import logging
import os
from suds.xsd.doctor import ImportDoctor
from urllib.parse import urlparse
from urllib.request import pathname2url
from suds.client import Client
from .utils import *


class _ClientManagementKeywords(object):

    def create_soap_client(self, url_or_path, alias=None, autoblend=False, timeout='90 seconds', username=None,
                           password=None, auth_type='STANDARD'):
        """Loads a WSDL from the given URL/path and creates a Suds SOAP client.

        Returns the index of this client instance which can be used later to
        switch back to it. See `Switch Soap Client` for example.

        Optional alias is an alias for the client instance and it can be used
        for switching between clients (just as index can be used). See `Switch
        Soap Client` for more details.

        ``username`` and ``password`` are needed if the WSDL is on a server
        requiring basic authentication. ``auth_type`` selects the authentication
        scheme to use. See `Set Http Authentication` for more information.

        Autoblend ensures that the schema(s) defined within the WSDL import
        each other.

        ``timeout`` sets the timeout for SOAP requests and must be given in
        Robot Framework's time format (e.g. ``1 minute``, ``2 min 3 s``, ``4.5``).

        Examples:
        | `Create Soap Client` | http://localhost:8080/ws/Billing.asmx?WSDL |
        | `Create Soap Client` | ${CURDIR}/../wsdls/tracking.wsdl |
        """
        url = self._get_url(url_or_path)
        autoblend = to_bool(autoblend)
        kwargs = {'autoblend': autoblend}
        if username:
            password = password if password is not None else ""
            transport = self._get_transport(auth_type, username, password)
            kwargs['transport'] = transport
        imports = self._imports
        if imports:
            self._log_imports()
            kwargs['doctor'] = ImportDoctor(*imports)
        client = Client(url, **kwargs)
        logging.getLogger('suds.client').disabled = True
        index = self._add_client(client, alias)
        self._set_soap_timeout(timeout)
        return index

    def switch_soap_client(self, index_or_alias):
        """Switches between clients using index or alias.

        Index is returned from `Create Soap Client` and alias can be given to
        it.

        Example:
        | `Create Soap Client`  | http://localhost:8080/Billing?wsdl   | Billing   |
        | `Create Soap Client`  | http://localhost:8080/Marketing?wsdl | Marketing |
        | `Call Soap Method`    | sendSpam                             |           |
        | `Switch Soap Client`  | Billing                              | # alias   |
        | `Call Soap Method`    | sendInvoices                         |           |
        | `Switch Soap Client`  | 2                                    | # index   |

        Above example expects that there was no other clients created when
        creating the first one because it used index ``1`` when switching to it
        later. If you aren't sure about that you can store the index into
        a variable as below.

        | ${id} =            | `Create Soap Client`  | ... |
        | # Do something ... |                       |     |
        | `Switch Soap Client`      | ${id}          |     |
        """
        self._cache.switch(index_or_alias)

    def close_connection(self):
        """Closes the current connection from soap client.

        Previous connection is made active by this keyword. Manually use
        `Switch Connection` to switch to another connection.

        Example:
        | ${id} =            | `Create Soap Client`  | ... |
        | # Do something ... |                       |     |
        | `Close Connection` |
        """
        index = self._cache.current_index
        if index is None:
            raise RuntimeError("No open connection.")
        self._cache._connections[index-1] = self._cache.current = self._cache._no_current
        self._cache._connections.pop()
        try:
            self._cache.current=self._cache.get_connection(index-1)
        except RuntimeError:
            pass

    def close_all_connections(self):
        """Closes all open connections.
        
        This keyword is ought to be used either in test or suite teardown to
        make sure all the connections are closed before the test execution
        finishes.

        After this keyword, the connection indices returned by
        `Create Soap Client` are reset and start from ``1``.

        Example:
        | ${id} =            | `Create Soap Client`   |
        | ${id} =            | `Create Soap Client    |
        | # Do something with the connections         |
        | [Teardown]        | `Close All Connections` |
        """
        self._cache.empty_cache()

    # PyAPI

    def _client(self):
        """Returns the current suds.client.Client instance."""
        return self._cache.current

    def _add_client(self, client, alias=None):
        """Puts a client into the cache and returns the index.

        The added client becomes the current one."""
        client.set_options(faults=True)
        self._logger.info('Using WSDL at %s%s' % (client.wsdl.url, client))
        self._imports = []
        index = self._cache.register(client, alias)
        self.set_soap_logging(True)
        return index

    # private

    def _log_imports(self):
        if self._imports:
            msg = "Using Imports for ImportDoctor:"
            for imp in self._imports:
                msg += "\n   Namespace: '%s' Location: '%s'" % (imp.ns, imp.location)
                for ns in imp.filter.tns:
                    msg += "\n      Filtering for namespace '%s'" % ns
            self._logger.info(msg)

    def _get_url(self, url_or_path):
        if not len(urlparse(url_or_path).scheme) > 1:
            if not os.path.isfile(url_or_path):
                raise IOError("File '%s' not found." % url_or_path)
            url_or_path = 'file:' + pathname2url(url_or_path)
        return url_or_path
