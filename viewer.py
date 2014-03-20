#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import xbmc
from xbmcaddon import Addon

# Addon info
__addonID__ = "script.filecleaner"
__addon__ = Addon(__addonID__)
__title__ = __addon__.getAddonInfo("name")
__profile__ = xbmc.translatePath(__addon__.getAddonInfo('profile')).decode('utf-8')
__author__ = "Anthirian, drewzh"
__icon__ = "special://home/addons/" + __addonID__ + "/icon.png"
__logfile__ = os.path.join(__profile__, "cleaner.log")


class Viewer:
    # constants
    WINDOW = 10147
    CONTROL_LABEL = 1
    CONTROL_TEXTBOX = 5

    def __init__(self, *args, **kwargs):
        xbmc.executebuiltin("ActivateWindow(%d)" % (self.WINDOW,))
        self.window = xbmcgui.Window(self.WINDOW)
        xbmc.sleep(100)  # give window time to initialize
        self.populate_window()

    def populate_window(self):
        heading = "Cleaning log"
        try:
            f = open(__logfile__)
        except (IOError, OSError) as error:
            xbmc.log("%s: %s" % (__title__, error), xbmc.LOGERROR)
        else:
            self.window.getControl(self.CONTROL_LABEL).setLabel("%s - %s" % (heading, __title__,))
            self.window.getControl(self.CONTROL_TEXTBOX).setText(f.read())
            f.close()

if __name__ == "__main__":
    try:
        Viewer()
    except Exception, ex:
        xbmc.log("%s: %s" % (__addonname__, ex), xbmc.LOGERROR)
