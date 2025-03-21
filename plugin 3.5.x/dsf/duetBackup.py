#!/usr/bin/python3 -u

'''
The she-bang is not required if called with fully qualified paths
The plugin manager does this.  Otherwise use ...
Standard python install e.g.
#!/usr/bin/python3 -u
Venv python install e.g.
#! <path-to-virtual-environment/bin>python -u
'''

import argparse
import shlex
import sys
from github import Github
import os
import re
from datetime import datetime, timedelta
import time
import requests
import json
import signal
import hashlib
from fnmatch import fnmatch
import logging
from pathlib import Path

global progName, progVersion
progName = 'duetBackup'
progVersion = "1.4"
# Min python version
pythonMajor = 3
pythonMinor = 8


'''
# Version 1.1
- Added message for DWC monitoring
- Added display of local date for next backup

# Version 1.2
- Added -nodelete option
- Added file comparison check
- Version 1.3
- Added README.md with last backup information
- Prevented README from being deleted
- Added -ignore

# Version 1.4
- Added logging and some defensive code
- Strings  changed to f-strings
- updated deprecated calls to datetime - requires version 3.1.2 or later
- added file change info to README.md
- Restructured code for easier maintenance
- M291 error messages change to no timeout
''' 

def setuplogging():  #Called at start
    global logger
    logger = logging.getLogger(__name__)
    logger.propagate = False
    # set logging level
    try:
        if verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
    except NameError:
        pass
    # Create handler for console output - file output handler is created
    c_handler = logging.StreamHandler(sys.stdout)
    c_format = logging.Formatter(f'''{progName} "%(asctime)s [%(levelname)s] %(message)s"''')
    c_handler.setFormatter(c_format)
    logger.addHandler(c_handler)

def setupLogfile(): 
    global logger
    filehandler = None
    for handler in logger.handlers:
        if handler.__class__.__name__ == "FileHandler":
            filehandler = handler
            break # There is only ever one
    
    if filehandler != None:  #  Get rid of it
        filehandler.flush()
        filehandler.close()
        logger.removeHandler(filehandler)

    f_handler = logging.FileHandler(logfilename, mode='w', encoding='utf-8')
    f_format = logging.Formatter(f'''"%(asctime)s [%(levelname)s] %(message)s"''')
    f_handler.setFormatter(f_format)
    logger.addHandler(f_handler)

def sendDuetGcode(command):
    # Used to send a command to Duet
    if printerConnected:
        URL = 'http://127.0.0.1/machine/code'
        r = urlCall(URL,  command)

def urlCall(url, post):   
    # Makes all the calls to the printer
    # If post is True then make a http post call
    global printerConnected
    printerConnected = True
    timelimit = 5  # timout for call to return
    loop = 0
    limit = 2  # seems good enough to catch transients
    while loop < limit:
        error  = ''
        code = 9999
        logger.debug(f'''Connection attempt {loop} url: {url} post:{post}''')
        try:
            if post is False:
                r = requests.get(url, timeout=timelimit, headers=urlHeaders)
            else:
                r = requests.post(url, timeout=timelimit, data=post, headers=urlHeaders)
            if r.status_code == 200:
                return r
        except requests.ConnectionError as e:
            logger.warning('Cannot connect to the printer - likely a network error')
            logger.debug(str(e))
            error = 'Connection Error'
            printerConnected = False
        except requests.exceptions.Timeout as e:
            logger.warning('The printer connection timed out - was the printer turned on?')
            logger.debug(str(e))
            error = 'Timed Out'
            printerConnected = False          
        time.sleep(1)
        loop += 1 # Loop back and try again
 
    # Call failed but is not fatal - Create dummy response
    class r:
        ok = False
        status_code = code
        reason = error
    return r

def loginPrinter():
    global urlHeaders
    urlHeaders = {}

    URL = (f'''http://127.0.0.1/machine/disconnect''') # Close any open session
    r = urlCall(URL,  False)
    URL = (f'''http://127.0.0.1/machine/connect?password={duetPassword}''') # Connect with password
    r = urlCall(URL,  False)
    code = r.status_code
    if code == 200:
        j = json.loads(r.text)
        sessionKey = j['sessionKey']
        urlHeaders = {'X-Session-Key': sessionKey}
    #  Could not connect to printer   
    elif code == 403:
        logger.warning('!!!!! SBC Password is invalid !!!!!')
    elif code == 503:
        logger.warning('!!!!! No more SBC connections available !!!!!')
    elif code == 502:
        logger.warning('!!!!!  Incorrect DCS version  !!!!!')
    else:
        logger.warning(f'''!!!!!  Could not connect.  Error code = {code} !!!!!''')
    return code

