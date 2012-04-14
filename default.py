import os
import sys
import shutil
import math
import time
import xbmc 
import xbmcgui
import xbmcaddon
from pysqlite2 import dbapi2 as sqlite

# Addon info
__title__ = 'XBMC File Cleaner'
__author__ = 'Andrew Higginson <azhigginson@gmail.com>'
__addonID__ = "script.filecleaner"
__icon__ = 'special://home/addons/' + __addonID__ + '/icon.png'
__settings__ = xbmcaddon.Addon(__addonID__)

# Autoexec info
AUTOEXEC_PATH = xbmc.translatePath('special://home/userdata/autoexec.py')
AUTOEXEC_FOLDER_PATH = xbmc.translatePath('special://home/userdata/')
AUTOEXEC_SCRIPT = '\nimport time;time.sleep(5);xbmc.executebuiltin("XBMC.RunScript(special://home/addons/script.filecleaner/default.py,-startup)")\n'

class Main:
    
    def __init__(self):
        """
        Create a Main object that performs regular cleaning of watched videos.
        """
        reload(sys)
        sys.setdefaultencoding('utf-8')
        
        self.refresh_settings()
        
        if self.serviceEnabled:
            self.notify(__settings__.getLocalizedString(30013))
        
        # Main service loop
        while self.serviceEnabled:
            self.refresh_settings()
            self.cleanup()
            # only run once every half hour
            time.sleep(1800)
        
        # Cleaning is disabled, do nothing
        self.notify(__settings__.getLocalizedString(30015))
        
    def cleanup(self):
        """
        Delete any watched videos from the XBMC video database.
        The videos to be deleted are subject to a number of criteria as can be specified in the addon's settings.
        """
        self.debug(__settings__.getLocalizedString(30009))
        if not self.deleteOnDiskLow or (self.deleteOnDiskLow and self.disk_space_low()):
            doClean = False
            
            if self.deleteMovies:
                movies = self.get_expired('movie')
                if movies:
                    for file, path in movies:
                        if os.path.exists(path):
                            doClean = True
                        if self.enableHolding:
                            self.debug("Moving %s to %s" % (file, self.holdingFolder))
                            self.move_file(path, self.holdingFolder)
                        else:
                            self.debug("Deleting %s" % (file))
                            self.delete_file(path)
            
            if self.deleteTVShows:
                episodes = self.get_expired('episode')
                if episodes:
                    for file, path, show, season, idFile in episodes:
                        if os.path.exists(path):
                            doClean = True
                        if self.enableHolding:
                            if self.createSeriesSeasonDirs:
                                newpath = os.path.join(
                                    self.holdingFolder,
                                    show,
                                    "Season " + season
                                )
                                self.createseasondirs(newpath)
                            else:
                                newpath = self.holdingFolder
                            self.debug("Moving %s to %s" % (file, newpath))
                            moveOk = self.move_file(path, newpath)
                            if self.doupdatePathReference and moveOk:
                                self.updatePathReference(idFile, newpath)
                        else:
                            self.debug("Deleting %s" % (file))
                            self.delete_file(path)
            
            # Finally clean the library to account for any deleted videos
            if doClean and self.cleanLibrary:
                time.sleep(10) # Wait 10 seconds for deletions to finish
                xbmc.executebuiltin("XBMC.CleanLibrary(video)")
    
    def get_expired(self, option):
        """
        Retrieve a list of episodes that have been watched and match any criteria set in the addon's settings.
        """
        try:
            results = []
            folder = os.listdir(xbmc.translatePath('special://database/'))
            for database in folder:
                # Check all video databases
                if database.startswith('MyVideos') and database.endswith('.db'):
                    con = sqlite.connect(xbmc.translatePath('special://database/' + database))
                    cur = con.cursor()
                    
                    if option == 'movie':
                        query = "SELECT files.strFilename as filename, path.strPath || files.strFilename as full_path "
                        query += "FROM files, path, %s " % option
                        query += "WHERE %s.idFile = files.idFile " % option
                        if self.enableHolding:
                            query += "AND NOT path.strPath like '%s%%' " % self.holdingFolder
                        query += "AND files.idPath = path.idPath "
                        if self.enableExpire:
                            query += "AND files.lastPlayed < datetime('now', '-%f days', 'localtime') " % self.expireAfter
                        query += "AND playCount > 0"
                        if self.deleteLowRating:
                            query += " AND c05+0 < %f" % self.lowRatingFigure
                            if self.ignoreNoRating:
                              query += " AND c05 > 0"
                    
                    elif option == 'episode':
                        query = "SELECT files.strFilename as filename, path.strPath || files.strFilename as full_path, tvshow.c00 as showname, episode.c12 as episodeno, files.idFile "
                        query += "FROM files, path, %s, tvshow, tvshowlinkepisode " % option
                        query += "WHERE %s.idFile = files.idFile " % option
                        if self.enableHolding:
                            query += "AND NOT path.strPath like '%s%%' " % self.holdingFolder
                        query += "AND files.idPath = path.idPath "
                        query += "AND tvshowlinkepisode.idEpisode = episode.idEpisode "
                        query += "AND tvshowlinkepisode.idShow = tvshow.idShow "
                        if self.enableExpire:
                            query += "AND files.lastPlayed < datetime('now', '-%f days', 'localtime') " % self.expireAfter
                        query += "AND playCount > 0"
                        if self.deleteLowRating:
                            query += " AND c03+0 < %f" % self.lowRatingFigure
                            if self.ignoreNoRating:
                              query += " AND c03 > 0"
                    
                    self.debug('Executing query on ' + database + ': ' + str(query))
                    
                    cur.execute(query)
                    
                    # Append the results to the list of files to delete.
                    results += cur.fetchall()
                    
            return results
        except:
            # The video database(s) could not be opened
            self.notify(__settings__.getLocalizedString(30012))
            raise
    
    def update_path_reference(self, idFile, newPath):
        """
        Update file reference for a file
        
        Keyword arguments:
        idFile -- the id of the file to update the path reference for
        newPath -- the new location for the file
        """
        try:
            folder = os.listdir(xbmc.translatePath('special://database/'))
            for database in folder:
                if database.startswith('MyVideos') and database.endswith('.db'):
                    con = sqlite.connect(xbmc.translatePath('special://database/' + database))
                    cur = con.cursor()
                    
                    # Insert path if it doesn't exist
                    # path(strPath) is probably invalid and should read path.strPath instead.
                    query = 'INSERT OR IGNORE INTO\
                            path(strPath)\
                            values("%s/")' % (newPath)
                    self.debug('Executing query on ' + database + ': ' + str(query))
                    cur.execute(query)
                    
                    # Look up the id of the new path
                    query = 'SELECT idPath'
                    query += ' FROM path'
                    query += ' WHERE strPath = ("%s/")' % newPath
                    
                    self.debug('Executing ' + str(query))
                    cur.execute(query)
                    idPath = cur.fetchone()[0]
                    
                    # Update path reference for the moved file
                    query = 'UPDATE OR IGNORE files'
                    query += ' SET idPath = %d' % idPath
                    query += ' WHERE idFile = %d' % idFile
                    
                    self.debug('Executing query on ' + database + ': ' + str(query))
                    cur.execute(query)
                    con.commit()
        # TODO: Don't catch all exceptions
        except:
            # Error opening video library database
            self.notify(__settings__.getLocalizedString(30012))
            raise
    
    def refresh_settings(self):
        """
        Retrieve new values for all settings, in order to account for any changes.
        """
        __settings__ = xbmcaddon.Addon(__addonID__)
        
        self.serviceEnabled = bool(__settings__.getSetting('service_enabled') == "true")
        #self.scanInterval = float(__settings__.getSetting('scan_interval') == "true")
        self.showNotifications = bool(__settings__.getSetting('show_notifications') == "true")
        self.enableExpire = bool(__settings__.getSetting('enable_expire') == "true")
        self.expireAfter = float(__settings__.getSetting('expire_after'))
        self.deleteOnDiskLow = bool(__settings__.getSetting('delete_on_low_disk') == "true")
        self.lowDiskPercentage = float(__settings__.getSetting('low_disk_percentage'))
        self.lowDiskPath = xbmc.translatePath(__settings__.getSetting('low_disk_path'))
        self.cleanLibrary = bool(__settings__.getSetting('clean_library') == "true")
        self.deleteMovies = bool(__settings__.getSetting('delete_movies') == "true")
        self.deleteTVShows = bool(__settings__.getSetting('delete_tvshows') == "true")
        self.deleteLowRating = bool(__settings__.getSetting('delete_low_rating') == "true")
        self.lowRatingFigure = float(__settings__.getSetting('low_rating_figure'))
        self.ignoreNoRating = bool(__settings__.getSetting('ignore_no_rating') == "true")
        self.enableHolding = bool(__settings__.getSetting('enable_holding') == "true")
        self.holdingFolder = xbmc.translatePath(__settings__.getSetting('holding_folder'))
        self.holdingExpire = int(__settings__.getSetting('holding_expire'))
        self.enableDebug = bool(xbmc.translatePath(__settings__.getSetting('enable_debug')) == "true")
        self.createSeriesSeasonDirs = bool(xbmc.translatePath(__settings__.getSetting('create_series_season_dirs')) == "true")
        self.doupdatePathReference = bool(xbmc.translatePath(__settings__.getSetting('update_path_reference')) == "true")
        
        # Set or remove autoexec.py line
        self.toggle_auto_start(self.serviceEnabled)
        return True
    
    def disk_space_low(self):
        """
        Check if the disk is running low on free space.
        Returns true if the free space is less than the threshold specified in the addon's settings.
        """
        diskStats = os.statvfs(self.lowDiskPath)
        diskCapacity = diskStats.f_frsize * diskStats.f_blocks
        diskFree = diskStats.f_frsize * diskStats.f_bavail
        diskFreePercent = math.ceil(float(100) / float(diskCapacity) * float(diskFree))
        
        return (float(diskFreePercent) < float(self.lowDiskPercentage))
    
    def delete_file(self, file):
        """
        Delete a file from the file system.
        """
        if os.path.exists(file):
            os.remove(file)
            # Deleted
            self.notify(__settings__.getLocalizedString(30014) % (os.path.basename(file), file), 10000)
    
    def move_file(self, file, destination):
        """
        Move a file to a new destination.
        
        Keyword arguments:
        file -- the file to be moved
        destination -- the new location of the file
        """
        try:
            if os.path.exists(file) and os.path.exists(destination):
                newfile = os.path.join(destination, os.path.basename(file))
                shutil.move(file, newfile)
                # Deleted
                self.notify(__settings__.getLocalizedString(30025) % (file), 10000)
                return True;
            else:
                if not os.path.exists(file):
                    self.notify("Can not move file %s as it doesn't exist" % (file), 10000);
                else:
                    self.notify("Can not move file, destination %s unavailable" % (destination), 10000);
                return False;
        except:
            self.debug("Failed to move file");
            return False;
    
    def create_season_dirs(self, seasondir):
        """
        Create season as well as series directories in the folder specified.
        
        Keyword arguments:
        seasondir -- the directory in which to create the folder(s)
        """
        seriesdir = os.path.dirname(seasondir)
        
        # Create series directory if it doesn't exist
        self.debug("Creating directory %s" % (seriesdir))
        try:
            os.mkdir(seriesdir)
            self.debug("Successfully created directory")
        except:
            self.debug("The directory already exists")
        
        # Create season directory if it doesn't exist
        self.debug("Creating directory %s" % (seasondir))
        try:
            os.mkdir(seasondir)
            self.debug("Successfully created directory")
        except:
            self.debug("The directory already exists")
    
    def create_directory(self, location):
        '''
        Creates a directory at the location provided.
        '''
    
    def notify(self, message, duration=5000, image=__icon__):
        '''
        Display an XBMC notification and log the message.
        
        Keyword arguments:
        message -- the message to be displayed and logged
        duration -- the duration the notification is displayed in milliseconds (default 5000)
        image -- the path to the image to be displayed on the notification (default "icon.png")
        '''
        self.debug(message)
        if self.showNotifications:
            xbmc.executebuiltin('XBMC.Notification(%s, %s, %s, %s)' % (__title__, message, duration, image))
    
    def debug(self, message):
        '''
        logs a debug message
        '''
        if self.enableDebug:
            xbmc.log('::' + __title__ + '::' + message)
    
    def toggle_auto_start(self, option):
        '''
        sets or removes autostart line in special://home/userdata/autoexec.py
        this function needs to be updated to work as an XBMC service
        '''
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

            # If the autoexec.py file is found and we're not in it
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
