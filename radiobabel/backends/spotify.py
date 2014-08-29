# future imports
from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

# stdlib imports
import logging

# third-party imports
import requests

# local imports
from radiobabel.errors import TrackNotFound


logger = logging.getLogger('radiobabel.backends.spotify')


def _make_request(url, params=None):
    """Make a HTTP request to the spotify API using the requests library
    """
    response = requests.get(url, params=params)
    # raise an exception if 400 <= response.status_code <= 599
    response.raise_for_status()
    return response.json()


def _make_post_request(url, data):
    """Make a HTTP request to the spotify API using the requests library
    """
    response = requests.post(url, data=data)
    # raise an exception if 400 <= response.status_code <= 599
    response.raise_for_status()
    return response.json()


def _make_oauth_request(url, token):
    # Use token in authorization header of call
    headers = {'Authorization': 'Bearer {}'.format(token)}
    response = requests.get(url, headers=headers)
    # raise an exception if 400 <= response.status_code <= 599
    response.raise_for_status()
    return response.json()


def _transform_search_response(search_results, offset):
    """Transform a result returned from the spotify API into a format we
    can return to clients/use to populate the database.
    """
    _track_list = [None for x in range(search_results['tracks']['total'])]
    for idx, track in enumerate(search_results['tracks']['items']):
        transformed_track = _transform_track(track)
        _track_list[offset + idx] = transformed_track
    return _track_list


def _transform_track(track):
    """Transform result into a format that more
    closely matches our unified API.
    """
    transformed_track = dict([
        ('source_type', 'spotify'),
        ('source_id', track['id']),
        ('name', track['name']),
        ('duration_ms', track['duration_ms']),
        ('preview_url', track['preview_url']),
        ('track_number', track['track_number']),
        ('image_small', None),
        ('image_medium', None),
        ('image_large', None),
    ])
    transformed_track['artists'] = []
    for artist in track.get('artists', []):
        transformed_track['artists'].append(dict([
            ('source_type', 'spotify'),
            ('source_id', artist['id']),
            ('name', artist['name']),
        ]))
    transformed_track['album'] = dict([
        ('source_type', 'spotify'),
        ('source_id', track['album']['id']),
        ('name', track['album']['name']),
    ])
    if track['album']['images']:
        transformed_track['image_large'] = track['album']['images'][0]['url']
        try:
            transformed_track['image_medium'] = \
                track['album']['images'][1]['url']
        except:
            pass
        try:
            transformed_track['image_small'] = \
                track['album']['images'][2]['url']
        except:
            pass

    return transformed_track


class SpotifyClient(object):

    def login_url(self, callback_url, client_id, client_secret):
        """Generates a login url, for the user to authenticate the app."""
        url = 'https://accounts.spotify.com/authorize/?client_id={0}&response_type=code&redirect_uri={1}&scope=playlist-modify-public%20playlist-modify-private&state=profile%2Factivity'.format(
            client_id, callback_url
        )
        return url

    def exchange_code(self, code, callback_url, client_id, client_secret):
        """Fetch auth and user data from the spotify api

        Returns a dictionary of a auth and user object.
        """
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': callback_url,
            'client_id': client_id,
            'client_secret': client_secret
        }
        auth_data = _make_post_request(
            'https://accounts.spotify.com/api/token',
            data
        )

        user_data = _make_oauth_request(
            'https://api.spotify.com/v1/me', auth_data['access_token'])

        response = {
            'auth': auth_data,
            'user': user_data
        }

        return response

    def track(self, track_id):
        """Lookup an individual track using the Spotify Web API

        radiobabel uses a unified format to show lookup results across all
        supported sources. This allows simple interaction for clients and easy
        implementation of a unified search API in future.

        track_id (required): id of the Spotify track to retrieve metadata for.
        """
        url = 'https://api.spotify.com/v1/tracks/{0}'.format(track_id)
        logger.info('Track lookup: {0}'.format(track_id))
        try:
            track = _make_request(url)
        except:
            raise TrackNotFound('Spotify: {0}'.format(track_id))

        return _transform_track(track)

    def search(self, query, limit=20, offset=0):
        """Search for tracks using the spotify API
        """
        logger.info('Searching: Limit {0}, Offset {1}'.format(limit, offset))

        # Max limit for the spotify api is 20
        if limit > 20:
            limit = 20

        params = {'q': query, 'type': 'track',
                  'limit': limit, 'offset': offset}
        response = _make_request('https://api.spotify.com/v1/search', params)
        tracks = _transform_search_response(response, offset)

        return tracks