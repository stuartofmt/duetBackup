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
```

The meaning of the settings is:

```
-topDir <the top level dir that is the source for backups>
-userName <your Github user name>
-userToken <your github token>
-rep <your repository name>
-branch <the main branch in your repository - usually main>
-dir <subdir>
-days <days between backups>
-hours <hours added to days>
```

**Notes on duetBackup.config**
The default top level directory is /opt/dsf for most purposes this will be sufficient and does not need to be included in the config file.  It can be over-ridden with the `-topDir` option.

You need to have at least one `-dir` setting. For each directory (under /opt/dsf) that you want to backup use a `-dir` setting.  Subdirectories below each `-dir` will also be backed up.

`-days` and `-hours` are integers.  duetBackup will repeat backups every n hours where n = days*24+hours. If you specify `-days 0` and `-hour 0`, a single backup will be performed and duetBackup will terminate.

For example - the following example will perform a backup, of the `main` branch in the `ender5Backup` repository, every 30 hrs, of the system dir and the macros dir :

```
-userName memyselfI
-userToken gbx_EDEFmLyZDDqgUIQxyz123BqW6x9jabcGCMXl
-rep ender5Backup
-dir sd/sys
-dir sd/macros
-days 1
-hours 6
```