## Get config data from file
class LoadFromFilex (argparse.Action):
    def __call__ (self, parser, namespace, values, option_string = None):
        with values as file:
            try:
                import copy

                old_actions = parser._actions
                file_actions = copy.deepcopy(old_actions)

                for act in file_actions:
                    act.required = False

                parser._actions = file_actions
                parser.parse_args(shlex.split(file.read()), namespace)
                parser._actions = old_actions

            except Exception as e:
                logger.error(f'''Error: {e}''')
                return
def init():
    # get config
    parser = argparse.ArgumentParser(
            description=f'''Duet3d Backup - V{progVersion}, allow_abbrev=False''')
    # Environment
    parser.add_argument('-topDir', type=str, nargs=1, default=["/opt/dsf"],
                        help='Top level dir')
    parser.add_argument('-userName', type=str, nargs=1, default=[""], help='Github User Name')
    parser.add_argument('-userToken', type=str, nargs=1, default=[""], help='Github Token')
    parser.add_argument('-repo', type=str, nargs=1, default=[""], help='Github Repo')
    parser.add_argument('-branch', type=str, nargs=1, default=["main"], help='Github current branch')
    parser.add_argument('-dir', type=str, nargs='+', action='append', help='list of dirs to backup')
    parser.add_argument('-ignore', type=str, nargs='+', action='append', help='list of patterns to ignore')
    parser.add_argument('-days', type=int, nargs=1, default=[0], help='Days between Backup Default is 7')
    parser.add_argument('-hours', type=int, nargs=1, default=[0], help='Hours (added to days) Default is 0')
    parser.add_argument('-duetPassword', type=str, nargs=1, default=[""], help='Duet3d Printer Password')
    parser.add_argument('-verbose', action='store_true', help='Detailed output')
    parser.add_argument('-noDelete', action='store_true', help='Delete files')
    parser.add_argument('-logfile', type=str, nargs=1, default=['/opt/dsf/sd/sys/duetBackup/duetBackup.log'], help='full logfile name')

    # Option to read from configuration file
    parser.add_argument('-file', type=argparse.FileType('r'), help='file of options', action=LoadFromFilex)

    args = vars(parser.parse_args())  # Save as a dict

    global topDir, userName, userToken, dirs, gitignore, userRepo, main, backupInt, duetPassword, verbose, noDelete
    global logfilename

    topDir = os.path.normpath(args['topDir'][0])
    userName = args['userName'][0]
    userToken = args['userToken'][0]
    userRepo = args['repo'][0]
    main = args['branch'][0]
    dirs =  args['dir']
    gitignore =  args['ignore']
    backupInt = int(args['days'][0])*24 + int(args['hours'][0])
    duetPassword = args['duetPassword'][0]
    verbose = args['verbose']
    noDelete = args['noDelete']
    logfilename = args['logfile'][0]

    if dirs is None:
        logger.critical('Nothing specified for -dir')
        force_quit

def loginGithub(user, token, repo):
    g = None
    repository = None
    try:
        logger.info(f'''Logging into Github as {user}''')
        g = Github(user, token)
        repository = g.get_user().get_repo(repo)
        last_commit_git = repository.get_commits()[0].last_modified
        logger.debug(f'''Git reported last commit on {last_commit_git}''')
        return repository, last_commit_git
    except Exception as e:
        msg = f'''Could not log into repository {repo}'''
        sendDuetGcode(f'''M291 S1 T0 P"{msg}"''')
        logger.critical(msg)
        logger.critical(str(e))
        force_quit(1)

