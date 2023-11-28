#!/usr/bin/python3 -u
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

global backupVersion
backupVersion = "1.1"

# Version 1.1
# Added message for DWC monitoring
# Added display of local date for next backup

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
    loginRetry = 0
    while loop < limit:
        error  = ''
        code = 9999
        if verbose: print(str(loop) +' url: ' + str(url) + ' post: ' + str(post))
        try:
            if post is False:
                r = requests.get(url, timeout=timelimit, headers=urlHeaders)
            else:
                r = requests.post(url, timeout=timelimit, data=post, headers=urlHeaders)
        except requests.ConnectionError as e:
            print('Cannot connect to the printer\n')
            if verbose: print(str(e))
            error = 'Connection Error'
            printerConnected = False
        except requests.exceptions.Timeout as e:
            print('The printer connection timed out\n')
            if verbose: print(str(e))
            error = 'Timed Out'
            printerConnected = False

        if error == '': # call returned something
            code = r.status_code
            if code == 200:
                return r
            elif code == 401: # Dropped session
                loginRetry += 1
                code = loginPrinter() # Try to get a new key
                if code == 200:
                    loop = 0
                    continue  # go back and try the last call
                else: # cannot login
                    if loginRetry > 1: # Failed to get new key
                        break
            # any other http error codes are to be handled by caller            
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
    parser.add_argument('-branch', type=str, nargs=1, default=["main"], help='Github branch') 
    parser.add_argument('-dir', type=str, nargs='+', action='append', help='list of dirs to backup')
    parser.add_argument('-days', type=int, nargs=1, default=[0], help='Days between Backup Default is 7')
    parser.add_argument('-hours', type=int, nargs=1, default=[0], help='Hours (added to days) Default is 0')
    parser.add_argument('-duetPassword', type=str, nargs=1, default=[""], help='Duet3d Printer Password')
    parser.add_argument('-verbose', action='store_true', help='Detailed output')
    # Option to read from configuration file
    parser.add_argument('-file', type=argparse.FileType('r'), help='file of options', action=LoadFromFilex)

    args = vars(parser.parse_args())  # Save as a dict

    global topDir, userName, userToken, dirs, userRepo, branch, backupInt, duetPassword, verbose

    topDir = os.path.normpath(args['topDir'][0])
    userName = args['userName'][0]
    userToken = args['userToken'][0]
    userRepo = args['repo'][0]
    branch = args['branch'][0]
    dirs =  args['dir']
    backupInt = int(args['days'][0])*24 + int(args['hours'][0])
    duetPassword = args['duetPassword'][0]
    verbose = args['verbose']

def login(user, token, repo):
    global backupTime
    while True:
        g = None
        repository = None
        try:
            print(f"""Logging into Github as {user}""")
            g = Github(user, token)
            repository = g.get_user().get_repo(repo)
            last_commit_str = repository.get_commits()[0].last_modified
        except Exception as e:
            msg = f"""Could not log into repository {repo}"""
            sendDuetGcode('M291 S1 T5 P"' + msg + '"')
            print(msg)
            if verbose: print(str(e))
            sys.exit(1)
        #Check to see if a backup is needed
        # convert to date object
        lc_date = re.findall("\d\d \w\w\w \d\d\d\d \d\d:\d\d:\d\d", last_commit_str)
        last_commit_date = datetime.strptime(lc_date[0], '%d %b %Y %H:%M:%S')
        # Work in GMT
        current_time_date = datetime.utcnow()
        current_time_str = current_time_date.strftime('%d %b %Y %H:%M:%S')
        backupTime = current_time_date.strftime('%d %b %Y')
        # When to backup ?
        next_backup_date = last_commit_date + timedelta(hours=backupInt)
        if verbose: print(f"""Last commit was {last_commit_str}""")
        if verbose: print(f"""Current time is {current_time_str} GMT""")
        if current_time_date > next_backup_date:
            msg = "Starting backup"
            sendDuetGcode('M291 S1 T5 P"' + msg + '"')
            print(msg)
            return repository
        else:
            local_backup_date = datetime_from_utc_to_local(next_backup_date)
            local_backup_str = local_backup_date.strftime('%d %b %Y %H:%M:%S')
            msg = f"""Next backup will start at {local_backup_str} Local Time"""
            sendDuetGcode('M291 S1 T0 P"' + msg + '"')
            print(msg)
            d = (next_backup_date - current_time_date)
            s = d.seconds
            print(f"""Sleeping for {s} seconds""")
            time.sleep(s)

