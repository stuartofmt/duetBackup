# README

This plugin provides periodic or instant backups of duet3d SBC files.  Backups are made to a Github repository, thereby facilitating the ability to roll back to earlier file versions.

**Modes of operation**
There are two modes of operation, depending on whether the archive option is used.

***Files deleted from the source are deleted from the main branch (default)***
    The designated directories are compared to the files in the `main` branch. Files are either Added (new files), Updated (if changed), or Skipped (if not changed).  Files that have been deleted from the designated directories are removed from the `main` branch.  In this way, the `main` branch is a snapshot of the designated directories.
    
    If you need to recover to the latest version - a simple download of the top level `main` branch is all that is needed.

    Github history still provides access to previously deleted files.

***Files are not deleted from the main branch***
    The behavior is the same as above, except that files which are deleted from the source are NOT  deleted from the main branch.  This makes recovery a little more involved.

**Prerequisites:**
SBC

V3.5.0-rc.1

Tested with Debian Bullseye

Python3

**To use the plugin:**

1- Create a new repository (Private is recomended) on Github.  Include a Readme.md file.  Take note of the name of the repository (including case) as well as the branch, which will usually be main.

2- Create a personal access token token.  A **classic** token with "repo" authorization is sufficient.  Instructions for creating a token can be found here:
https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens

3- Create(using DWC) a file `System/duetBackup/duetBackup.config` details are in the file Config Notes.

4- Install the plugin using the zip file from the DSF / DWC version folder.

5- To create an initial backup, set `-days 0` and `-hours 0`. This will run duetBackup once.  After that, set `-days` and `-hrs` to your prefered backup interval.  Note that if there are no changes to any files, backup does nothing.

**Versions**

***V1.0***
- Initial release


***V1.1***
- Added messages, sent to DWC
- Displays time to next backup using local time (previously GMT)
- Added `-duetPassword` to support for printers that use a password
- Added `-verbose` to enable more detailed log messages.

***V1.2***
- Added `-noDelete` option
- Compares files to determine if an update is needed.
- Added date / time of last change to file (except initial save).

***V1.3***
- README.md file shows date and time of last backup