def wait_until_backup_needed(last_commit_git, backupInt):
    # Check to see if a backup is needed else wait
    # setup date objects
    # Work in GMT
    while True:
        last_commit_date = re.findall("\d\d \w\w\w \d\d\d\d \d\d:\d\d:\d\d", last_commit_git)
        last_commit_dt = datetime.strptime(last_commit_date[0], '%d %b %Y %H:%M:%S') - timedelta(seconds=TimeZoneOffset) # local time
        last_commit_str = last_commit_dt.strftime('%d %b %Y %H:%M')
        logger.info(f'''Last Commit to Github was {last_commit_str} Local Time (TZ = {TimeZoneOffsetHrs} hrs)''')
        
        current_time_dt = datetime.now() # local time zone
        current_time_str = current_time_dt.strftime('%d %b %Y %H:%M')
        backupTime = (current_time_dt + timedelta(seconds = TimeZoneOffset)).strftime('%d %b %Y %H:%M')
        logger.debug(f'''Current time is {current_time_str}''')
        logger.debug(f'''Backup time UTC {backupTime}''')
        
        # When to backup ?
        next_backup_dt = last_commit_dt + timedelta(hours=backupInt)
        next_backup_str = next_backup_dt.strftime('%d %b %Y %H:%M')
        logger.debug(f'''Next Backup is due at {next_backup_str}''')

        if current_time_dt > next_backup_dt:
            if backupInt == 0:
                msg = "Performing single backup"
            else:
                msg = "Starting interval backup"

            logger.info(msg)
            return backupTime
        else:
            msg = f'''Next backup will start at {next_backup_str} Local Time (TZ = {TimeZoneOffsetHrs} hrs)'''
            logger.info(msg)
            d = (next_backup_dt - current_time_dt)
            s = d.seconds
            logger.debug(f'''Sleeping for {s} seconds''')
            time.sleep(s)

def list_files_in_repo(repository,branch):
    # repository is repository object
    branch_files = []
    branches = repository.get_branches()
    existing_branches = []
    for br in branches:
        existing_branches.append(br.name)

    if branch not in existing_branches: 
        msg = f'''Branch {branch} does not exist in repository {repository}'''
        sendDuetGcode(f'''M291 S1 T0 P"{msg}"''')
        logger.error(msg)
        return branch_files
    
    logger.info(f'''Getting files in {repository} from branch {branch}''')
    try:
        contents = repository.get_contents("", ref=branch)
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                contents.extend(repository.get_contents(file_content.path))
            else:
                file = file_content
                branch_files.append(str(file).replace('ContentFile(path="','').replace('")',''))
    except Exception as e:
        msg = f'''Problem getting files from {repository}'''
        sendDuetGcode(f'''M291 S1 T0 P"{msg}"''')
        logger.error(msg)
        logger.debug(str(e))
    return branch_files

def get_list_of_source_files():
    # Get a complete list of source files
    sourceFiles = []
    for dir in dirs:
        try:
            walkdir = os.path.normpath(os.path.join(topDir,str(dir[0])))
            logger.info(f'''List files in directory = {walkdir}''')
            if verbose:
                # Extra info - could be a permission issue
                path = Path(walkdir)
                owner = path.owner()
                group = path.group()
                logger.debug (f'''Permissions for {path.name} are owner: {owner} and group: {group}''')
            for (dirpath, dirnames, filenames) in os.walk(walkdir):
                for filename in filenames:
                    dirpath = dirpath.replace(topDir,'') # get the relative path
                    commit =os.path.join(dirpath,filename)
                    commit = commit.replace('\\','/')  # make sure slashes face the right way
                    if commit.startswith('/'): commit = commit.replace('/','', 1) # get rid of any leading /
                    backupfile = True
                    for ignore in gitignore:
                        logger.debug(f'''Check {commit} against {ignore[0]}''') 
                        if fnmatch(commit,ignore[0]):
                            backupfile = False

                    if backupfile:
                        sourceFiles.append(commit)
                    else:
                        logger.info(f'''Ignoring {commit} due to {ignore}''')


        except Exception as e:
            msg = f'''Error listing files!!'''
            sendDuetGcode(f'''M291 S1 T0 P"{msg}"''')
            logger.critical(msg)
            logger.critical(str(e))
            force_quit(1)

    return sourceFiles

def backupFilesToBranch(repo, branch, branch_list,sourceFiles, backupTime):
    addedfiles = []
    updatedfiles = []
    logger.info(f'''Backing up Files to {repo} branch {branch}''')
    try:
        for item in sourceFiles:
            action = backupFile(repo, branch, branch_list, backupTime, item)
            if action == 'added':
                addedfiles.append(item)
            elif action == 'updated':
                updatedfiles.append(item)            
    except Exception as e:
        msg = f'''Error trying to backup {item}'''
        sendDuetGcode(f'''M291 S1 T0 P"{msg}"''')
        logger.error(msg)
        logger.debug(str(e))
    return addedfiles, updatedfiles   

