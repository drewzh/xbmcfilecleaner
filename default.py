import os
import sys
import shutil
import math
import time
import xbmc
import xbmcaddon
import sqlite3

# Addon info
__title__ = 'XBMC File Cleaner'
__author__ = 'Andrew Higginson <azhigginson@gmail.com>'
__addonID__ = "script.filecleaner"
__icon__ = 'special://home/addons/' + __addonID__ + '/icon.png'
__settings__ = xbmcaddon.Addon(__addonID__)

# Autoexec info
AUTOEXEC_PATH = xbmc.translatePath('special://home/userdata/autoexec.py')
AUTOEXEC_SCRIPT = 'import time;time.sleep(5);xbmc.executebuiltin("XBMC.RunScript(special://home/addons/script.filecleaner/default.py,-startup)")'

class Main:
    
    def __init__(self):
        """
        Create a Main object that performs regular cleaning of watched videos.
        """
        reload(sys)
        sys.setdefaultencoding('utf-8')
        self.reload_settings()
        
        if self.removeFromAutoExec:
            self.debug("Checking for presence of the old script in " + AUTOEXEC_PATH)
            self.disable_autoexec()
        
        if self.serviceEnabled:
            self.notify(__settings__.getLocalizedString(30013))
        
        # wait delayedStart minutes upon startup
        time.sleep(self.delayedStart * 60)
        
        # Main service loop
        while (not xbmc.abortRequested and self.serviceEnabled):
            self.reload_settings()
            self.cleanup()
            
            # wait for scanInterval minutes to rescan
            time.sleep(self.scanInterval * 60)
        
        # Cleaning is disabled or abort is requested by XBMC, so do nothing
        self.notify(__settings__.getLocalizedString(30015))
        
    def cleanup(self):
        """
        Delete any watched videos from the XBMC video database.
        The videos to be deleted are subject to a number of criteria as can be specified in the addon's settings.
        """
        self.debug(__settings__.getLocalizedString(30009))
        if not self.deleteOnDiskLow or (self.deleteOnDiskLow and self.disk_space_low()):
            cleaningRequired = False
            
            if self.deleteMovies:
                movies = self.get_expired('movie')
                if movies:
                    for file, path in movies:
                        if os.path.exists(path):
                            cleaningRequired = True
                        if self.enableHolding:
                            self.debug("Moving movie %s from %s to %s" % (os.path.basename(file), path, self.holdingFolder))
                            self.move_file(path, self.holdingFolder)
                        else:
                            self.debug("Deleting movie %s from %s" % (os.path.basename(file), path))
                            self.delete_file(path)
            
            if self.deleteTVShows:
                episodes = self.get_expired('episode')
                if episodes:
                    for file, path, show, season, idFile in episodes:
                        if os.path.exists(path):
                            cleaningRequired = True
                        if self.enableHolding:
                            if self.createSeriesSeasonDirs:
                                newpath = os.path.join(
                                    self.holdingFolder,
                                    show,
                                    "Season " + season
                                )
                                self.create_season_dirs(newpath)
                            else:
                                newpath = self.holdingFolder
                            self.debug("Moving episode %s from %s to %s" % (os.path.basename(file), os.path.dirname(file), newpath))
                            moveOk = self.move_file(path, newpath)
                            if self.doupdatePathReference and moveOk:
                                self.updatePathReference(idFile, newpath)
                        else:
                            self.delete_file(path)
            
            # Finally clean the library to account for any deleted videos.
            if self.cleanLibrary and cleaningRequired:
                # Wait 10 seconds for deletions to finish before cleaning.
                time.sleep(10)
                
                # Check if the library is being updated before cleaning up
                while (xbmc.getCondVisibility('Library.IsScanningVideo')  == True):
                    pause = 5
                    iterations = 0
                    limit = self.scanInterval - pause
                    
                    # Make sure we don't mess up the scan interval timing by waiting too long.
                    if (iterations * pause >= limit):
                        break
                        
                    self.debug("The video library is currently being updated, waiting %d minutes before cleaning up." % pause)
                    time.sleep(pause * 60)
                
                xbmc.executebuiltin("XBMC.CleanLibrary(video)")
    
    def get_expired(self, option):
        """
        Retrieve a list of episodes that have been watched and match any criteria set in the addon's settings.
        
        Keyword arguments:
        option -- the type of videos to remove, can be either 'movie' or 'episode.'
        """
        try:
            results = []
            margin = 0.000001
            folder = os.listdir(xbmc.translatePath('special://database/'))
            for database in folder:
                # Check all video databases
                if database.startswith('MyVideos') and database.endswith('.db'):
                    con = sqlite3.connect(xbmc.translatePath('special://database/' + database))
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
                            query += " AND %s.c05 BETWEEN %f AND %f" % (option, (margin if self.ignoreNoRating else 0), self.lowRatingFigure - margin)
                            if self.lowRatingFigure != 10.000000:
                                query += " AND %s.c05 <> 10.000000" % option # somehow 10.000000 is considered to be between 0.000001 and 7.999999
                    
                    elif option == 'episode':
                        query = "SELECT files.strFilename as filename, path.strPath || files.strFilename as full_path, tvshow.c00 as showname, episode.c12 as season, files.idFile "
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
                            query += " AND %s.c03 BETWEEN %f AND %f" % (option, (margin if self.ignoreNoRating else 0), self.lowRatingFigure - margin)
                            if self.lowRatingFigure != 10.000000:
                                query += " AND %s.c03 <> 10.000000" % option # somehow 10.000000 is considered to be between 0.000001 and 7.999999
                    
                    self.debug('Executing query on %s: %s' % (database, query))
                    
                    cur.execute(query)
                    
                    # Append the results to the list of files to delete.
                    results += cur.fetchall()
                    
            return results
        except:
            # The video database(s) could not be opened, or the query was invalid
            self.notify(__settings__.getLocalizedString(30012))
            # raise
    
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
                    con = sqlite3.connect(xbmc.translatePath('special://database/' + database))
                    cur = con.cursor()
                    
                    # Insert path if it doesn't exist
                    query = 'INSERT OR IGNORE INTO\
                            path(strPath)\
                            values("%s/")' % (newPath)
                    self.debug('Executing query on %s: %s' % (database, query))
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
                    
                    self.debug('Executing query on %s: %s' % (database, query))
                    cur.execute(query)
                    con.commit()
        # TODO: Don't catch all exceptions
        except:
            # Error opening video library database
            self.notify(__settings__.getLocalizedString(30012))
            raise
    
    def reload_settings(self):
        """
        Retrieve new values for all settings, in order to account for any recent changes.
        """
        __settings__ = xbmcaddon.Addon(__addonID__)
        
        self.serviceEnabled = bool(__settings__.getSetting('service_enabled') == "true")
        self.delayedStart = float(__settings__.getSetting('delayed_start'))
        self.scanInterval = float(__settings__.getSetting('scan_interval'))
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
        self.holdingExpire = float(__settings__.getSetting('holding_expire'))
        self.enableDebug = bool(xbmc.translatePath(__settings__.getSetting('enable_debug')) == "true")
        self.createSeriesSeasonDirs = bool(xbmc.translatePath(__settings__.getSetting('create_series_season_dirs')) == "true")
        self.doupdatePathReference = bool(xbmc.translatePath(__settings__.getSetting('update_path_reference')) == "true")
        self.removeFromAutoExec = bool(xbmc.translatePath(__settings__.getSetting('remove_from_autoexec')) != "false") # true
    
    def disk_space_low(self):
        """
        Check if the disk is running low on free space.
        Returns true if the free space is less than the threshold specified in the addon's settings.
        TODO: Checks to make sure you set the disk usage path before enabling, if you store your videos on a secondary drive (e.g, /media/external or D:\ etc).
        TODO: statvfs is deprecated since python 2.6
        """
        diskStats = os.statvfs(self.lowDiskPath)
        diskCapacity = diskStats.f_frsize * diskStats.f_blocks
        diskFree = diskStats.f_frsize * diskStats.f_bavail
        try:
            diskFreePercent = math.ceil(float(100) / float(diskCapacity) * float(diskFree))
        except ZeroDivisionError, e:
            self.notify('No free space left, or hard disk capacity is 0. Did you select the correct hard disk to check for free space?', 15000)
            return False
        
        return (float(diskFreePercent) < float(self.lowDiskPercentage))
    
    def delete_file(self, file):
        """
        Delete a file from the file system.
        """
        if os.path.exists(file):
            try:
                os.remove(file)
                self.notify(__settings__.getLocalizedString(30014) % (os.path.basename(file), os.path.dirname(file)), 10000)
            except OSError, e:
                self.debug('Deleting file %s failed with error code %d' % (file, e.errno))
        else:
            self.debug('The file "%s" was already deleted' % file)
    
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
        except OSError, e:
            self.debug("Moving file %s failed with error code %d" % (file, e.errno));
            return False;
    
    def create_season_dirs(self, seasondir):
        """
        Create season as well as series directories in the folder specified.
        
        Keyword arguments:
        seasondir -- the directory in which to create the folder(s)
        """
        seriesdir = os.path.dirname(seasondir)
        create_directory(seriesdir)
        create_directory(seasondir)
    
    def create_directory(self, location):
        '''
        Creates a directory at the location provided.
        '''
        try:
            self.debug('Creating directory at %s' % location)
            os.mkdir(location)
            self.debug('Successfully created directory')
        except OSError, e:
            self.debug('Creating directory at %s failed with error code %d' % (location, e.errno))
    
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
            xbmc.log(__title__ + '::' + message)
    
    def disable_autoexec(self):
        '''
        Removes the autoexec line in special://home/userdata/autoexec.py
        Since version 2.0 this addon is run as a service. This line was needed in prior versions of the addon to allow for automatically starting the addon. 
        If this line is not removed after updating to version 2.0, the script would be started twice. 
        In short, this function allows for backward compatibility for updaters.
        '''
        try:
            # See if the autoexec.py file exists
            if (os.path.exists(AUTOEXEC_PATH)):
                found = False
                autoexecfile = file(AUTOEXEC_PATH, 'r')
                filecontents = autoexecfile.readlines()
                autoexecfile.close()
                
                # Check if we're in it
                for line in filecontents:
                    if line.find(__addonID__) > 0:
                       found = True
                       __settings__.setSetting(id='remove_from_autoexec', value='true')
                
                # Found that we're in it and it's time to remove ourselves
                if (found):
                    autoexecfile = file(AUTOEXEC_PATH, 'w')
                    for line in filecontents:
                        if not line.find(__addonID__) > 0:
                            autoexecfile.write(line)
                    autoexecfile.close()
                    __settings__.setSetting(id='remove_from_autoexec', value='false')
                    self.debug("The autostart script was successfully removed from %s" % AUTOEXEC_PATH)
                else:
                    self.debug("No need to remove the autostart script, as it was already removed from %s" % AUTOEXEC_PATH)
        except OSError, e:
            self.debug('Removing the autostart script in %s failed with error code %d' % (AUTOEXEC_PATH, e.errno))

run = Main()
