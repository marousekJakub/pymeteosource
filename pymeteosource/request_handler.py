"""Module that handles sending the requests to API"""

import requests
from requests.adapters import HTTPAdapter, Retry

from .errors import InvalidRequestError

class RequestHandler:
    """
    Object that handles sending the requests to API

    Attributes
    ----------
    session : requests.sessions.Session
        A session object to send the requests. This can speed-up multiple
        requests within a program run.

    Methods
    -------
    execute_request
        Execute request and return the JSON response
    """

    def __init__(self, key, use_gzip):
        """
        :param str: The API key
        :param bool: True if gzip compression should be used, False otherwise
        """
        # Initialize the session
        self.session = requests.Session()
        # Automatically add key header to all requests made within the session
        self.session.headers.update({'X-API-Key': key})
        # Set header to allow gzip encoding to improve speed, if wanted
        if use_gzip:
            self.session.headers.update({'Accept-Encoding': 'gzip'})

        # retry a request in case of a timeout, socket error and 5xx errors
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 501, 502, 503, 504])
        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def execute_request(self, url, **params):
        """
        Make a request and return the JSON response

        :param str: URL of the requests (without the parameters)
        :param kwargs: Arguments of the request (lat, lon, ...)
        """
        response = self.session.get(url, params=params, timeout=10)
        if response.status_code != 200:
            raise InvalidRequestError(response)

        data = response.json()

        return data