def backupFile(repo, branch, branch_list, backupTime, filepath, filecontent= ''):
    basedir = os.path.dirname(filepath)
    file = os.path.basename(filepath)   
    fileurl = os.path.join(topDir,basedir, file)
    if basedir == '':   # file is at the top level
        git_file = file
    else:                    # file is in a folder
        git_file = filepath

    file_hash = ''
    if filecontent == '':  # This is the normal case
        try:
            with open(fileurl, 'rb') as file:
                filecontent = file.read()
                file_hash = hash(fileurl,filecontent)
        except Exception as e:
            msg = f'''Could not get content of file {git_file}'''
            sendDuetGcode(f'''M291 S1 T0 P"{msg}"''')
            logger.error(msg)
            logger.debug(str(e))
        
    # Update github
    try:
        if git_file in branch_list:
            contents = repo.get_contents(git_file, ref=branch)
            logger.debug(f'''SHA from Github =  {contents.sha}''')
            logger.debug(f'''File Hash = {file_hash}''')
            if contents.sha != file_hash:  #file has changed
                logger.info(f'''Updating {git_file}''')
                repo.update_file(contents.path, backupTime, filecontent, contents.sha, branch=branch)
                return 'updated'
            else:
                logger.debug(f'''Skipping {git_file}''')
        else:
            logger.info(f'''Adding {git_file}''')
            repo.create_file(git_file, "Original", filecontent, branch=branch)
            return 'added'   
    except Exception as e:
        msg = f'''Error trying to backup the file {git_file}'''
        sendDuetGcode(f'''M291 S1 T0 P"{msg}"''')
        logger.error(msg)
    return 'error'

def removeDeletedFiles(repo, mainbranch, main_files,sourceFiles, backupTime):
    deletedfiles = []
    logger.info(f'''Delete unnecessary files from branch {mainbranch}''')
    logger.debug(sourceFiles)
    for fileurl in main_files:
        logger.debug(fileurl)
        if fileurl not in sourceFiles:
            try:
                contents = repo.get_contents(fileurl, ref=mainbranch)
                repo.delete_file(contents.path, backupTime , contents.sha, branch=mainbranch)
                logger.info(f'''Deleted {fileurl}''')
                deletedfiles.append(fileurl)
            except Exception as e:
                msg = f'''Error trying to delete {contents.path}'''
                sendDuetGcode(f'''M291 S1 T0 P"{msg}"''')
                logger.error(msg)
                logger.error(str(e))
    return deletedfiles

def hash(f, content):
    try:
        githeader = f'''blob {os.path.getsize(f)}\0'''
        githeader = bytes(githeader, 'utf-8')

        file_hash = hashlib.sha1()
        file_hash.update(githeader)
        file_hash.update(content)
        hash = file_hash.hexdigest()
    except Exception as e:
        msg = f'''Could not calculate hash for {f}'''
        logger.error(msg)
        logger.error(str(e))
        return ''
    return hash

def update_readme(repository, main, main_files, addedfiles, updatedfiles, deletedfiles):
    # Update dates and times in README.md
    local_backup_dt = datetime.now()
    local_backup_str = local_backup_dt.strftime('%d %b %Y at %H:%M')
    utc_backup_dt = datetime.now() + timedelta(seconds = TimeZoneOffset)
    utc_backup_str = utc_backup_dt.strftime('%d %b %Y at %H:%M')

    '''
    Note the use of \n in markdown for the headings and <br> for line-by-line
    '''
    
    filecontent = f'''# Last backup was:\n'''
    filecontent = filecontent + f'''## {local_backup_str} Local Time (TZ = {TimeZoneOffsetHrs} hrs)  \n'''
    filecontent = filecontent + f'''## {utc_backup_str} UTC \n'''

    filecontent = filecontent + f'''\n'''
    
    if len(addedfiles) > 0:
        filecontent = filecontent + f'''### The following files were added:\n'''
        for file in addedfiles:
            filecontent = filecontent + f'''{file}<br>'''
    else:
        filecontent = filecontent + f'''### No files were added.\n'''

    filecontent = filecontent + f'''\n'''

    if len(updatedfiles) > 0:
        filecontent = filecontent + f'''### The following files were updated:\n'''
        for file in addedfiles:
            filecontent = filecontent + f'''{file}<br>'''
    else:
        filecontent = filecontent + f'''### No files were updated.\n'''

    filecontent = filecontent + f'''\n'''

    if len(deletedfiles) > 0:
        filecontent = filecontent + f'''### The following files were deleted:\n'''
        for file in deletedfiles:
            filecontent = filecontent + f'''{file}<br>'''
    else:
        filecontent = filecontent + f'''### No files were deleted \n'''

    backupFile(repository, main, main_files, utc_backup_str, 'README.md', filecontent)

