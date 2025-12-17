# Startup at boot (Standalone)

## Create a systemd unit file 
The easiest way to run duetBackup, standalone on linux system boot, is to use a *unit* file and systemctl.

This document briefly describes how to do this. It is accurate for Debian Bullseye.  There may be differences for other distributions - so this document is only guidance.

Download the example unit file **duetBackup.service**<br>

Edit the example unit file paying particular attention to the following:
```
WorkingDirectory=/home/pi/duetBackup
```
This should usually be the directory in which you have duetBackup.py installed.

```
User=pi
```
Needs to be the usual login user

The ExecStart line needs to have a fully qualified filename for the binary. arguments can either be fully qualified or relative to WorkingDirectory.

You should have tested the ExecStart command from the command line and be confident that it works as you want.

**Example 1 using a config file (recomended)**
```
ExecStart=/home/pi/duetBackup/venv/bin/python ./duetBackup.py -file ./duetBackup.config
```

## Determine the systemd directory

Determine where your systemctl files are. Usually this will be somewhere like /`lib/systemd/system`. This directory will be used in the following commands.

If your distribution does not use this directory, and you are unsure what it is - you can narrow down the options with:

```
sudo find / -name system | grep systemd
```

## Installing the unit file

- [1]  copy the unit file (.service file) to the systemd directory

example (change this depending on the name of your unit file)
```
sudo cp ./[your unit file name ] /lib/systemd/system/[your unit file name ]
```

- [2] change the ownership to root
example
```
sudo chown root:root /lib/systemd/system/[your unit file name]
```

- [3]  relaod systemd daemon so that it recognizes the new file

```
sudo systemctl daemon-reload
```

## Testing the unit file

- [1]  start the service

```
sudo systemctl start [your unit file name]
```

- [2]  check for errors

```
sudo systemctl status [your unit file name]
```

If there is an error - you can edit the unit file (use sudo) in the /lib/systemd/system directory then reload using step 3 above.

## Start the program at each boot

Enable the unit file
```
sudo systemctl enable [your unit file name]
```

reboot and test to see if its running