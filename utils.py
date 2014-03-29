#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import time
import xbmc
from xbmcaddon import Addon
import settings  # TODO: No idea why I can't use "from settings import *" here.


# Addon info
__addonID__ = "script.filecleaner"
__addon__ = Addon(__addonID__)
__title__ = __addon__.getAddonInfo("name")
__profile__ = xbmc.translatePath(__addon__.getAddonInfo("profile")).decode("utf-8")
__icon__ = xbmc.translatePath(__addon__.getAddonInfo("icon")).decode("utf-8")


class Log(object):
    def __init__(self):
        self.logpath = os.path.join(__profile__, "cleaner.log")

    def prepend(self, data):
        """
        Prepend the given data to the current log file. Will create a new log file if none exists.

        :type data: list
        :param data: A list of strings to prepend to the log file.
        """
        try:
            debug("Prepending the log file with new data.")
            debug("Backing up current log.")
            f = open(self.logpath, "a+")  # use append mode to make sure it is created if non-existent
            previous_data = f.read()
        except (IOError, OSError) as err:
            debug("%s" % err, xbmc.LOGERROR)
        else:
            f.close()

            try:
                debug("Writing new log data.")
                f = open(self.logpath, "w")
                if data:
                    f.write("[B][%s][/B]\n" % time.strftime("%d/%m/%Y \t %H:%M:%S"))
                    for line in data:
                        f.write("\t-\t%s\n" % line)
                    f.write("\n")
                    debug("New data written to log file.")
                else:
                    debug("No data to write. Stopping.")

                debug("Appending previous log file contents.")
                f.writelines(previous_data)
            except (IOError, OSError) as err:
                debug("%s" % err, xbmc.LOGERROR)
            else:
                f.close()

    def trim(self, lines_to_keep=15):
        """
        Trim the log file to contain a maximum number of lines.

        :type lines_to_keep: int
        :param lines_to_keep: The number of lines to preserve. Any lines below this number get erased. Defaults to 15.
        :rtype: str
        :return: The contents of the log file after trimming.
        """
        try:
            debug("Trimming log file contents. Keeping the top %d lines" % lines_to_keep)
            f = open(self.logpath, "r+")
            lines = []
            for i in xrange(lines_to_keep):
                lines.append(f.readline())

            f.truncate()
            f.writelines(lines)
        except (IOError, OSError) as err:
            debug("%s" % err, xbmc.LOGERROR)
        else:
            f.close()
            return self.get()

    def clear(self):
        """
        Erase the contents of the log file.

        :rtype: str
        :return: An empty string if clearing succeeded.
        """
        try:
            debug("Clearing log file contents.")
            f = open(self.logpath, "r+")
            f.truncate()
        except (IOError, OSError) as err:
            debug("%s" % err, xbmc.LOGERROR)
        else:
            f.close()
            return self.get()

    def get(self):
        """
        Retrieve the contents of the log file.

        :rtype: str
        :return: The contents of the log file.
        """
        try:
            debug("Retrieving log file contents.")
            f = open(self.logpath, "r")
        except (IOError, OSError) as err:
            debug("%s" % err, xbmc.LOGERROR)
        else:
            contents = f.read()
            f.close()
            return contents


def translate(msg_id):
    """
    Retrieve a localized string by id.

    :type msg_id: int
    :param msg_id: The id of the localized string.
    :rtype: str
    :return: The localized string. Empty if msg_id is not an integer.
    """
    if isinstance(msg_id, int):
        return __addon__.getLocalizedString(msg_id)
    else:
        return ""


def notify(message, duration=5000, image=__icon__, level=xbmc.LOGNOTICE):
    """Display an XBMC notification and log the message.

    :type message: str
    :param message: the message to be displayed (and logged). You may also use the id (int) for localization.
    :type duration: int
    :param duration: the duration the notification is displayed in milliseconds (default 5000)
    :type image: str
    :param image: the path to the image to be displayed on the notification (default "icon.png")
    :type level: int
    :param level: (Optional) the log level (supported values are found at xbmc.LOG...)
    """
    debug(message, level)
    if settings.get_setting(settings.notifications_enabled) and not (settings.get_setting(settings.notify_when_idle) and xbmc.Player().isPlayingVideo()):
        xbmc.executebuiltin("XBMC.Notification(%s, %s, %s, %s)" % (__title__, message, duration, image))


def debug(message, level=xbmc.LOGNOTICE):
    """Write a debug message to xbmc.log

    :type message: basestring
    :param message: the message to log
    :type level: int
    :param level: (Optional) the log level (supported values are found at xbmc.LOG...)
    """
    if settings.get_setting(settings.debugging_enabled):
        if isinstance(message, unicode):
            message = message.encode("utf-8")
        for line in message.splitlines():
            xbmc.log(msg=__title__ + ": " + line, level=level)