def list_files_in_repo(repository):
    # repositoty is repository object
    global all_files    
    all_files = []
    print(f"""Getting files in {repository}""")
    try:
        contents = repository.get_contents("")
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                contents.extend(repository.get_contents(file_content.path))
            else:
                file = file_content
                all_files.append(str(file).replace('ContentFile(path="','').replace('")',''))
    except Exception as e:
        msg = f"""Problem getting files from {repository}"""
        sendDuetGcode('M291 S1 T5 P"' + msg + '"')
        print(msg)
        if verbose: print(str(e))  

def backupFile(topdir, repository, branch, basedir, file): 
    global backupTime   
    fileurl = os.path.join(basedir, file)
    if basedir == topdir:   # file is at the top level
        git_file = file
    else:                    # file is in a folder
        git_file = os.path.join(basedir.replace(topdir,''),file)

    git_file = git_file.replace('\\','/')  # make sure slashes face the right way
    if git_file.startswith('/'): git_file = git_file.replace('/','', 1) # get rid of any leading /


    if verbose: print(f"""Attempting to backup {git_file}""")
    try:
        with open(fileurl, 'r') as file:
            content = file.read()
    except Exception as e:
        mag = f"""Could not get content of file {git_file}"""
        sendDuetGcode('M291 S1 T5 P"' + msg + '"')
        print(msg)
        if verbose: print(str(e))
        return

    # Upload to github
    try:
        if git_file in all_files:
            contents = repository.get_contents(git_file)
            repository.update_file(contents.path, backupTime, content, contents.sha, branch=branch)
        else:
            repository.create_file(git_file, backupTime, content, branch=branch)
    except Exception as e:
        msg = f"""There was an error trying to backup the file {git_file}"""
        sendDuetGcode('M291 S1 T5 P"' + msg + '"')
        print(msg)
        if verbose: print(str(e))

def quit_forcibly(*args):        
     os.kill(os.getpid(), 9)  # Brutal but effective

# Main
if __name__ == "__main__":
    # shutdown with SIGINT (kill -2 <pid> or SIGTERM)
    signal.signal(signal.SIGINT, quit_forcibly) # Ctrl + C
    signal.signal(signal.SIGTERM, quit_forcibly)


    global all_files, backupTime, printerConnected

    init()  #  Get options

    while True:
        code = loginPrinter() # Returns when next backup is due
        if code == 200:
            printerConnected = True
            sendDuetGcode('M291 S1 T5 P"duetBackup Connected"')

        repository = login(userName, userToken, userRepo)
        if repository is None:
            msg = f"""Could not access {userRepo}"""
            sendDuetGcode('M291 S1 T5 P"' + msg + '"')
            print(msg)
        list_files_in_repo(repository)
        # Backup each dir in turn
        for dir in dirs:
            msg = f"""Starting backup of {dir[0]}"""
            sendDuetGcode('M291 S1 T5 P"' + msg + '"')
            print(msg)
            try:
                walkdir = os.path.normpath(os.path.join(topDir,str(dir[0])))
                print(f"""Checking directory = {walkdir}""")
                commit_list = []
                for (dirpath, dirnames, filenames) in os.walk(walkdir):
                    for filename in filenames:
                        commit = (dirpath,filename) # Add as a tuple
                        commit_list.append(commit) 
            except Exception as e:
                msg = f"""Error getting list of files from {walkdir}"""
                sendDuetGcode('M291 S1 T5 P"' + msg + '"')
                print(msg)
                if verbose: print(str(e))
                
            try:
                for item in commit_list:
                    backupFile(topDir,repository,branch, item[0],item[1])
            except Exception as e:
                msg = f"""Error trying to backup {walkdir}"""
                sendDuetGcode('M291 S1 T5 P"' + msg + '"')
                print(msg)
                if verbose: print(str(e))

        if backupInt == 0:
            msg = 'Exiting normally after single backup'
            sendDuetGcode('M291 S1 T5 P"' + msg + '"')
            print(msg)
            sys.exit(0)