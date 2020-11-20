# -*- coding: utf-8 -*-
"""Package with api client."""
import logging
import hashlib
import six
import requests
from requests.auth import AuthBase
from .exceptions import AuthyTokenIssue, OutdatedVersion


# pylint: disable=too-few-public-methods
class TermiusAuth(AuthBase):
    """Authentication method to sync-cloud."""

    header_name = 'Authorization'

    def __init__(self, username, apikey):
        """Create new authenticator."""
        self.username = username
        self.apikey = apikey

    @property
    def auth_header(self):
        """Render auth header content."""
        return 'ApiKey {username}:{apikey}'.format(
            username=self.username, apikey=self.apikey
        )

    def __call__(self, request):
        """Add header to request."""
        request.headers[self.header_name] = self.auth_header
        return request


def hash_password(password):
    """Generate hash from password."""
    password = six.b(password)
    return hashlib.sha256(password).hexdigest()


class API(object):
    """Class to send requests to sync cloud."""

    host = 'api.termius.com'
    base_url = 'https://{}/api/'.format(host)
    logger = logging.getLogger(__name__)
    timeout = 180

    def __init__(self, username=None, apikey=None):
        """Construct new API instance."""
        if username and apikey:
            self.auth = TermiusAuth(username, apikey)
        else:
            self.auth = None

    def set_auth(self, username, apikey):
        """Provide credentials."""
        self.auth = TermiusAuth(username, apikey)

    def request_url(self, endpoint):
        """Create full url to endpoint."""
        return self.base_url + endpoint

    def login(self, email, password, authy_token=None):
        """Return user's auth token."""
        password = hash_password(password)
        payload = dict(password=password, email=email)
        if authy_token is not None:
            payload['authy_token'] = authy_token

        response = requests.post(self.request_url('v3.1/login/'), data=payload)
        self.__check_login_response(response)

        response_payload = response.json()
        apikey = response_payload['token']
        self.set_auth(email, apikey)
        return response_payload

    def __check_login_response(self, response):
        if response.status_code == 487:
            raise AuthyTokenIssue(response.json)

        if response.status_code != 200:
            self.logger.warning('Can not login!')

        self.__check_response(response, (200,))

    @staticmethod
    def __check_response(response, success_statuses=None):
        if response.status_code == 490:
            raise OutdatedVersion(
                'The current version of Termius CLI is '
                'incompatible with new Termius encryption algorithms.'
            )

        success_statuses = success_statuses or (200, 201, 202, 204)
        assert response.status_code in success_statuses, response.text

    def post(self, endpoint, data):
        """Send authorized post request."""
        self.logger.debug('send post')
        response = requests.post(
            self.request_url(endpoint),
            json=data, auth=self.auth,
            timeout=self.timeout
        )
        self.logger.debug('get response = %s', response.status_code)
        self.__check_response(response, (201,))

        return response.json()

    def get(self, endpoint):
        """Send authorized get request."""
        response = requests.get(
            self.request_url(endpoint),
            auth=self.auth,
            timeout=self.timeout
        )
        self.__check_response(response, (200,))
        return response.json()

    def delete(self, endpoint):
        """Send authorized delete request."""
        response = requests.delete(self.request_url(endpoint), auth=self.auth)
        self.__check_response(response, (200, 204))
        return response.json()

    def put(self, endpoint, data):
        """Send authorized put request."""
        response = requests.put(
            self.request_url(endpoint),
            json=data, auth=self.auth,
            timeout=self.timeout
        )
        self.__check_response(response, (200, 202))
        return response.json()
