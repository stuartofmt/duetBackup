The configuration file supports the following settings:

```
-topDir [optional - defaults to /opt/dsf]
-userName [mandatory]
-userToken [Mandatory]
-rep [mandatory]
-branch [optional - defaults to main]
-dir [mandatory - at least one entry required]
-days [optional - default is 0]
-hours [optional - default is 0]
-duetPassword [optional - default is none]
-verbose [optional - default is False]
-noDelete [optional - default is False]
-ignore [optional - zero or more entries]
```

The meaning of the settings is:

```
-topDir <the top level dir that is the source for backups>
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
```

**Notes on duetBackup.config**
The default top level directory is /opt/dsf for most purposes this will be sufficient and does not need to be included in the config file.  It can be over-ridden with the `-topDir` option.

You need to have at least one `-dir` setting. For each directory (under /opt/dsf) that you want to backup use a `-dir` setting.  Subdirectories below each `-dir` will also be backed up.

`-days` and `-hours` are integers.  duetBackup will repeat backups every n hours where n = days*24+hours. If you specify `-days 0` and `-hour 0`, a single backup will be performed and duetBackup will terminate.

`-ignore` accepts the following patterns:

* matches everything

? matches any single character

[seq] matches any character in seq

[!seq] matches any character not in seq

Example 1 - the following example will perform a backup, of the `main` branch in the `ender5Backup` repository, for the system dir and the macros dir.  This will occur every 30 hrs.  Any files deleted will be removed from `branch`:

```
-userName memyselfI
-userToken gbx_EDEFmLyZDDqgUIQxyz123BqW6x9jabcGCMXl
-rep ender5Backup
-dir sd/sys
-dir sd/macros
-days 1
-hours 6
```

Example 2 - Same as example 1 but any files ending in `.log` will not be backed up. Any files in the subdirectories below `/sys` will not be backed up.  Also these files will be deleted (because `-noDelete` is not set):

```
-userName memyselfI
-userToken gbx_EDEFmLyZDDqgUIQxyz123BqW6x9jabcGCMXl
-rep ender5Backup
-dir sd/sys
-dir sd/macros
-days 1
-hours 6
-ignore *.log
-ignore */sys/*/*
```