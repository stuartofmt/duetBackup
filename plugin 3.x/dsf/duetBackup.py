#!/usr/bin/python -u

"""
For use with v3.6 when virtual environments are implemented
#!/opt/dsf/plugins/duetBackup/venv/bin/python -u
"""

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

global backupVersion
backupVersion = "1.1"

# Version 1.1
# Added message for DWC monitoring
# Added display of local date for next backup
# Version 1.2
# Added -nodelete option
# Added file comparison check
# Version 1.3
# Added README.md with last backup information
# Prevented README from being deleted
# Added -ignore

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
        if verbose: print(str(loop) +' url: ' + str(url) + ' post: ' + str(post))
        try:
            if post is False:
                r = requests.get(url, timeout=timelimit, headers=urlHeaders)
            else:
                r = requests.post(url, timeout=timelimit, data=post, headers=urlHeaders)
            if r.status_code == 200: return r
        except requests.ConnectionError as e:
            print('Cannot connect to the printer - likely a network error\n')
            if verbose: print(str(e))
            error = 'Connection Error'
            printerConnected = False
        except requests.exceptions.Timeout as e:
            print('The printer connection timed out - was the printer turned on?\n')
            if verbose: print(str(e))
            error = 'Timed Out'
            printerConnected = False          
        time.sleep(1)
        loop += 1      # Try again
 
    # Call failed - Create dummy response
    class r:
        ok = False
        status_code = code
        reason = error
    return r

def datetime_from_utc_to_local(utc_datetime):
    now_timestamp = time.time()
    offset = datetime.fromtimestamp(now_timestamp) - datetime.utcfromtimestamp(now_timestamp)
    return utc_datetime + offset

def loginPrinter():
    global urlHeaders
    urlHeaders = {}
    print('Logging in to Printer')

    URL = ('http://127.0.0.1/machine/disconnect') # Close any open session
    r = urlCall(URL,  False)
    URL = ('http://127.0.0.1/machine/connect?password=' + duetPassword) # Connect with password
    r = urlCall(URL,  False)
    code = r.status_code
    if code == 200:
        if verbose: print('!!!!! Connected to printer !!!!!')
        j = json.loads(r.text)
        sessionKey = j['sessionKey']
        urlHeaders = {'X-Session-Key': sessionKey}
    #  Could not connect to printer   
    elif code == 403:
        print('!!!!! SBC Password is invalid !!!!!')
    elif code == 503:
        print('!!!!! No more SBC connections available !!!!!')
    elif code == 502:
        print('!!!!!  Incorrect DCS version  !!!!!')
    else:
        print('!!!!!  Could not connect.  Error code = ' + str(code) + ' !!!!!')
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
                print('Error: ' +  str(e))
                return
def init():
    # get config
    parser = argparse.ArgumentParser(
            description='Duet3d Backup. V' + backupVersion,
            allow_abbrev=False)
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
    # Option to read from configuration file
    parser.add_argument('-file', type=argparse.FileType('r'), help='file of options', action=LoadFromFilex)

    args = vars(parser.parse_args())  # Save as a dict

    global topDir, userName, userToken, dirs, gitignore, userRepo, main, backupInt, duetPassword, verbose, noDelete

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

    if dirs is None:
        print('Nothing specified for -dir')
        quit_forcibly

