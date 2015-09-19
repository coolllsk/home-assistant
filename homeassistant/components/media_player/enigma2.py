"""
homeassistant.components.media_player.enigma2
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provides an interface to the Enigma2/Dreambox Webinterface

Configuration:

media_player:
  platform: enigma2
  name: Dreambox
  url: http://192.168.0.123

Variables:

name
*Optional
The name of the device.

url
*Required
The URL of the Enigma2 Webinterface. Example: http://192.168.0.123

"""

import re
import urllib
import logging
import xml.etree.ElementTree as ET

from homeassistant.components.media_player import (
    MediaPlayerDevice, SUPPORT_PAUSE, SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_MUTE, MEDIA_TYPE_VIDEO)
from homeassistant.const import (
    STATE_IDLE, STATE_PLAYING, STATE_PAUSED, STATE_OFF)

_LOGGER = logging.getLogger(__name__)

SUPPORT_ENIGMA = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE

DEVICEINFO_ENDPOINT = '/web/deviceinfo'
CURRENT_ENDPOINT = '/web/getcurrent'
VOLUME_ENDPOINT = '/web/vol'
#POWERSTATE_ENDPOINT = '/web/powerstate'

RE_SERVICE_NAME_SANITIZE = re.compile(r' \([^ \)]+\)$')

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Enigma2/Dreambox platform. """

    add_devices([
        Enigma2Device(
            config.get('name', 'Dreambox'),
            config.get('url')),
    ])


class Enigma2Device(MediaPlayerDevice):
    """ Represents a Enigma2/Dreambox device. """

    # pylint: disable=too-many-public-methods

    def __init__(self, name, url, timeout=8):
        self._name = name

        self._url = url
        self._e2version = None  # Enigma 2 version
        self._device_type = None
        self._timeout = timeout

        self._player_state = STATE_OFF
        self._volume_level = 1.0
        self._volume_muted = False

        self._service_name = None
        self._event_title = None
        self._event_duration = None

        self.update()

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        # TODO support other states, e.g. STATE_PAUSED
        return self._player_state

    @property
    def should_poll(self):
        """ We will push an update after each command. """
        return True

    @property
    def volume_level(self):
        """ Volume level of the media player (0..1). """
        return self._volume_level

    @property
    def is_volume_muted(self):
        """ Boolean if volume is currently muted. """
        return self._volume_muted

    @property
    def media_content_id(self):
        """ Content ID of current playing media. """
        return '1'

    @property
    def media_title(self):
        """ Title of current playing media. """
        return self._generate_media_title()

    @property
    def media_content_type(self):
        """ Content type of current playing media. """
        return MEDIA_TYPE_VIDEO

    @property
    def media_duration(self):
        """ Duration of current playing media in seconds. """
        return self._event_duration

    @property
    def supported_media_commands(self):
        """ Flags of media commands that are supported. """
        return SUPPORT_ENIGMA

    def mute_volume(self, mute):
        """ mute the volume. """
        # TODO
        self._volume_muted = mute

    def set_volume_level(self, volume):
        """ set volume level, range 0..1. """
        # TODO
        self._volume_level = volume

    def update(self):
        device = self._get_device_info()
        if not device:
            # Device is offline or N/A
            self._player_state = STATE_OFF
            #self.update_ha_state()
            return

        self._device_type = device['type']
        self._e2version = device['enigma_version']

        if not self._fetch_current():
            self._player_state = STATE_IDLE
            #self.update_ha_state()
            return

        self._player_state = STATE_PLAYING
        #self.update_ha_state()

    def _get_device_info(self):
        """ Get device info """
        root = self._get_xml_endpint(DEVICEINFO_ENDPOINT)

        if not root:
            return None

        mapping = {
            'type': 'e2devicename',
            #'interface_version': 'e2webifversion',
            'enigma_version': 'e2enigmaversion'
        }

        return self._xml_values(root, mapping)

    def _fetch_current(self):
        """ Fetch current station and programme """
        root = self._get_xml_endpint(CURRENT_ENDPOINT)

        if not root:
            return False

        service_tree = root.find('e2service')
        if service_tree is None:
            return False

        service_name = service_tree.find('e2servicename')
        if service_name is None:
            return False

        # Sanitize Service Name
        service_name = service_name.text
        service_name = RE_SERVICE_NAME_SANITIZE.sub('', service_name)
        self._service_name = service_name

        event_tree = root.find('e2eventlist')
        if not event_tree:
            return False

        event_et = event_tree.findall('e2event')
        if event_et is None:
            return False

        event = event_et[0]

        self._event_title = self._xml_element_content(event, 'e2eventtitle')
        self._event_duration = self._xml_element_content(event, 'e2eventduration')

        return True

    def _generate_media_title(self):
        """ Generates media title for HA from current service and programme """
        if not self._service_name or not self._event_title:
            return 'N/A'

        title = '%s - %s' % (self._service_name, self._event_title)
        return title

    @staticmethod
    def _xml_values(tree, mapping):
        values = {}
        for key, match in mapping.items():
            element = tree.find(match)
            if element is not None:
                values[key] = element.text
            else:
                values[key] = None
        return values

    def _get_xml_endpint(self, endpoint):
        try:
            response = urllib.request.urlopen(self._url + endpoint,
                                              timeout=self._timeout)
        except urllib.error.URLerror:
            return None

        root = ET.fromstring(response.read().decode('utf-8'))
        return root

    def _xml_element_content(self, tree, element_name):
        element = tree.find(element_name)
        if element is None:
            return None
        return element.text
