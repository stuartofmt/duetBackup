# Standalone

duetBackup can be run as a standalone application.

**This document is not comprehensive, make sure you read the README.md file on the main page**

## Requirements 

* Python3 V3.8 or higher
* Linux - or  Windows have been tested
* Python libraries

Some OS (e.g. Debian Bookworm) *require* python be run in virtual environments.
In any case - It is highly recommended to use a virtual environment - for each python application.  This document assumes a virtual environment and includes brief notes on creatating one.

It is suggested that this program be placed in its own folder (e.g. /home/pi/duetBackup).

**Copy the duetBackup.py file from the latest plugin version (it is located in the dsf sub folder).**

### Create a virtual environment

The following instructions create a virtual environment in the same folder as the program.

This creates a virtual environment in  `[path-to-program]/venv`.

`python -m venv --system-site-packages  [path-to-program]/venv`

example
```
python -m venv --system-site-packages  /home/pi/duetBackup/venv
```

### Installing required libraries

The following libraries are needed and should be installed using the following command

`[path-to-program]/venv/bin/python -m pip install --no-cache-dir --upgrade [library name]`

**Note that if an error occurs try the following form i.e. without `--no-cache-dir`**

`[path-to-program]/venv/bin/python -m pip install --no-cache-dir --upgrade [library name]`

Libraries

[1] opencv-python

[2] imutils

example
```
/home/pi/duetBackup/venv/bin/python -m pip install --no-cache-dir --upgrade [library name]
```

### Usage

duetBackup can be started manually using one of the following command line forms

[path-to-program]/venv/bin/python [path-to-duetBackup]duetBackup.py [options]

The recomended way is to use a configuration file

`[path-to-program]/venv/bin/python [path-to-duetBackup]duetBackup.py -file [path-to-config-file]/[config_file_name]`

example
```
/home/pi/duetBackup/venv/bin/python /home/pi/duetBackup/duetBackup.py -file /home/pi/duetBackup/duetBackup.config
```

Alternatively  [options] can listed individually in the command line.