def login(user, token, repo):
    global backupTime
    while True:
        g = None
        repository = None
        try:
            print(f"""Logging into Github as {user}""")
            g = Github(user, token)
            repository = g.get_user().get_repo(repo)
            last_commit_git = repository.get_commits()[0].last_modified
        except Exception as e:
            msg = f"""Could not log into repository {repo}"""
            sendDuetGcode('M291 S1 T5 P"' + msg + '"')
            print(msg)
            if verbose: print(str(e))
            sys.exit(1)
        #Check to see if a backup is needed
        # convert to date object
        # Work in GMT
        last_commit_date = re.findall("\d\d \w\w\w \d\d\d\d \d\d:\d\d:\d\d", last_commit_git)
        last_commit_str = datetime.strptime(last_commit_date[0], '%d %b %Y %H:%M:%S')
        current_time_date = datetime.utcnow()
        current_time_str = current_time_date.strftime('%d %b %Y %H:%M')
        backupTime = current_time_date.strftime('%d %b %Y %H:%M')
        # When to backup ?
        next_backup_date = last_commit_str + timedelta(hours=backupInt)
        if verbose: print(f"""Last commit was {last_commit_str}""")
        if verbose: print(f"""Current time is {current_time_str} GMT""")
        if current_time_date > next_backup_date:
            msg = "Starting backup"
            sendDuetGcode('M291 S1 T5 P"' + msg + '"')
            print(msg)
            return repository
        else:
            local_backup_date = datetime_from_utc_to_local(next_backup_date)
            local_backup_str = local_backup_date.strftime('%d %b %Y %H:%M')
            msg = f"""Next backup will start at {local_backup_str} Local Time"""
            sendDuetGcode('M291 S1 T20 P"' + msg + '"')
            print(msg)
            d = (next_backup_date - current_time_date)
            s = d.seconds
            if verbose: print(f"""Sleeping for {s} seconds""")
            time.sleep(s)

def list_files_in_repo(repository,branch):
    # repository is repository object
    branch_files = []
    branches = repository.get_branches()
    existing_branches = []
    for br in branches:
        existing_branches.append(br.name)

    if branch not in existing_branches: 
        msg = f"""Branch {branch} does not exist in repository {repository}"""
        sendDuetGcode('M291 S1 T5 P"' + msg + '"')
        print(msg)    
        return branch_files
    
    print(f"""Getting files in {repository} from branch {branch}""")
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
        msg = f"""Problem getting files from {repository}"""
        sendDuetGcode('M291 S1 T5 P"' + msg + '"')
        print(msg)
        if verbose: print(str(e))
    return branch_files

def backupFilesToBranch(repo, branch, branch_list):
    # uses global source_files[] 
    try:
        for item in source_files:
            backupFile(repo, branch, branch_list, item)
    except Exception as e:
        msg = f"""Error trying to backup {item}"""
        sendDuetGcode('M291 S1 T5 P"' + msg + '"')
        print(msg)
        if verbose: print(str(e))   

def backupFile(repo, branch, branch_list, filepath, filecontent= ''):
    global backupTime
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
            msg = f"""Could not get content of file {git_file}"""
            sendDuetGcode('M291 S1 T5 P"' + msg + '"')
            print(msg)
            if verbose: print(str(e))
            return
        
    # Upload to github
    try:
        if git_file in branch_list:
            contents = repo.get_contents(git_file, ref=branch)
            if verbose: print(f"""SHA from Github =  {contents.sha}""")
            if verbose: print(f"""File Hash = {file_hash}""")
            if contents.sha != file_hash:  #file has changed
                print(f"""Updating {git_file}""")
                repo.update_file(contents.path, backupTime, filecontent, contents.sha, branch=branch)
            else:
                if verbose: print(f"""Skipping {git_file}""")
        else:
            print(f"""Adding {git_file}""")
            repo.create_file(git_file, "Original", filecontent, branch=branch)   
    except Exception as e:
        msg = f"""Error trying to backup the file {git_file}"""
        sendDuetGcode('M291 S1 T5 P"' + msg + '"')
        print(msg)
        if verbose: print(str(e))

