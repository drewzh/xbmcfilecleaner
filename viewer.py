#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
import xbmc
import xbmcgui
from xbmcaddon import Addon
from utils import debug, notify

# Addon info
__addonID__ = "script.filecleaner"
__addon__ = Addon(__addonID__)
__title__ = __addon__.getAddonInfo("name")
__profile__ = xbmc.translatePath(__addon__.getAddonInfo("profile")).decode("utf-8")
__author__ = "Anthirian, drewzh"
__icon__ = xbmc.translatePath(__addon__.getAddonInfo("icon")).decode("utf-8")
__logfile__ = os.path.join(__profile__, "cleaner.log")


class LogViewer(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.caption = kwargs.get("caption", "")
        self.text = kwargs.get("text", "")
        xbmcgui.WindowXMLDialog.__init__(self)

    def onInit(self):
        self.getControl(101).setLabel(self.caption)
        self.getControl(201).setText(self.text)


def show_logviewer(windowtitle, text):
    path = __addon__.getAddonInfo("path")
    win = LogViewer("DialogLogViewer.xml", path, "Default", caption=windowtitle, text=text)
    win.doModal()
    del win

#The following will actually display the dialog

try:
    f = open(__logfile__)
except (IOError, OSError) as error:
    xbmc.log("%s: %s" % (__title__, error), xbmc.LOGERROR)
else:
    # TODO: Extra argumenten mee geven en op basis daarvan een actie bepalen
    caption = "Cleaning Log"
    if len(sys.argv) > 1:
        caption += " - %s" % sys.argv[1]
    show_logviewer(caption, f.read())
    f.close()