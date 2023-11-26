#!/usr/bin/python3 -u
import argparse
import shlex
import sys
from github import Github
from os import walk
from os import path
import re
from datetime import datetime, timedelta
import time 

global backupVersion
backupVersion = "0.0"

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
    parser.add_argument('-days', type=int, nargs=1, default=[7], help='Days between Backup Default is 7')
    parser.add_argument('-hours', type=int, nargs=1, default=[0], help='Hours (added to days) Default is 0')

    # Option to read from configuration file
    parser.add_argument('-file', type=argparse.FileType('r'), help='file of options', action=LoadFromFilex)

    args = vars(parser.parse_args())  # Save as a dict

    global topDir, userName, userToken, dirs, userRepo, branch, backupInt

    topDir = path.normpath(args['topDir'][0])
    userName = args['userName'][0]
    userToken = args['userToken'][0]
    userRepo = args['repo'][0]
    branch = args['branch'][0]
    dirs =  args['dir']
    backupInt = int(args['days'][0])*24 + int(args['hours'][0])

def login(user, token, repo):
    global backupTime
    try:
        print(f"""Logging in as {user}""")
        g = Github(user, token)
        repo = g.get_user().get_repo(repo)
        last_commit_str = repo.get_commits()[0].last_modified
    except Exception as e:
        print(f"""Could not log into repository {repo}""")
        print(str(e))
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
    next_backup_str = next_backup_date.strftime('%d %b %Y %H:%M:%S')
    print(f"""Last commit was {last_commit_str}""")
    print(f"""Current time is {current_time_str} GMT""")
    if current_time_date > next_backup_date:
        print("Attempting backup")
        return repo
    else:
        print(f"""No backup needed""")
        print(f"""Next backup not due until {next_backup_str} GMT""")
        d = (next_backup_date - current_time_date)
        s = d.seconds
        print(f"""Sleeping for {s} seconds""")
        time.sleep(s)


def list_files_in_repo(repo):
    global all_files    
    all_files = []
    try:
        contents = repo.get_contents("")
        while contents:
            file_content = contents.pop(0)
            if file_content.type == "dir":
                contents.extend(repo.get_contents(file_content.path))
            else:
                file = file_content
                all_files.append(str(file).replace('ContentFile(path="','').replace('")',''))
    except Exception as e:
        print(f"""Problem getting files from {repo}""")
        print(str(e))  

def backupDir(topdir, repository, branch, basedir, file): 
    global backupTime   
    fileurl = path.join(basedir, file)
    if basedir == topdir:   # file is at the top level
        git_file = file
    else:                    # file is in a folder
        git_file = path.join(basedir.replace(topdir,''),file)

    git_file = git_file.replace('\\','/')  # make sure slashes face the right way
    if git_file.startswith('/'): git_file = git_file.replace('/','', 1) # get rid of any leading /


    print(f"""Attempting to backup {git_file}""")
    try:
        with open(fileurl, 'r') as file:
            content = file.read()
    except Exception as e:
        print(f"""Could not get content of file {git_file}""")
        print(str(e))
        return

    # Upload to github
    try:
        if git_file in all_files:
            contents = repository.get_contents(git_file)
            repository.update_file(contents.path, backupTime, content, contents.sha, branch=branch)
        else:
            repository.create_file(git_file, backupTime, content, branch=branch)
    except Exception as e:
        print(f"""There was an error trying to backup the file""")
        print(str(e))

#Main
global all_files, backupTime  

init()
while True:
    repository = login(userName, userToken, userRepo)
    list_files_in_repo(repository)
    # Backup each dir in turn
    for dir in dirs:
        try:
            walkdir = path.normpath(path.join(topDir,str(dir[0])))
            print(f"""Checking directory = {walkdir}""")
            commit_list = []
            for (dirpath, dirnames, filenames) in walk(walkdir):
                for filename in filenames:
                    commit = (dirpath,filename) # Add as a tuple
                    commit_list.append(commit) 
        except Exception as e:
            print(f"""Error getting list of files from {walkdir}""")
            print(str(e))
            
        try:
            for item in commit_list:
                backupDir(topDir,repository,branch, item[0],item[1])
        except Exception as e:
            print(f"""Error trying to backup {walkdir},""")
            print(str(e))

    if backupInt == 0:
        print('exiting normally after single backup')
        sys.exit(0)