def removeDeletedFiles(repo, mainbranch, main_files):
    # Uses global source_files[]
    global backupTime
    print(f"""Delete unnecessary files from branch {mainbranch}""")
    if verbose: print(source_files)
    for fileurl in main_files:
        if verbose: print(fileurl)
        if fileurl not in source_files:
            try:
                contents = repo.get_contents(fileurl, ref=mainbranch)
                repo.delete_file(contents.path, backupTime , contents.sha, branch=mainbranch)
                print(f"""Deleted {fileurl}""")
            except Exception as e:
                msg = f"""Error trying to delete {contents.path}"""
                sendDuetGcode('M291 S1 T5 P"' + msg + '"')
                print(msg)
                print(str(e))

def hash(f, content):
    try:
        githeader = f"""blob {os.path.getsize(f)}\0"""
        githeader = bytes(githeader, 'utf-8')

        file_hash = hashlib.sha1()
        file_hash.update(githeader)
        file_hash.update(content)
        hash = file_hash.hexdigest()
    except Exception as e:
        msg = f"""Could not calculate hash for {f}"""
        print(str(e))
        return ''
    return hash    
            
def quit_forcibly(*args):        
     os.kill(os.getpid(), 9)  # Brutal but effective

# Main
if __name__ == "__main__":
    # shutdown with SIGINT (kill -2 <pid> or SIGTERM)
    signal.signal(signal.SIGINT, quit_forcibly) # Ctrl + C
    signal.signal(signal.SIGTERM, quit_forcibly)


    global source_files, backupTime, printerConnected

    init()  #  Get options
    while True:
        main_files = []
        code = loginPrinter() # Returns when next backup is due
        if code == 200:
            printerConnected = True
            sendDuetGcode('M291 S1 T5 P"duetBackup Connected"')

        repository = login(userName, userToken, userRepo)
        if repository is None:
            msg = f"""Could not access {userRepo}"""
            sendDuetGcode('M291 S1 T5 P"' + msg + '"')
            print(msg)
            quit_forcibly()

        main_files = list_files_in_repo(repository, main)

        # Backup each dirs
        print(f"""The following dirs will be backed up {dirs}""")
        source_files = []
        # Get a complete list of source files
        for dir in dirs:
            try:
                walkdir = os.path.normpath(os.path.join(topDir,str(dir[0])))
                print(f"""List files in directory = {walkdir}""")
                for (dirpath, dirnames, filenames) in os.walk(walkdir):
                    for filename in filenames:
                        dirpath = dirpath.replace(topDir,'') # get the relative path
                        commit =os.path.join(dirpath,filename)
                        commit = commit.replace('\\','/')  # make sure slashes face the right way
                        if commit.startswith('/'): commit = commit.replace('/','', 1) # get rid of any leading /
                        backupfile = True
                        for ignore in gitignore:
                            if verbose: print(f"""Check {commit} against {ignore[0]}""") 
                            if fnmatch(commit,ignore[0]):
                                backupfile = False

                        if backupfile:
                            source_files.append(commit)
                        else:
                            print(f"""Ignoring {commit} due to {ignore}""")

   
            except Exception as e:
                msg = f"""Error listing files!!"""
                sendDuetGcode('M291 S1 T5 P"' + msg + '"')
                print(msg)
                if verbose: print(str(e))
                quit_forcibly()

        backupFilesToBranch(repository,main, main_files)
        if not noDelete:
            source_files.append('README.md') # Dont delete 
            source_files.append('.gitignore') # Dont delete 
            removeDeletedFiles(repository,main, main_files)
        
        # Update README.md
        last_backup_date = datetime.utcnow()
        utc_backup_str = last_backup_date.strftime('%d %b %Y at %H:%M')
        local_backup_date = datetime.now()
        local_backup_str = local_backup_date.strftime('%d %b %Y at %H:%M')
        filecontent = f"""# Last backup was:\n## {local_backup_str} local time \n## {utc_backup_str} UTC"""
        backupFile(repository, main, main_files, 'README.md', filecontent)


        if backupInt == 0:
            msg = 'Exiting normally after single backup'
            sendDuetGcode('M291 S1 T5 P"' + msg + '"')
            print(msg)
            quit_forcibly()
