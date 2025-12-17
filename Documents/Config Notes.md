# Configuration

The configuration file supports the following settings:

-userName <your Github user name>
-userToken <your github token>
-rep <your repository name>
-main <the main branch in your repository - usually main>
-dir <subdir>
-days <days between backups>
-hours <hours added to days>
-duetPassword<the password for the printer, if used>
-verbose<produces more detailed logging>
-noDelete <do not delete files>
-ignore  <do not backup files that match the pattern>
~~-topDir <the top level dir that is the source for backups>~~
-logfile <the fully qualified path and name of the logfile>
-duetIP <the ip address of the printer>

Soem settings are mandatory, some allow multiple instances:

-userName [Mandatory]
-userToken [Mandatory]
-rep [Mandatory]
-branch [optional - defaults to main]
-dir [Mandatory one or more entries]
-days [optional - default is 0]
-hours [optional - default is 0]
-duetPassword [optional - default is mone]
-verbose [optional - default is False]
-noDelete [optional - zero or more entries]
-ignore [optional - zero or more entries]
~~-topDir [optional - defaults to /opt/dsf]~~
-logfile[optional - defaults to /opt/dsf/sd/sys/duetBackup/duetBackup.log]
-duetIP [optional - defaults to 127.0.0.1 (i.e. the local machine)]

## Mandatory Items

If any of the Mandatory options are not set, the program will not run.

Each `-dir` entry specifies a directory (under /opt/dsf) that you want to backup. Subdirectories below each `-dir` will also be backed up.

## Backup Interval

`-days` and `-hours` are integers.  duetBackup will repeat backups every n hours where n = days*24+hours. If you specify `-days 0` and `-hour 0`, a single backup will be performed and duetBackup will terminate.

## Files to ignore

each `-ignore` specifies a file, filetype or file pattern that will be excluded from the backup

use a separate `-ignore` for each patterm

if `-ignore` is omitted the program will attempt to backup all file.
if `-ignore` does not have an argument its the same as omitting -ignore.

`-ignore` accepts the following patterns:

* matches everything

? matches any single character

[seq] matches any character in seq

[!seq] matches any character not in seq

## Syncronization

if `-noDelete` is omitted, the program essentially syncs the github repository to the printer.

if `-noDelete` does not have an argument all files in the repository are retained

if `-noDelete` has an argument, files in that folder are retained in the repository.

Specify a separate `-noDelete` for each folder

## Settings usually left at default

- logfile and -duetIP are usually omitted (defaults) unless using duetBackup in standalone mode (i.e. not as a plugin)


## Examples

Example 1 - the following example will perform a backup, of the `main` branch in the `ender5Backup` repository, for the system dir and the macros dir.  This will occur every 30 hrs.  Any files deleted will be removed from github (but of course you can look back through the github version history):


-userName memyselfI
-userToken gbx_EDEFmLyZDDqgABCxyz123BqW6x9jabcGCMXl
-rep ender5Backup
-dir sd/sys
-dir sd/macros
-days 1
-hours 6

Example 2 - Same as example 1 but any files ending in `.log` and ending in  `.conf?` (e.g. test.conf1, test2.conf2) will not be backed up. Also these files will be deleted from the repository (if there from a prior backup) -  because `-noDelete` is not set:


-userName memyselfI
-userToken gcm_EDEFmLyZDDqgABCxyz123BqW6x9jabcGCMXl
-rep ender5Backup
-dir sd/sys
-dir sd/macros
-days 1
-hours 6
-ignore *.log
-ignore *.conf?

Example 3 - Will perform an immediate backup of `sd/sys` , `sd/macros` and `sd/gcodes` (Jobs).  The files in `sd/gcodes` will not be deleted:

-userName memyselfI
-userToken gbx_EDEFmLyZDDqgABCxyz123BqW6x9jabcGCMXl
-rep ender5Backup
-dir sd/sys
-dir sd/macros
-dir sd/gcodes
-days 0
-hours 0
-noDelete sd/gcodes

**Notes on duetBackup.config**
~~The default top level directory is /opt/dsf for most purposes this will be correct and does not need to be included in the config file.  It can be over-ridden with the `-topDir` option.~~

The default logfile (duetBackup.log) will be placed in /opt/dsf/sd/sys/duetBackup i.e it is accessible from the DWC UI through system --> duetBackup --> duetBackup.log.  It can be over-ridden by specifying a fully qualified path and logfile name with the `-logfile` option.

A new log file will be created on each backup interval (this is to keep the logfile small).