def checkPythonVersion():
    logger.debug(f'''Python version is {sys.version_info.major}.{sys.version_info.minor}''')
    if sys.version_info.major >= pythonMajor:
        if sys.version_info.minor >= pythonMinor:
            return
    else:
        logger.critical(f'''Minimum version {pythonMajor}.{pythonMinor} is required. Exiting''' )
        force_quit(1)

def force_quit(code):
    # Note:  Some libraries will send warnings to stdout / std error
    # These will display if run from console standalone
    logger.info('Shutdown Requested')
    sys.exit(int(code))

def main():
    # shutdown with SIGINT (kill -2 <pid> or SIGTERM)
    signal.signal(signal.SIGINT, force_quit) # Ctrl + C
    signal.signal(signal.SIGTERM, force_quit)

    global printerConnected, TimeZoneOffset, TimeZoneOffsetHrs, logger
    printerConnected = False
    
    init()  #  Get options

    setuplogging()
    setupLogfile()
    logger.info('Initial logfile started')
    logger.info(f'''{progName} -- {progVersion}''')
    
    checkPythonVersion()

    # Get time zone info
    TimeZoneOffset = -datetime.now().astimezone().utcoffset().total_seconds()
    logger.debug(f'''Time Zone Offset Seconds = {TimeZoneOffset}''')
    TimeZoneOffsetHrs = TimeZoneOffset/3600
    if TimeZoneOffsetHrs == 0:
        TimeZoneOffsetHrs = 0.0
    logger.info(f'''Time Zone Offset Hours = {TimeZoneOffsetHrs}''')
    
    code = loginPrinter() # only used to send messages to DWC - will work without
    if code == 200:
        printerConnected = True
        
    # Log into Github repo and get last commit date
    repository, last_commit_git = loginGithub(userName, userToken, userRepo)
    if repository is None:
        msg = f'''Could not access {userRepo}'''
        logger.critical(msg)
        force_quit(1)
        
    while True:
        backupTime = wait_until_backup_needed(last_commit_git, backupInt) # wait until backup needed
        
        setupLogfile()
        
        logger.info('New logfile started')
        logger.info(f'''{progName} -- {progVersion}''') 

        main_Files = [] # Files already in Github
        source_Files = [] # Files to be backed up
        added_Files = [] # Files added added to Github
        updated_Files = [] # Files updated in Github
        removed_Files = [] # Files removed from Github

        code = loginPrinter() # only used to send messages to DWC - will work without
        if code == 200:
            printerConnected = True
            
        # Log into Github again because considerable time may have elapsed
        repository, last_commit_git = loginGithub(userName, userToken, userRepo)
        if repository is None:
            msg = f'''Could not access {userRepo}'''
            sendDuetGcode(f'''M291 S1 T0 P"{msg}"''')
            logger.critical(msg)
            force_quit(1)

        # get a list of all files in the repo
        main_Files = list_files_in_repo(repository, main)

        # Backup each source directory
        logger.info(f'''The following dirs will be backed up {dirs}''')
        source_Files = get_list_of_source_files()

        added_Files, updated_Files = backupFilesToBranch(repository,main, main_Files, source_Files,backupTime)
        
        if not noDelete:
            source_Files.append('README.md') # Dont delete 
            source_Files.append('.gitignore') # Dont delete
        deleted_Files = removeDeletedFiles(repository,main, main_Files,source_Files, backupTime)
        
        update_readme(repository, main, main_Files, added_Files, updated_Files, deleted_Files)

        if backupInt == 0:
            msg = 'Exiting normally after single backup'
            sendDuetGcode(f'''M291 S1 T5 P"{msg}"''')
            logger.info(msg)
            force_quit(0)


###########################
# Program  begins here
###########################

if __name__ == "__main__":  # Do not run anything below if the file is imported by another program
    try:
        main()
    except SystemExit as e:
        if e.code == 9999:  # Emergency Shutdown - just kill everything
            logger.critical(f'''Forcing Termination SystemExit was {e.code}''')
            logging.shutdown()  #Flush and close the logs
            time.sleep(5) # Give it a chance to finish
            os._exit(1)