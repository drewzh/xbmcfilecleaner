#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import locale
import time
import re
import json
from ctypes import *

import xbmc
import xbmcvfs
from settings import *
from utils import translate, notify, debug, write_to_log


# Addon info
__addonID__ = "script.filecleaner"
__addon__ = Addon(__addonID__)
__title__ = __addon__.getAddonInfo("name")
__author__ = "Anthirian, drewzh"
__icon__ = "special://home/addons/" + __addonID__ + "/icon.png"


class Cleaner:
    """
    The Cleaner class is used in XBMC to identify and delete videos that have been watched by the user. It starts with
    XBMC and runs until XBMC shuts down. Identification of watched videos can be enhanced with additional criteria,
    such as recently watched, low rated and based on free disk space. Deleting of videos can be enabled for movies,
    music videos or tv shows, or any combination of these. Almost all of the methods in this class will be called
    through the cleanup method.
    """

    # Constants to ensure correct JSON-RPC requests for XBMC
    MOVIES = "movies"
    MUSIC_VIDEOS = "musicvideos"
    TVSHOWS = "episodes"

    movie_filter_fields = ["title", "plot", "plotoutline", "tagline", "votes", "rating", "time", "writers",
                           "playcount", "lastplayed", "inprogress", "genre", "country", "year", "director",
                           "actor", "mpaarating", "top250", "studio", "hastrailer", "filename", "path", "set",
                           "tag", "dateadded", "videoresolution", "audiochannels", "videocodec", "audiocodec",
                           "audiolanguage", "subtitlelanguage", "videoaspect", "playlist"]
    episode_filter_fields = ["title", "tvshow", "plot", "votes", "rating", "time", "writers", "airdate",
                             "playcount", "lastplayed", "inprogress", "genre", "year", "director", "actor",
                             "episode", "season", "filename", "path", "studio", "mpaarating", "dateadded",
                             "videoresolution", "audiochannels", "videocodec", "audiocodec", "audiolanguage",
                             "subtitlelanguage", "videoaspect", "playlist"]
    musicvideo_filter_fields = ["title", "genre", "album", "year", "artist", "filename", "path", "playcount",
                                "lastplayed", "time", "director", "studio", "plot", "dateadded", "videoresolution",
                                "audiochannels", "videocodec", "audiocodec", "audiolanguage", "subtitlelanguage",
                                "videoaspect", "playlist"]

    supported_filter_fields = {
        TVSHOWS: episode_filter_fields,
        MOVIES: movie_filter_fields,
        MUSIC_VIDEOS: musicvideo_filter_fields
    }
    methods = {
        TVSHOWS: "VideoLibrary.GetEpisodes",
        MOVIES: "VideoLibrary.GetMovies",
        MUSIC_VIDEOS: "VideoLibrary.GetMusicVideos"
    }
    properties = {
        TVSHOWS: ["file", "showtitle", "season"],
        MOVIES: ["file", "title", "year"],
        MUSIC_VIDEOS: ["file", "artist"]
    }

    def __init__(self):
        """Create a Cleaner object that performs regular cleaning of watched videos."""

        try:
            locale.setlocale(locale.LC_ALL, "English_United Kingdom")
        except locale.Error as le:
            debug("Could not change locale: %r" % le, xbmc.LOGWARNING)

        service_sleep = 10
        ticker = 0
        delayed_completed = False

        while not xbmc.abortRequested:
            scan_interval_ticker = get_setting(scan_interval) * 60 / service_sleep
            delayed_start_ticker = get_setting(delayed_start) * 60 / service_sleep

            if not get_setting(cleaner_enabled):
                continue
            else:
                if delayed_completed and ticker >= scan_interval_ticker:
                    self.cleanup()
                    ticker = 0
                elif not delayed_completed and ticker >= delayed_start_ticker:
                    delayed_completed = True
                    self.cleanup()
                    ticker = 0

                time.sleep(service_sleep)
                ticker += 1

        debug("Abort requested. Terminating.")

    def cleanup(self):
        """
        Delete any watched videos from the XBMC video database.

        The videos to be deleted are subject to a number of criteria as can be specified in the addon's settings.
        """
        debug("Starting cleaning routine")
        if get_setting(delete_when_idle) and xbmc.Player().isPlayingVideo():
            debug("A video is currently playing. No cleaning will be performed this interval.", xbmc.LOGWARNING)
            return

        if not get_setting(delete_when_low_disk_space) or (get_setting(delete_when_low_disk_space) and
                                                           self.disk_space_low()):
            # create stub to summarize cleaning results
            summary = "Deleted" if get_setting(delete_files) else "Moved"
            cleaned_files = []
            cleaning_required = False
            if get_setting(delete_movies):
                movies = self.get_expired_videos(self.MOVIES)
                if movies:
                    count = 0
                    for abs_path, title, year in movies:
                        if xbmcvfs.exists(abs_path):
                            cleaning_required = True
                            if not get_setting(delete_files):
                                if get_setting(create_subdirs):
                                    new_path = os.path.join(get_setting(holding_folder), "%s (%d)" % (title, year))
                                else:
                                    new_path = get_setting(holding_folder)
                                if self.move_file(abs_path, new_path):
                                    count += 1
                                    cleaned_files.append(abs_path)
                                    self.delete_empty_folders(os.path.dirname(abs_path))
                            else:
                                if self.delete_file(abs_path):
                                    count += 1
                                    cleaned_files.append(abs_path)
                                    self.delete_empty_folders(os.path.dirname(abs_path))
                        else:
                            debug("XBMC could not find the file at %r" % abs_path, xbmc.LOGWARNING)
                    if count > 0:
                        summary += " %d %s" % (count, self.MOVIES)

            if get_setting(delete_tv_shows):
                episodes = self.get_expired_videos(self.TVSHOWS)
                if episodes:
                    count = 0
                    for abs_path, show_name, season_number in episodes:
                        if xbmcvfs.exists(abs_path):
                            if not get_setting(delete_files):
                                if get_setting(create_subdirs):
                                    new_path = os.path.join(get_setting(holding_folder), show_name, "Season %d" % season_number)
                                else:
                                    new_path = get_setting(holding_folder)
                                if self.move_file(abs_path, new_path):
                                    cleaning_required = True
                                    count += 1
                                    cleaned_files.append(abs_path)
                                    self.delete_empty_folders(os.path.dirname(abs_path))
                            else:
                                if self.delete_file(abs_path):
                                    cleaning_required = True
                                    count += 1
                                    cleaned_files.append(abs_path)
                                    self.delete_empty_folders(os.path.dirname(abs_path))
                        else:
                            debug("XBMC could not find the file at %r" % abs_path, xbmc.LOGWARNING)
                    if count > 0:
                        summary += " %d %s" % (count, self.TVSHOWS)

            if get_setting(delete_music_videos):
                musicvideos = self.get_expired_videos(self.MUSIC_VIDEOS)
                if musicvideos:
                    count = 0
                    for abs_path, artists in musicvideos:
                        if xbmcvfs.exists(abs_path):
                            cleaning_required = True
                            if not get_setting(delete_files):
                                if get_setting(create_subdirs):
                                    artist = ", ".join(str(a) for a in artists)
                                    new_path = os.path.join(get_setting(holding_folder), artist)
                                else:
                                    new_path = get_setting(holding_folder)
                                if self.move_file(abs_path, new_path):
                                    count += 1
                                    cleaned_files.append(abs_path)
                                    self.delete_empty_folders(os.path.dirname(abs_path))
                            else:
                                if self.delete_file(abs_path):
                                    count += 1
                                    cleaned_files.append(abs_path)
                                    self.delete_empty_folders(os.path.dirname(abs_path))
                        else:
                            debug("XBMC could not find the file at %r" % abs_path, xbmc.LOGWARNING)
                    if count > 0:
                        summary += " %d %s" % (count, self.MUSIC_VIDEOS)

            write_to_log(cleaned_files)

            # Give a status report if any deletes occurred
            if not summary.endswith("ed"):
                notify(summary)

            # Finally clean the library to account for any deleted videos.
            if get_setting(clean_xbmc_library) and cleaning_required:
                # Wait 10 seconds for deletions to finish before cleaning.
                time.sleep(10)

                # Check if the library is being updated before cleaning up
                if xbmc.getCondVisibility("Library.IsScanningVideo"):
                    debug("The video library is being updated. Skipping library cleanup.", xbmc.LOGWARNING)
                else:
                    xbmc.executebuiltin("XBMC.CleanLibrary(video)")

    def get_expired_videos(self, option):
        """
        Find videos in the XBMC library that have been watched and satisfy any other conditions enabled in the settings.

        :type option: str
        :param option: The type of videos to find (one of the globals MOVIES, MUSIC_VIDEOS or TVSHOWS).
        :rtype: list
        :return: A list of expired videos that satisfy the conditions specified.
        """

        # A non-exhaustive list of pre-defined filters to use during JSON-RPC requests
        # These are possible conditions that must be met before a video can be deleted
        by_playcount = {"field": "playcount", "operator": "greaterthan", "value": "0"}
        by_date_played = {"field": "lastplayed", "operator": "notinthelast", "value": "%d" % get_setting(expire_after)}
        # TODO add GUI setting for date_added
        by_date_added = {"field": "dateadded", "operator": "notinthelast", "value": "7"}
        by_minimum_rating = {"field": "rating", "operator": "lessthan", "value": "%d" % get_setting(minimum_rating)}
        by_no_rating = {"field": "rating", "operator": "isnot", "value": "0"}
        by_artist = {"field": "artist", "operator": "contains", "value": "Muse"}
        by_progress = {"field": "inprogress", "operator": "false", "value": ""}

        # link settings and filters together
        settings_and_filters = [
            # TODO: Verify this works correctly with the new settings loading
            (get_setting(enable_expiration), by_date_played),
            (get_setting(delete_when_low_rated), by_minimum_rating),
            (get_setting(not_in_progress), by_progress)
        ]

        # Only check not rated videos if checking for video ratings at all
        if get_setting(delete_when_low_rated):
            settings_and_filters.append((get_setting(ignore_no_rating), by_no_rating))

        enabled_filters = [by_playcount]
        for s, f in settings_and_filters:
            if s and f["field"] in self.supported_filter_fields[option]:
                enabled_filters.append(f)

        debug("[%s] Filters enabled: %r" % (self.methods[option], enabled_filters))

        filters = {"and": enabled_filters}

        request = {
            "jsonrpc": "2.0",
            "method": self.methods[option],
            "params": {
                "properties": self.properties[option],
                "filter": filters
            },
            "id": 1
        }

        rpc_cmd = json.dumps(request)
        response = xbmc.executeJSONRPC(rpc_cmd)
        debug("[%s] Response: %r" % (self.methods[option], response))
        result = json.loads(response)

        try:
            error = result["error"]
            return self.handle_json_error(error)
        except KeyError as ke:
            if "error" in ke:
                pass  # no error
            else:
                raise

        debug("Building list of expired videos")
        expired_videos = []
        response = result["result"]
        try:
            debug("Found %d watched %s matching your conditions" % (response["limits"]["total"], option))
            debug("JSON Response: " + str(response))
            for video in response[option]:
                # Gather all properties and add it to this video's information
                temp = []
                for p in self.properties[option]:
                    temp.append(video[p])
                expired_videos.append(temp)
        except KeyError as ke:
            if option in ke:
                pass  # no expired videos found
            else:
                debug("KeyError: %r not found" % ke, xbmc.LOGWARNING)
                self.handle_json_error(response)
                raise
        finally:
            debug("Expired videos: " + str(expired_videos))
            return expired_videos

    def handle_json_error(self, error):
        """If a JSON-RPC request results in an error, this function will handle it.
        This function currently only logs the error that occurred, and will not act on it.

        :type error: dict
        :param error: the error to handle
        :rtype : None
        """
        error_format = {
            "code": {
                "type": "integer",
                "required": True
            },
            "message": {
                "type": "string",
                "required": True
            },
            "data": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "required": True
                    },
                    "stack": {
                        "type": "object",
                        "id": "Error.Stack",
                        "properties": {
                            "name": {
                                "type": "string",
                                "required": True
                            },
                            "type": {
                                "type": "string",
                                "required": True
                            },
                            "message": {
                                "type": "string",
                                "required": True
                            },
                            "property": {
                                "$ref": "Error.Stack"
                            }
                        }
                    }
                }
            }
        }

        code = error["code"]
        msg = error["message"]
        details = error["data"] if "data" in error else "No further details"

        # If we cannot do anything about this error, just log it and stop
        debug("JSON error occurred.\nCode: %d\nMessage: %r\nDetails: %r" % (code, msg, details), xbmc.LOGERROR)
        return None

    def is_excluded(self, full_path):
        """Check if the file path is part of the excluded sources.

        :type full_path: str
        :param full_path: the path to the file that should be checked for exclusion
        :rtype: bool
        :return: True if the path matches an excluded path, False otherwise.
        """
        if not get_setting(exclusion_enabled):
            debug("Path exclusion is disabled.")
            return False

        if not full_path:
            debug("File path is empty and cannot be checked for exclusions")
            return False

        exclusions = [get_setting(exclusion1), get_setting(exclusion2), get_setting(exclusion3)]

        if r"://" in full_path:
            debug("Detected a network path")
            pattern = re.compile("(?:smb|afp|nfs)://(?:(?:.+):(?:.+)@)?(?P<tail>.*)$", flags=re.U | re.I)

            debug("Converting excluded network paths for easier comparison")
            normalized_exclusions = []
            for ex in exclusions:
                # Strip everything but the folder structure
                try:
                    if ex and r"://" in ex:
                        # Only normalize non-empty excluded paths
                        normalized_exclusions.append(pattern.match(ex).group("tail").lower())
                except (AttributeError, IndexError, KeyError) as err:
                    debug("Could not parse the excluded network path %r\n%s" % (ex, err), xbmc.LOGWARNING)
                    return True

            debug("Conversion result: %r" % normalized_exclusions)

            debug("Proceeding to match a file with the exclusion paths")
            debug("The file to match is %r" % full_path)
            result = pattern.match(full_path)

            try:
                debug("Converting file path for easier comparison.")
                converted_path = result.group("tail").lower()
                debug("Result: %r" % converted_path)
                for ex in normalized_exclusions:
                    debug("Checking against exclusion %r." % ex)
                    if converted_path.startswith(ex):
                        debug("File %r matches excluded path %r." % (converted_path, ex))
                        return True

                debug("No match was found with an excluded path.")
                return False

            except (AttributeError, IndexError, KeyError) as err:
                debug("Error converting %r. No files will be deleted.\n%s" % (full_path, err), xbmc.LOGWARNING)
                return True
        else:
            debug("Detected a local path")
            for ex in exclusions:
                if ex and full_path.startswith(ex):
                    debug("File %r matches excluded path %r." % (full_path, ex))
                    return True

            debug("No match was found with an excluded path.")
            return False

    def get_free_disk_space(self, path):
        """Determine the percentage of free disk space.

        :type path: str
        :param path: the path to the drive to check (this can be any path of any depth on the desired drive). If the
        path doesn't exist, this function returns 100, in order to prevent files from being deleted accidentally
        :rtype : float
        """
        percentage = float(100)
        debug("Checking for disk space on path: %r" % path)
        dirs, files = xbmcvfs.listdir(path)
        if dirs or files:  # Workaround for xbmcvfs.exists("C:\")
            if xbmc.getCondVisibility("System.Platform.Windows"):
                debug("We are checking disk space from a Windows file system")
                debug("The path to check is %r" % path)

                if r"://" in path:
                    debug("We are dealing with network paths")
                    debug("Extracting information from share %r" % path)

                    regex = "(?P<type>smb|nfs|afp)://(?:(?P<user>.+):(?P<pass>.+)@)?(?P<host>.+?)/(?P<share>.+?).*$"
                    pattern = re.compile(regex, flags=re.I | re.U)
                    match = pattern.match(path)
                    try:
                        share = match.groupdict()
                        debug("Protocol: %r, User: %r, Password: %r, Host: %r, Share: %r" %
                              (share["type"], share["user"], share["pass"], share["host"], share["share"]))
                    except AttributeError as ae:
                        debug("%r\nCould not extract required data from %r" % (ae, path), xbmc.LOGERROR)
                        return percentage

                    debug("Creating UNC paths so Windows understands the shares")
                    path = os.path.normcase(r"\\" + share["host"] + os.sep + share["share"])
                    debug("UNC path: %r" % path)
                    debug("If checks fail because you need credentials, please mount the share first")
                else:
                    debug("We are dealing with local paths")

                if not isinstance(path, unicode):
                    debug("Converting path to unicode for disk space checks")
                    path = path.decode("mbcs")
                    debug("New path: %r" % path)

                bytes_total = c_ulonglong(0)
                bytes_free = c_ulonglong(0)
                windll.kernel32.GetDiskFreeSpaceExW(c_wchar_p(path), byref(bytes_free), byref(bytes_total), None)

                try:
                    percentage = float(bytes_free.value) / float(bytes_total.value) * 100
                    debug("Hard disk check results:")
                    debug("Bytes free: %s" % locale.format("%d", bytes_free.value, grouping=True))
                    debug("Bytes total: %s" % locale.format("%d", bytes_total.value, grouping=True))
                except ZeroDivisionError:
                    notify(translate(32511), 15000, level=xbmc.LOGERROR)
            else:
                debug("We are checking disk space from a non-Windows file system")
                debug("Stripping " + path + " of all redundant stuff.")
                path = os.path.normpath(path)
                debug("The path now is " + path)

                try:
                    diskstats = os.statvfs(path)
                    percentage = float(diskstats.f_bfree) / float(diskstats.f_blocks) * 100
                    debug("Hard disk check results:")
                    debug("Bytes free: %s" % locale.format("%d", diskstats.f_bfree, grouping=True))
                    debug("Bytes total: %s" % locale.format("%d", diskstats.f_blocks, grouping=True))
                except OSError as ose:
                    notify(translate(32512), 15000, level=xbmc.LOGERROR)
                    debug("Error accessing %r: %r" % (path, ose))
                except ZeroDivisionError:
                    notify(translate(32511), 15000, level=xbmc.LOGERROR)
        else:
            notify(translate(32513), 15000, level=xbmc.LOGERROR)

        debug("Free space: %0.2f%%" % percentage)
        return percentage

    def disk_space_low(self):
        """
        Check if the disk is running low on free space.

        :rtype: bool
        :return: True if the disk space is below the user-specified threshold, False otherwise.
        """
        return self.get_free_disk_space(get_setting(disk_space_check_path)) <= get_setting(disk_space_threshold)

    def delete_file(self, location):
        """
        Delete a file from the file system.

        Example:
         - success = delete_file(location)

        :type location: str
        :param location: the path to the file you wish to delete
        :rtype: bool
        :return: True if the file was deleted succesfully, False otherwise.
        """
        debug("Deleting file at %r" % location)
        if self.is_excluded(location):
            debug("This file is found on an excluded path and will not be deleted.")
            return False

        if xbmcvfs.exists(location):
            if get_setting(delete_related):
                path, name = os.path.split(location)
                name, _ = os.path.splitext(name)

                for extra_file in xbmcvfs.listdir(path)[1]:
                    if extra_file.startswith(name):
                        extra_file_path = os.path.join(path, extra_file)
                        if extra_file_path != location:
                            debug('Deleting %r' % extra_file_path)
                            xbmcvfs.delete(extra_file_path)

            return xbmcvfs.delete(location)
        else:
            debug("XBMC could not find the file at %r" % location, xbmc.LOGERROR)
            return False

    def delete_empty_folders(self, folder):
        """
        Delete the folder if it is empty.

        Presence of custom file extensions can be ignored while scanning.

        To achieve this, edit the ignored file types setting in the addon settings.

        Example:
         - success = delete_empty_folders(path)

        :type folder: str
        :param folder: The folder to be deleted.
        :rtype: bool
        :return: True if the folder was deleted succesfully, False otherwise.
        """
        if not get_setting(delete_folders):
            debug("Deleting of folders is disabled.")
            return False

        debug("Checking if %r is empty" % folder)
        ignored_file_types = [file_ext.strip() for file_ext in get_setting(ignore_extensions).split(",")]
        debug("Ignoring file types %r" % ignored_file_types)
        subfolders, files = xbmcvfs.listdir(folder)
        debug("Contents of %r:\nSubfolders: %r\nFiles: %r" % (folder, subfolders, files))

        empty = True
        try:
            for f in files:
                _, ext = os.path.splitext(f)
                debug("File extension: " + ext)
                if ext not in ignored_file_types:
                    debug("Found non-ignored file type %r" % ext)
                    empty = False
                    break
        except OSError as oe:
            debug("Error deriving file extension. Errno " + str(oe.errno), xbmc.LOGERROR)
            empty = False

        # Only delete directories if we found them to be empty (containing no files or filetypes we ignored)
        if empty:
            debug("Directory is empty and will be removed")
            try:
                # Recursively delete any subfolders
                for f in subfolders:
                    debug("Deleting file at " + str(os.path.join(folder, f)))
                    self.delete_empty_folders(os.path.join(folder, f))

                # Delete any files in the current folder
                for f in files:
                    debug("Deleting file at " + str(os.path.join(folder, f)))
                    xbmcvfs.delete(os.path.join(folder, f))

                # Finally delete the current folder
                return xbmcvfs.rmdir(folder)
            except OSError as oe:
                debug("An exception occurred while deleting folders. Errno " + str(oe.errno), xbmc.LOGERROR)
                return False
        else:
            debug("Directory is not empty and will not be removed")
            return False

    def move_file(self, source, dest_folder):
        """Move a file to a new destination. Returns True if the move succeeded, False otherwise.
        Will create destination if it does not exist.

        Example:
            success = move_file(a, b)

        :type source: basestring
        :param source: the source path (absolute)
        :type dest_folder: str
        :param dest_folder: the destination path (absolute)
        :rtype : bool
        """
        if self.is_excluded(source):
            debug("This file is found on an excluded path and will not be moved.")
            return False
        if isinstance(source, unicode):
            source = source.encode("utf-8")
        dest_folder = xbmc.makeLegalFilename(dest_folder)
        debug("Moving %r to %r" % (os.path.basename(source), dest_folder))
        if xbmcvfs.exists(source):
            if not xbmcvfs.exists(dest_folder):
                debug("Destination %r does not exist yet." % dest_folder)
                debug("Creating destination %r." % dest_folder)
                if xbmcvfs.mkdirs(dest_folder):
                    debug("Successfully created %r." % dest_folder)
                else:
                    debug("Destination %r could not be created." % dest_folder, xbmc.LOGERROR)
                    return False

            new_path = os.path.join(dest_folder, os.path.basename(source))

            if xbmcvfs.exists(new_path):
                debug("A file with the same name already exists in the holding folder. Checking file sizes.")
                existing_file = xbmcvfs.File(new_path)
                file_to_move = xbmcvfs.File(source)
                if file_to_move.size() > existing_file.size():
                    debug("This file is larger than the existing file. Replacing the existing file with this one.")
                    existing_file.close()
                    file_to_move.close()
                    return xbmcvfs.delete(new_path) and xbmcvfs.rename(source, new_path)
                else:
                    debug("This file is smaller than the existing file. Deleting this file instead of moving.")
                    existing_file.close()
                    file_to_move.close()
                    return self.delete_file(source)
            else:
                debug("Moving %r to %r." % (source, new_path))
                if get_setting(delete_related):
                    path, name = os.path.split(source)
                    name, ext = os.path.splitext(name)

                    for extra_file in xbmcvfs.listdir(path)[1]:
                        if extra_file.startswith(name):
                            extra_file_path = os.path.join(path, extra_file)
                            new_extra_path = os.path.join(dest_folder, os.path.basename(extra_file))

                            if new_extra_path != new_path:
                                debug("Renaming %r to %r." % (extra_file_path, new_extra_path))
                                xbmcvfs.rename(extra_file_path, new_extra_path)

                return xbmcvfs.rename(source, new_path)
        else:
            debug("XBMC could not find the file at %r" % source, xbmc.LOGWARNING)
            return False


run = Cleaner()
