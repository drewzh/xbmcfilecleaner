#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import re
import json
from ctypes import *

import xbmc
import xbmcaddon
import xbmcvfs
from settings import *
from utils import *


# Addon info
__addonID__ = "script.filecleaner"
__addon__ = Addon(__addonID__)
__title__ = xbmc.translatePath(__addon__.getAddonInfo("name")).decode("utf-8")
__author__ = "Anthirian, drewzh"
__icon__ = xbmc.translatePath(__addon__.getAddonInfo("icon")).decode("utf-8")


class Cleaner(object):
    """
    The Cleaner class is used in XBMC to identify and delete videos that have been watched by the user. It starts with
    XBMC and runs until XBMC shuts down. Identification of watched videos can be enhanced with additional criteria,
    such as recently watched, low rated and based on free disk space. Deleting of videos can be enabled for movies,
    music videos or tv shows, or any combination of these. Almost all of the methods in this class will be called
    through the cleanup method.
    """

    # Constants to ensure correct (Frodo-compatible) JSON-RPC requests for XBMC
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
    stacking_indicators = ["part", "pt", "cd", "dvd", "disk", "disc"]

    def __init__(self):
        """Create a Cleaner object that performs regular cleaning of watched videos."""
        debug("%s version %s loaded." % (__addon__.getAddonInfo("name").decode("utf-8"),
                                         __addon__.getAddonInfo("version").decode("utf-8")))

    def cleanup(self):
        """
        Delete any watched videos from the XBMC video database.

        The videos to be deleted are subject to a number of criteria as can be specified in the addon's settings.
        """
        debug("Starting cleaning routine.")
        if get_setting(clean_when_idle) and xbmc.Player().isPlayingVideo():
            debug("A video is currently playing. Skipping cleaning.", xbmc.LOGWARNING)
            return

        if not get_setting(clean_when_low_disk_space) or (get_setting(clean_when_low_disk_space)
                                                           and self.disk_space_low()):
            # create stub to summarize cleaning results
            summary = "Deleted" if get_setting(delete_files) else "Moved"
            cleaned_files = []
            if get_setting(clean_movies):
                movies = self.get_expired_videos(self.MOVIES)
                if movies:
                    count = 0
                    for abs_path, title, year in movies:
                        unstacked_path = self.unstack(abs_path)
                        if xbmcvfs.exists(unstacked_path[0]):
                            if not get_setting(delete_files):
                                if get_setting(create_subdirs):
                                    new_path = os.path.join(get_setting(holding_folder), "%s (%d)" % (title, year))
                                else:
                                    new_path = get_setting(holding_folder)
                                if self.move_file(abs_path, new_path):
                                    count += 1
                                    if len(unstacked_path) > 1:
                                        cleaned_files.extend(unstacked_path)
                                    else:
                                        cleaned_files.append(abs_path)
                                    self.clean_related_files(abs_path, new_path)
                                    self.delete_empty_folders(abs_path)
                            else:
                                if self.delete_file(abs_path):
                                    count += 1
                                    if len(unstacked_path) > 1:
                                        cleaned_files.extend(unstacked_path)
                                    else:
                                        cleaned_files.append(abs_path)
                                    self.clean_related_files(abs_path)
                                    self.delete_empty_folders(abs_path)
                        else:
                            debug("XBMC could not find %r" % abs_path, xbmc.LOGWARNING)
                    if count > 0:
                        summary += " %d %s" % (count, self.MOVIES)

            if get_setting(clean_tv_shows):
                episodes = self.get_expired_videos(self.TVSHOWS)
                if episodes:
                    count = 0
                    for abs_path, show_name, season_number in episodes:
                        if xbmcvfs.exists(abs_path):
                            if not get_setting(delete_files):
                                if get_setting(create_subdirs):
                                    new_path = os.path.join(get_setting(holding_folder), show_name,
                                                            "Season %d" % season_number)
                                else:
                                    new_path = get_setting(holding_folder)
                                if self.move_file(abs_path, new_path):
                                    count += 1
                                    cleaned_files.append(abs_path)
                                    self.clean_related_files(abs_path, new_path)
                                    self.delete_empty_folders(abs_path)
                            else:
                                if self.delete_file(abs_path):
                                    count += 1
                                    cleaned_files.append(abs_path)
                                    self.clean_related_files(abs_path)
                                    self.delete_empty_folders(abs_path)
                        else:
                            debug("XBMC could not find %r" % abs_path, xbmc.LOGWARNING)
                    if count > 0:
                        summary += " %d %s" % (count, self.TVSHOWS)

            if get_setting(clean_music_videos):
                musicvideos = self.get_expired_videos(self.MUSIC_VIDEOS)
                if musicvideos:
                    count = 0
                    for abs_path, artists in musicvideos:
                        if xbmcvfs.exists(abs_path):
                            if not get_setting(delete_files):
                                if get_setting(create_subdirs):
                                    artist = ", ".join(str(a) for a in artists)
                                    new_path = os.path.join(get_setting(holding_folder), artist)
                                else:
                                    new_path = get_setting(holding_folder)
                                if self.move_file(abs_path, new_path):
                                    count += 1
                                    cleaned_files.append(abs_path)
                                    self.clean_related_files(abs_path, new_path)
                                    self.delete_empty_folders(os.path.dirname(abs_path))
                            else:
                                if self.delete_file(abs_path):
                                    count += 1
                                    cleaned_files.append(abs_path)
                                    self.clean_related_files(abs_path)
                                    self.delete_empty_folders(os.path.dirname(abs_path))
                        else:
                            debug("XBMC could not find %r" % abs_path, xbmc.LOGWARNING)
                    if count > 0:
                        summary += " %d %s" % (count, self.MUSIC_VIDEOS)

            # Give a status report if any deletes occurred
            if cleaned_files:
                Log().prepend(cleaned_files)
                notify(summary)

            # Finally clean the library to account for any deleted videos.
            if get_setting(clean_xbmc_library) and cleaned_files:
                xbmc.sleep(5000)  # Sleep 5 seconds until file I/O is done.

                if xbmc.getCondVisibility("Library.IsScanningVideo"):
                    debug("The video library is being updated. Skipping library cleanup.", xbmc.LOGWARNING)
                else:
                    xbmc.executebuiltin("XBMC.CleanLibrary(video)")

            return summary

    def get_expired_videos(self, option):
        """
        Find videos in the XBMC library that have been watched.

        Respects any other conditions user enables in the addon's settings.

        :type option: str
        :param option: The type of videos to find (one of the globals MOVIES, MUSIC_VIDEOS or TVSHOWS).
        :rtype: list
        :return: A list of expired videos, along with a number of extra attributes specific to the video type.
        """

        # A non-exhaustive list of pre-defined filters to use during JSON-RPC requests
        # These are possible conditions that must be met before a video can be deleted
        by_playcount = {"field": "playcount", "operator": "greaterthan", "value": "0"}
        by_date_played = {"field": "lastplayed", "operator": "notinthelast", "value": "%d" % get_setting(expire_after)}
        # TODO: add GUI setting for date_added
        by_date_added = {"field": "dateadded", "operator": "notinthelast", "value": "7"}
        by_minimum_rating = {"field": "rating", "operator": "lessthan", "value": "%d" % get_setting(minimum_rating)}
        by_no_rating = {"field": "rating", "operator": "isnot", "value": "0"}
        # TODO: Don't hard code 'Muse' as artist
        by_artist = {"field": "artist", "operator": "contains", "value": "Muse"}
        by_progress = {"field": "inprogress", "operator": "false", "value": ""}

        # link settings and filters together
        settings_and_filters = [
            (get_setting(enable_expiration), by_date_played),
            (get_setting(clean_when_low_rated), by_minimum_rating),
            (get_setting(not_in_progress), by_progress)
        ]

        # Only check not rated videos if checking for video ratings at all
        if get_setting(clean_when_low_rated):
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
            debug("An error occurred. %r" % error)
            return None
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
                debug("%r" % response, xbmc.LOGWARNING)
                raise
        finally:
            debug("Expired videos: " + str(expired_videos))
            return expired_videos

    def is_excluded(self, full_path):
        """Check if the file path is part of the excluded sources.

        :type full_path: str
        :param full_path: the path to the file that should be checked for exclusion
        :rtype: bool
        :return: True if the path matches a user-set excluded path, False otherwise.
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
        :param path: The path to the drive to check. This can be any path of any depth on the desired drive.
        :rtype: float
        :return: The percentage of free space on the disk; 100% if errors occur.
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
                    debug("Bytes free: %s" % bytes_free.value)
                    debug("Bytes total: %s" % bytes_total.value)
                except ZeroDivisionError:
                    notify(translate(32511), 15000, level=xbmc.LOGERROR)
            else:
                debug("We are checking disk space from a non-Windows file system")
                debug("Stripping %r of all redundant stuff." % path)
                path = os.path.normpath(path)
                debug("The path now is " + path)

                try:
                    diskstats = os.statvfs(path)
                    percentage = float(diskstats.f_bfree) / float(diskstats.f_blocks) * 100
                    debug("Hard disk check results:")
                    debug("Bytes free: %r" % diskstats.f_bfree)
                    debug("Bytes total: %r" % diskstats.f_blocks)
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
        """Check whether the disk is running low on free space.

        :rtype: bool
        :return: True if disk space is below threshold (set through addon settings), False otherwise.
        """
        return self.get_free_disk_space(get_setting(disk_space_check_path)) <= get_setting(disk_space_threshold)

    def unstack(self, path):
        """Unstack path if it is a stacked movie. See http://wiki.xbmc.org/index.php?title=File_stacking for more info.

        :type path: str
        :param path: The path that should be unstacked.
        :rtype: list
        :return: A list of paths that are part of the stack. If it is no stacked movie, a one-element list is returned.
        """
        if path.startswith("stack://"):
            debug("Unstacking %r." % path)
            return path.replace("stack://", "").split(" , ")
        else:
            debug("Unstacking %r is not needed." % path)
            return [path]

    def get_stack_bare_title(self, filenames):
        """Find the common title of files part of a stack, minus the volume and file extension.

        Example:
            ["Movie_Title_part1.ext", "Movie_Title_part2.ext"] yields "Movie_Title"

        :type filenames: list
        :param filenames: a list of file names that are part of a stack. Use unstack() to find these file names.
        :rtype: str
        :return: common title of file names part of a stack
        """
        title = os.path.basename(os.path.commonprefix(filenames))
        for e in self.stacking_indicators:
            if title.endswith(e):
                title = title[:-len(e)].rstrip("._-")
                break
        return title

    def delete_file(self, location):
        """
        Delete a file from the file system. Also supports stacked movie files.

        Example:
            success = delete_file(location)

        :type location: str
        :param location: the path to the file you wish to delete.
        :rtype: bool
        :return: True if (at least one) file was deleted successfully, False otherwise.
        """
        debug("Attempting to delete %r" % location)

        paths = self.unstack(location)
        success = []

        if self.is_excluded(paths[0]):
            debug("Detected a file on an excluded path. Aborting.")
            return False

        for p in paths:
            if xbmcvfs.exists(p):
                success.append(bool(xbmcvfs.delete(p)))
            else:
                debug("File %r no longer exists." % p, xbmc.LOGERROR)
                success.append(False)

        debug("Return statuses: %r" % success)
        return any(success)

    def delete_empty_folders(self, location):
        """
        Delete the folder if it is empty. Presence of custom file extensions can be ignored while scanning.

        To achieve this, edit the ignored file types setting in the addon settings.

        Example:
            success = delete_empty_folders(path)

        :type location: str
        :param location: The path to the folder to be deleted.
        :rtype: bool
        :return: True if the folder was deleted successfully, False otherwise.
        """
        if not get_setting(delete_folders):
            debug("Deleting of folders is disabled.")
            return False

        folder = os.path.dirname(self.unstack(location)[0])  # Stacked paths should have the same parent, use any
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

    def clean_related_files(self, source, dest_folder=None):
        """Clean files related to another file based on the user's preferences.

        Related files are files that only differ by extension, or that share a prefix in case of stacked movies.

        Examples of related files include NFO files, thumbnails, subtitles, fanart, etc.

        :type source: str
        :param source: Location of the file whose related files should be cleaned.
        :type dest_folder: str
        :param dest_folder: (Optional) The folder where related files should be moved to. Not needed when deleting.
        """
        if settings.get_setting(clean_related):
            debug("Cleaning related files.")

            path_list = self.unstack(source)
            path, name = os.path.split(path_list[0])  # Because stacked movies are in the same folder, only check one
            if source.startswith("stack://"):
                name = self.get_stack_bare_title(path_list)
            else:
                name, ext = os.path.splitext(name)

            debug("Attempting to match related files in %r with prefix %r" % (path, name))
            for extra_file in xbmcvfs.listdir(path)[1]:
                if extra_file.startswith(name):
                    debug("%r starts with %r." % (extra_file, name))
                    extra_file_path = os.path.join(path, extra_file)
                    if settings.get_setting(delete_files):
                        if extra_file_path not in path_list:
                            debug("Deleting %r." % extra_file_path)
                            xbmcvfs.delete(extra_file_path)
                    else:
                        new_extra_path = os.path.join(dest_folder, os.path.basename(extra_file))
                        if new_extra_path not in path_list:
                            debug("Moving %r to %r." % (extra_file_path, new_extra_path))
                            xbmcvfs.rename(extra_file_path, new_extra_path)
            debug("Finished searching for related files.")
        else:
            debug("Cleaning of related files is disabled.")

    def move_file(self, source, dest_folder):
        """Move a file to a new destination. Will create destination if it does not exist.

        Example:
            success = move_file(a, b)

        :type source: str # TODO: Check p.
        :param source: the source path (absolute)
        :type dest_folder: str
        :param dest_folder: the destination path (absolute)
        :rtype: bool
        :return: True if (at least one) file was moved successfully, False otherwise.
        """
        if isinstance(source, unicode):
            source = source.encode("utf-8")

        paths = self.unstack(source)
        success = []
        dest_folder = xbmc.makeLegalFilename(dest_folder)

        if self.is_excluded(paths[0]):
            debug("Detected a file on an excluded path. Aborting.")
            return False

        for p in paths:
            debug("Attempting to move %r to %r." % (p, dest_folder))
            if xbmcvfs.exists(p):
                if not xbmcvfs.exists(dest_folder):
                    if xbmcvfs.mkdirs(dest_folder):
                        debug("Created destination %r." % dest_folder)
                    else:
                        debug("Destination %r could not be created." % dest_folder, xbmc.LOGERROR)
                        return False

                new_path = os.path.join(dest_folder, os.path.basename(p))

                if xbmcvfs.exists(new_path):
                    debug("A file with the same name already exists in the holding folder. Checking file sizes.")
                    existing_file = xbmcvfs.File(new_path)
                    file_to_move = xbmcvfs.File(p)
                    if file_to_move.size() > existing_file.size():
                        debug("This file is larger than the existing file. Replacing it with this one.")
                        existing_file.close()
                        file_to_move.close()
                        success.append(bool(xbmcvfs.delete(new_path) and xbmcvfs.rename(p, new_path)))
                    else:
                        debug("This file isn't larger than the existing file. Deleting it instead of moving.")
                        existing_file.close()
                        file_to_move.close()
                        success.append(bool(xbmcvfs.delete(p)))
                else:
                    debug("Moving %r to %r." % (p, new_path))
                    success.append(bool(xbmcvfs.rename(p, new_path)))
            else:
                debug("File %r no longer exists." % p, xbmc.LOGWARNING)
                success.append(False)

        return any(success)

if __name__ == "__main__":
    cleaner = Cleaner()
    cleaner.cleanup()
    # TODO: Ask user to view log
