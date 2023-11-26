## README

This plugin provides periodic or instant backups of duet3d SBC files.  Backups are made to a Github repository, thereby ensuring the ability to roll back to earlier file versions.

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

4- Install the plugin usinhg the zip file from the DSF / DWC version folder.

**Versions**

V1.0 - Initial release