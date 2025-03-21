## To setup / install the plugin

1- Create a new repository (Private is recomended) on Github.  Include a Readme.md file in the base of the repository.  Take note of the name of the repository (including case) as well as the branch, which will usually be 'main'.

2- Create a personal access token token.  A **classic** token with "repo" authorization is sufficient.  Instructions for creating a token can be found here:
https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens

3- Create (using DWC) a file `System/duetBackup/duetBackup.config` details of the contents are in the file `Document/Config Notes.md`

4- Install the plugin using the zip file from the folder approprate to your DSF version.  During installation, it is recomended to monitor the progress in a console (see notes in the file `Documents/Monitoring.md`)

5- To create an initial backup, set `-days 0` and `-hours 0`. This will run duetBackup once.  After that, set `-days` and `-hrs` to your prefered backup interval.  Note that if there are no changes to any files, backup does nothing.