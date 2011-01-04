import xbmc, xbmcgui, xbmcaddon, os, math
from pysqlite2 import dbapi2 as sqlite

# Addon info
__title__ = 'XBMC File Cleaner'
__author__ = 'Andrew Higginson <azhigginson@gmail.com>'
__addonID__	= "script.filecleaner"
__settings__ = xbmcaddon.Addon(__addonID__)

# Autoexec info
AUTOEXEC_PATH = xbmc.translatePath('special://home/userdata/autoexec.py')
AUTOEXEC_FOLDER_PATH = xbmc.translatePath('special://home/userdata/')
AUTOEXEC_SCRIPT = '\nimport time;time.sleep(5);xbmc.executebuiltin("XBMC.RunScript(special://home/addons/script.filecleaner/default.py,-startup)")\n'

class Main:

    def __init__(self):
        # Get Settings
        self.serviceEnabled = bool(__settings__.getSetting('service_enabled') == "true")
        self.showNotifications = bool(__settings__.getSetting('show_notifications') == "true")
        self.checkInterval = float(__settings__.getSetting('check_interval'))
        self.expireAfter = float(__settings__.getSetting('expire_after'))
        self.deleteWatched = bool(__settings__.getSetting('delete_watched') == "true")
        self.deleteOnDiskLow = bool(__settings__.getSetting('delete_on_low_disk') == "true")
        self.lowDiskPercentage = float(__settings__.getSetting('low_disk_percentage'))
        self.lowDiskPath = __settings__.getSetting('low_disk_path')
        self.updateLibrary = bool(__settings__.getSetting('update_library') == "true")

        # Set or remove auto startup
        self.autoStart(self.serviceEnabled)

        if self.serviceEnabled == True:
            # Cancel any alarms already set
            xbmc.executebuiltin('XBMC.CancelAlarm(%s, true)' % (__addonID__))

            self.notify(__settings__.getLocalizedString(30013))

            # Set the alarm again if service is enabled
            if self.serviceEnabled == True:
                xbmc.executebuiltin('XBMC.AlarmClock(%s, XBMC.RunScript(%s), %d, true)' % (__addonID__, __addonID__, self.checkInterval * 60 * 24))
            
            if (self.deleteOnDiskLow == True and self.isDiskSpaceLow() == True) or self.deleteOnDiskLow == False:
                # Get expired videos and delete from file system
                files = self.getExpired()
                
                # Delete all returned files
                for file in files:
                    self.deleteFile(file)
             
            # Finally update the library to account for any deleted videos
            if self.updateLibrary == True:
                xbmc.executebuiltin("XBMC.UpdateLibrary(video)")
        else:
            self.notify(__settings__.getLocalizedString(30015))
            
    # Get all expired videos from the library database
    def getExpired(self):
        try:
            con = sqlite.connect(xbmc.translatePath('special://database/MyVideos34.db'))
            cur = con.cursor()
            sql = "SELECT strFilename FROM files, episode WHERE episode.idFile = files.idFile AND lastPlayed < date('now', '-%d days')" % (self.expireAfter)
            
            # If set, only query 'watched' files
            if self.deleteWatched == True:
                sql = sql + " AND playCount > 0"
                
            cur.execute(sql)
            
            # Return list of files to delete
            return [element[0] for element in cur.fetchall()]
        except:
            self.notify(__settings__.getLocalizedString(30012))
            raise

    # Returns true if running out of disk space
    def isDiskSpaceLow(self):
        diskStats = os.statvfs(xbmc.translatePath(self.lowDiskPath))
        diskCapacity = diskStats.f_frsize * diskStats.f_blocks
        diskFree = diskStats.f_frsize * diskStats.f_bavail
        diskFreePercent = math.ceil(float(100) / float(diskCapacity) * float(diskFree))

        return (float(diskFreePercent) < float(self.lowDiskPercentage))

    # Delete file from the OS
    def deleteFile(self, file):
        self.notify(__settings__.getLocalizedString(30014) + ' ' + file)

    # Display notification on screen and send to log
    def notify(self, message):
        xbmc.log('::' + __title__ + '::' + message)
        if self.showNotifications == True:
            xbmc.executebuiltin('XBMC.Notification(%s, %s)' % (__title__, message))
            
    def autoStart(self, option):
	    # See if the autoexec.py file exists
	    if (os.path.exists(AUTOEXEC_PATH)):
		    # Var to check if we're in autoexec.py
		    found = False
		    autoexecfile = file(AUTOEXEC_PATH, 'r')
		    filecontents = autoexecfile.readlines()
		    autoexecfile.close()

		    # Check if we're in it
		    for line in filecontents:
			    if line.find(__addonID__) > 0:
				    found = True

		    # If the autoexec.py file is found and we're not in it,
		    if (not found and option):
			    autoexecfile = file(AUTOEXEC_PATH, 'w')
			    filecontents.append(AUTOEXEC_SCRIPT)
			    autoexecfile.writelines(filecontents)            
			    autoexecfile.close()

		    # Found that we're in it and it's time to remove ourselves
		    if (found and not option):
			    autoexecfile = file(AUTOEXEC_PATH, 'w')
			    for line in filecontents:
				    if not line.find(__addonID__) > 0:
					    autoexecfile.write(line)
			    autoexecfile.close()

	    else:
		    if (os.path.exists(AUTOEXEC_FOLDER_PATH)):
			    autoexecfile = file(AUTOEXEC_PATH, 'w')
			    autoexecfile.write (AUTOEXEC_SCRIPT.strip())
			    autoexecfile.close()
		    else:
			    os.makedirs(AUTOEXEC_FOLDER_PATH)
			    autoexecfile = file(AUTOEXEC_PATH, 'w')
			    autoexecfile.write (AUTOEXEC_SCRIPT.strip())
			    autoexecfile.close()

run = Main()
