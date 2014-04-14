#!/usr/bin/python
# -*- coding: utf-8 -*-

import xbmc
import utils
from xbmcaddon import Addon

# Addon info
__addonID__ = "script.filecleaner"
__addon__ = Addon(__addonID__)

# Exhaustive list of constants as used by the addon's settings
service_enabled = "service_enabled"
delete_folders = "delete_folders"
ignore_extensions = "ignore_extensions"

delete_related = "delete_related"
delayed_start = "delayed_start"
scan_interval = "scan_interval"

notifications_enabled = "notifications_enabled"
notify_when_idle = "notify_when_idle"
debugging_enabled = "debugging_enabled"

clean_xbmc_library = "clean_xbmc_library"
delete_movies = "delete_movies"
delete_tv_shows = "delete_tv_shows"
delete_music_videos = "delete_music_videos"
delete_when_idle = "delete_when_idle"

enable_expiration = "enable_expiration"
expire_after = "expire_after"

delete_when_low_rated = "delete_when_low_rated"
minimum_rating = "minimum_rating"
ignore_no_rating = "ignore_no_rating"

delete_when_low_disk_space = "delete_when_low_disk_space"
disk_space_threshold = "disk_space_threshold"
disk_space_check_path = "disk_space_check_path"

delete_files = "delete_files"
holding_folder = "holding_folder"
create_subdirs = "create_subdirs"

not_in_progress = "not_in_progress"

exclusion_enabled = "exclusion_enabled"
exclusion1 = "exclusion1"
exclusion2 = "exclusion2"
exclusion3 = "exclusion3"

bools = [service_enabled, delete_folders, delete_related, notifications_enabled, notify_when_idle, debugging_enabled,
         clean_xbmc_library, delete_movies, delete_tv_shows, delete_music_videos, delete_when_idle, enable_expiration,
         delete_when_low_rated, ignore_no_rating, delete_when_low_disk_space, delete_files, create_subdirs,
         not_in_progress, exclusion_enabled]
strings = [ignore_extensions]
numbers = [delayed_start, scan_interval, expire_after, minimum_rating, disk_space_threshold]
paths = [disk_space_check_path, holding_folder, create_subdirs, exclusion1, exclusion2, exclusion3]

available_settings = bools + strings + numbers + paths


def get_setting(setting):
    """
    Get the value for a specified setting.

    Note: Make sure to check the return type of the setting you get.

    :param setting: The setting you want to retrieve the value of.
    :return: The value corresponding to the provided setting. This can be a float, a bool, a string or None.
    """
    if setting in bools:
        return bool(__addon__.getSetting(setting) == "true")
    elif setting in numbers:
        return float(__addon__.getSetting(setting))
    elif setting in strings:
        return str(__addon__.getSetting(setting))
    elif setting in paths:
        return xbmc.translatePath(__addon__.getSetting(setting))
    else:
        utils.debug("Could not retrieve the value of %r. The type is unknown.", xbmc.LOGWARNING)
        return None


def load_all():
    """
    Get the values for all settings.

    Note: Make sure to check the return type of settings you get.

    :rtype: dict
    :return: All settings and their current values.
    """
    settings = dict()
    for s in bools + strings + numbers + paths:
        print s
        settings[s] = get_setting(s)
    return settings
