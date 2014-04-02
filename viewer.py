#!/usr/bin/python
# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
from xbmcaddon import Addon
import utils


# Addon info
__addonID__ = "script.filecleaner"
__addon__ = Addon(__addonID__)
__title__ = __addon__.getAddonInfo("name")
__profile__ = xbmc.translatePath(__addon__.getAddonInfo("profile")).decode("utf-8")


class LogViewerDialog(xbmcgui.WindowXMLDialog):
    CAPTIONID = 101
    TEXTBOXID = 201
    TRIMBUTTONID = 301
    CLEARBUTTONID = 302

    def __init__(self, xml_filename, script_path, default_skin="Default", default_res="720p", *args, **kwargs):
        self.log = utils.Log()
        self.caption = "Cleaning Log"
        xbmcgui.WindowXMLDialog.__init__(self)

    def onInit(self):
        self.getControl(self.CAPTIONID).setLabel(self.caption)
        self.getControl(self.TEXTBOXID).setText(self.log.get())

    def onClick(self, control_id, *args):
        if control_id == self.TRIMBUTTONID:
            if xbmcgui.Dialog().yesno("Are you sure?", "This will trim the log file, keeping the first 15 lines.",
                                      "This action is irreversible. Do you wish to continue?"):
                self.getControl(self.TEXTBOXID).setText(self.log.trim())
        elif control_id == self.CLEARBUTTONID:
            if xbmcgui.Dialog().yesno("Are you sure?", "This will delete the entire contents of the log file.",
                                      "This action is irreversible. Do you wish to continue?"):
                self.getControl(self.TEXTBOXID).setText(self.log.clear())
        else:
            utils.debug("Unknown button pressed", xbmc.LOGERROR)


if __name__ == "__main__":
    win = LogViewerDialog("DialogLogViewer.xml", __addon__.getAddonInfo("path"))
    win.doModal()
    del win