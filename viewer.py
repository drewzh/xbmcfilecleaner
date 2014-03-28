#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys

import xbmc
import xbmcgui
from xbmcaddon import Addon
from utils import Log, notify


# Addon info
__addonID__ = "script.filecleaner"
__addon__ = Addon(__addonID__)
__title__ = __addon__.getAddonInfo("name")
__profile__ = xbmc.translatePath(__addon__.getAddonInfo("profile")).decode("utf-8")


class LogViewerDialog(xbmcgui.WindowXMLDialog):
    CAPTIONID = 101
    TEXTBOXID = 201

    def __init__(self, *args, **kwargs):
        self.log = Log()
        self.caption = "Cleaning Log"
        xbmcgui.WindowXMLDialog.__init__(self)

    def onInit(self):
        self.getControl(self.CAPTIONID).setLabel(self.caption)
        if len(sys.argv) > 1:
            if sys.argv[1] == "show":
                self.getControl(self.TEXTBOXID).setText(self.log.get())
            elif sys.argv[1] == "trim":
                # TODO: File is not trimmed yet
                self.getControl(self.TEXTBOXID).setText(self.log.trim())
            elif sys.argv[1] == "clear":
                self.getControl(self.TEXTBOXID).setText(self.log.clear())
            else:
                self.getControl(self.TEXTBOXID).setText("Unknown argument %r" % sys.argv[1])
        else:
            self.getControl(self.TEXTBOXID).setText("Too few arguments")


def show_logviewer():
    path = __addon__.getAddonInfo("path")
    win = LogViewerDialog("DialogLogViewer.xml", path, "Default")
    win.doModal()
    del win


if __name__ == "__main__":
    # TODO: Reuse window when buttons are pressed
    show_logviewer()