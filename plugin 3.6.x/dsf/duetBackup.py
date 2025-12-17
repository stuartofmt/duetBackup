
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
progVersion = "2.0"
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
- updated deprecated calls to datetime
- added file change info to README.md
- Restructured code for easier maintenance
- M291 error messages change to no timeout

# Version 1.5
- changed dependency versions
- fixed non-critical error in sig handling
- test for mandatory args in argparse
- fixed error in -ignore not specified
- fixed error if multiple -ignore

# Version 2.0
- expanded noDelete to allow selection of directories
- -ignore files will be deleted if syncing file
- changed API. Both Standalaone and SBC compatible
- made printer connection handling more efficient
- improved on DWC messages
- added aliases for Jobs and System folders
- force the defult sd folder names to lower case
- tolerates incorrect case in the default sd folder names 
- removed .gitignore file (redundant)
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

def logMessage(level,msg,error,space=False):
	if space:
		msg = f'''\n{msg}'''
		if error != '':
			error = f'''{error}\n'''

	if level == 'info':
		logger.info(msg)
		if error != '':
			logger.info(error)

	elif level == 'error':
		logger.error(msg)
		if error != '':
			logger.error(error)

	elif level == 'debug':
		logger.debug(msg)
		if error != '':
			logger.debug(error)

	elif level == 'warning':
		logger.warning(msg)
		if error != '':
			logger.warning(error)

	elif level == 'critical':
		logger.critical(msg)
		if error != '':
			logger.critical(error)

	else:
		logger.info(msg)
		if error != '':
			logger.info(error)

def sendDuetGcode(command):
	# send a gcode command to Duet
	if reconnectPrinter() :
		command = f'''/rr_gcode?gcode={command}'''  #Post includes command type in url
		urlCall(printerUrl, command, False) # Post form - sent blindly

def urlCall(url, cmd, post):
	# Makes all the calls to the printer
	# If post is True then make a http post call
	# Get commands need a leading /
	# Set defaults for return codes
	code = 0
	error = 'Unknown'

	timelimit = 5  # timout for call to return
	loop = 0
	limit = 2  # seems good enough to catch transients
	r = ''
	if post is False:
		url = url + cmd  # concatenate for GET
	while loop < limit:
		try:
			if post is False:
				msg = f'''Connection attempt: {loop} url: {url} post:{post}'''
				logMessage('debug',msg,'',True)
				r = requests.get(url, timeout=timelimit) # if using rr_ API
			else: #post includes the http command type in the url
				msg = f'''Connection attempt {loop} url: {url} cmd: {cmd} post:{post}'''
				logMessage('debug',msg,'',True)
				r = requests.post(url, timeout=timelimit, data=cmd) # If using rr_ API

		except requests.ConnectionError as e:
			msg = 'Cannot connect to the printer - likely a network error'
			logMessage('info',msg,str(e),True)
		except requests.exceptions.Timeout as e:
			msg = 'Timed out - Is the printer turned on?'
			logMessage('info',msg,'',True)
		finally:
			if r.status_code in [200,204]: #204 is no content e.g. disconnect
				return r.status_code, r.text
			else:
				time.sleep(1)
				loop += 1 # Loop back and try again
	
	msg = f'''Error - code = {r.status_code} payload = {r.text}'''
	logMessage('debug',msg,'',True)

	return r.status_code, r.text

def reconnectPrinter():
	urlCall(printerUrl, '/rr_disconnect', False) #Called blindly - does not return anything
	result = loginPrinter()
	return result

def loginPrinter(): #logon and get key parameters
	cmd = (f'''/rr_connect?sessionKey=yes&password={duetPassword}''') # using rr_ API
	code, payload = urlCall(printerUrl, cmd, False)
	if code in [200,204]:
		return True
	elif code == 403:
		msg = 'Password is invalid'
	elif code == 503:
		msg = 'No more connections available'
	elif code == 502:
		msg = 'Incorrect DCS version'
	else:
		msg = f'''Is the Printer turned on?.'''
	
	msg = f'''Login issue: {msg} code = {code}'''
	logMessage('info',msg,'',True)
	return False

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
				msg = f'''Problem parsing config file - {str(e)}'''
				logger.info(msg)
				return
def init():
	# get config
	parser = argparse.ArgumentParser(
			description=f'''Duet3d Backup - V{progVersion}, allow_abbrev=False''')

	parser.add_argument('-userName', type=str, nargs=1, default = [''], help='Github User Name')
	parser.add_argument('-userToken', type=str, nargs=1, default = [''],  help='Github Token')
	parser.add_argument('-rep', type=str, nargs=1, default = [''], help='Github Repo')
	parser.add_argument('-branch', type=str, nargs=1, default=["main"], help='Github current branch')
	parser.add_argument('-dir', type=str, nargs='*', action='append', default = [], help='list of dirs to backup')
	parser.add_argument('-ignore', type=str, nargs='*', action='append', default = [], help='list of patterns to ignore')
	parser.add_argument('-days', type=int, nargs=1, default=[0], help='Days between Backup Default is 7')
	parser.add_argument('-hours', type=int, nargs=1, default=[0], help='Hours (added to days) Default is 0')
	parser.add_argument('-duetPassword', type=str, nargs=1, default=["reprap"], help='Duet3d Printer Password')
	parser.add_argument('-verbose', action='store_true', help='Detailed output')
	parser.add_argument('-noDelete', type=str, nargs='*', action='append', default = [], help='list of folders to ignore in delete')
	parser.add_argument('-logfile', type=str, nargs=1, default=['/opt/dsf/sd/sys/duetBackup/duetBackup.log'], help='full logfile name')
	#parser.add_argument('-file', type=argparse.FileType('r'), help='file of options', action=LoadFromFilex)
	parser.add_argument('-duetIP', type=str, nargs=1, default=["127.0.0.1"], help='Duet3d Printer IP')
  
	# Option to read from configuration file
	parser.add_argument('-file', type=argparse.FileType('r'), help='file of options', action=LoadFromFilex)

	global userName, userToken, dirs, gitignore, userRepo, main, backupInt, duetPassword, verbose, noDelete
	global logfilename, duetIP

	args = vars(parser.parse_args())  # Save as a dict

	userName = args['userName'][0]
	userToken = args['userToken'][0]
	userRepo = args['rep'][0]
	main = args['branch'][0]
	dirs =  args['dir']
	gitignore =  args['ignore']
	backupInt = int(args['days'][0])*24 + int(args['hours'][0])
	duetPassword = args['duetPassword'][0]
	verbose = args['verbose']
	noDelete = args['noDelete']
	logfilename = args['logfile'][0]
	duetIP = args['duetIP'][0]

def update_list(list,alias,real):
	if len(list) == 0 or (len(list) == 1 and list[0] == []):
		return list
	replaceAlias = re.compile(re.escape(alias), re.IGNORECASE)
	list[:] = [[replaceAlias.sub(real,x[0])] if x[0].casefold().startswith(alias.casefold()) else x for x in list]
	return list

def check_for_alias():
	global dirs, noDelete
	#change aliases
	alias = 'sd/systems'
	real = 'sd/sys'
	dirs = update_list(dirs,alias,real)
	noDelete = update_list(noDelete,alias,real)

	alias = 'sd/jobs'
	real = 'sd/gcodes'
	dirs = update_list(dirs,alias,real)
	noDelete = update_list(noDelete,alias,real)
	#change incorrect case (looks strange but is ok)
	aliases = ['sd/filaments','sd/macros','sd/firmware','sd/menu']
	for alias in aliases:
		real = alias
		dirs = update_list(dirs,alias,real)
		noDelete = update_list(noDelete,alias,real)

def check_for_mandatory():
	mandatory_items = True

	if userName == '':
		msg = '-userName is required'
		logMessage('critical',msg,'',True)
		mandatory_items = False
	if userToken == '':
		msg = '-userToken is required'
		logMessage('critical',msg,'',True)
		mandatory_items = False
	if userRepo == '':
		msg = '-rep is required'
		logMessage('critical',msg,'',True)
		mandatory_items = False
	if dirs == []:
		msg = '-dir is required'
		logMessage('critical',msg,'',True)
		mandatory_items = False
	if not mandatory_items:
		force_quit(1)

def list_options():
	global deleteFiles, dirs, gitignore, noDelete

	msg = 'The following dir(s) will be backed up:'
	logMessage('info',msg,'',True)
	dirs[:] = [x for x in dirs if x != []] #get rid of empty entries
	for dir in dirs:
		logger.info(f'''-dir {dir[0]}''')

	if gitignore == [] or gitignore == [[]] : # -ignore omitted or used without pattern
		msg = 'All files will be backed up'
		logMessage('info',msg,'',True)
	else:
		msg = 'The following pattern(s) will be ignored:'
		logMessage('info',msg,'',True)
		gitignore[:] = [x for x in gitignore if x != []] #get rid of empty entries
		for ignore in gitignore:
			logger.info(f'''-ignore {ignore[0]}''')

	if noDelete == []: # option omitted
		msg = 'Files will be synced'
		logMessage('info',msg,'',True)
	elif noDelete == [[]] : # -noDelete used with no argument
		msg = 'No files will be removed'
		logMessage('info',msg,'',True)
		deleteFiles = False
	else:
		msg = 'Files will not be removed from the following dir(s):'
		logMessage('info',msg,'',True)
		noDelete[:] = [x for x in noDelete if x != []] # get rid of empty entries
		for dir in noDelete:
			logger.info(f'''-noDelete {dir[0]}''')


def loginGithub(user, token, repo):
	g = None
	repository = None
	try:
		logger.info(f'''Logging into Github as {user}''')
		g = Github(user, token)
		repository = g.get_user().get_repo(repo)
		last_commit_git = repository.get_commits()[0].last_modified
		logger.debug(f'''Git reported last backup on {last_commit_git}''')
		return repository, last_commit_git
	except Exception as e:
		msg = f'''Could not log into repository {repo}'''
		logMessage('critical',msg,str(e),True)
		sendDuetGcode(f'''M291 S1 T0 P"{msg}"''')
		force_quit(1)

def wait_until_backup_needed(last_commit_git, backupInt):
	# Check to see if a backup is needed else wait
	# setup date objects
	# Work in GMT
	while True:
		last_commit_date = re.findall("\d\d \w\w\w \d\d\d\d \d\d:\d\d:\d\d", last_commit_git)
		last_commit_dt = datetime.strptime(last_commit_date[0], '%d %b %Y %H:%M:%S') + timedelta(seconds=TimeZoneOffset) # local time
		last_commit_str = last_commit_dt.strftime('%d %b %Y %H:%M')
		logger.info(f'''\nLast backup to Github was {last_commit_str} Local Time (TZ = {TimeZoneOffsetHrs:+.1f} hrs)''')
		
		current_time_dt = datetime.now() # local time zone
		current_time_str = current_time_dt.strftime('%d %b %Y %H:%M')
		backupTime = (current_time_dt - timedelta(seconds = TimeZoneOffset)).strftime('%d %b %Y %H:%M')
		logger.debug(f'''Current time (local) is {current_time_str}''')
		logger.debug(f'''Current time  (UTC) {backupTime}''')
		
		# When to backup ?
		next_backup_dt = last_commit_dt + timedelta(hours=backupInt)
		next_backup_str = next_backup_dt.strftime('%d %b %Y %H:%M')
		logger.debug(f'''Next Backup is due at {next_backup_str} Local time''')

		if (current_time_dt >= next_backup_dt) or backupInt == 0:
			return backupTime
		else:
			msg = f'''Next backup will start at {next_backup_str} Local Time (TZ = {TimeZoneOffsetHrs:+.1f} hrs)'''
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
		logMessage('error',msg,'',True)
		sendDuetGcode(f'''M291 S1 T0 P"{msg}"''')
		return branch_files
	
	msg = f'''Getting files in {repository} from branch {branch}'''
	logMessage('info',msg,'',True)
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
		logMessage('error',msg,str(e),True)
		sendDuetGcode(f'''M291 S1 T0 P"{msg}"''')
	return branch_files


def getFiles(dir):
	if reconnectPrinter() :
		command = f'''/rr_filelist?first=0&dir={dir}'''
		code, payload = urlCall(printerUrl, command, False) # Get form
		j = []
		entries = []
		if code == 200:
			try:
				j = json.loads(payload)
				status = j['err']
				if status == 0 and j['next'] == 0: #compete list
					entries = j['files']
				elif status == 1: # Drive does not exist
					msg = f'''Drive {dir} does not exist'''
				elif status == 2: # Directory  does not exist
					msg = f'''Directory {dir} does not exist'''
			except Exception as e:
				msg = f'''Unknown error getting files from {dir}'''
				logMessage('info',msg,str(e),True)
			finally:
				if status > 0:
					logMessage('info',msg,'',False)
				return entries
	return []

def getDuetFiles(dir,filelist = None):
	# Recursive function
	# Top level call needs filelist set to [] or omitted
	if filelist is None:
		filelist = []
	msg = f'''Getting files in {dir}'''
	logMessage('debug',msg,'',True)
	# get the files in the current dir
	entries = getFiles(dir)
	if entries != []:
		moredirs = []
		for entry in entries:
			if entry['type'] == 'd':
				moredirs.append(f'''{dir}{entry["name"]}/''')
			if entry['type'] == 'f':
				filelist.append(f'''{dir.replace('0:/','sd/',1)}{entry['name']}''')	
		for nextdir in moredirs:
			filelist = getDuetFiles(nextdir,filelist)
	return filelist

def get_list_of_source_files(dirs):
	# Get a complete list of source files
	sourcefiles = []
	try:
		for dir in dirs:
			dir = f'''{dir[0].replace('sd/','0:/')}'''
			if not dir.endswith('/'):
				dir = dir + '/'
			list = getDuetFiles(dir,[]) # can optionally omit second argument
			if list != []:
				for filename in list:
					if not ignoreFile(filename):
						sourcefiles.append(filename)
	except Exception as e:
			logMessage('info',str(e),'',True)
			sendDuetGcode(f'''M291 S1 T0 P"{str(e)}"''')
	
	return sourcefiles
   
def ignoreFile(filename):
	for ignore in gitignore:
		logger.debug(f'''Checking {filename} for ignore {ignore[0]}''')
		if fnmatch(filename,ignore[0]): # filename matches ignore condition
			logger.debug(f'''Ignoring {filename} because of match with {ignore[0]}''') 
			return True
	return False

def backupFilesToBranch(repo, branch, branch_list,sourceFiles, backupTime):
	addedfiles = []
	updatedfiles = []
	logger.info(f'''\nBacking up Files to {repo} branch {branch}''')
	for item in sourceFiles:
		action = backupFile(repo, branch, branch_list, backupTime, item)
		if action == 'Adding':
			addedfiles.append(item)
		elif action == 'Updating':
			updatedfiles.append(item)
		elif action == 'Error':
			msg = f'''Uncaught error trying to backup {item}'''
			logMessage('error',msg,'',True)

	return addedfiles, updatedfiles   
	
def downloadFile(file):
	if reconnectPrinter():
		commandUrl = f'''{printerUrl}/rr_download?name=''' 
		code, payload = urlCall(commandUrl, file, False) # Get form
		if code == 404:
			msg = f'''Could not download file {file}'''
			logMessage('info',msg,'',True)
			return ''
		
		return payload
	
def getHash(filepath, filecontent):
	file_hash = ''
	if filecontent == '':  # This is the normal case
		try:
			if filepath.startswith('sd/'):
				file = filepath.replace('sd/','/')
			filecontent = downloadFile(file)
			file_hash = hash(filepath,filecontent)
		except Exception as e:
			msg = f'''Could not get content of file {filepath}'''
			logMessage('error',msg,str(e),True)
			sendDuetGcode(f'''M291 S1 T0 P"{msg}"''')
	else:
		file_hash = hash(filepath,filecontent)
	return file_hash , filecontent   

def backupFile(repo, branch, branch_list, backupTime, filepath, filecontent = None):
	if filecontent is None: # Done this way for safely against mutable variables
		filecontent = ''
	# if no filecontent file_hash will try to download the conetent
	file_hash,filecontent = getHash(filepath,filecontent)

	# Update github
	try:
		action = ''
		if filepath in branch_list:
			contents = repo.get_contents(filepath, ref=branch)
			logger.debug(f'''\nGit Hash:  {contents.sha}''')
			logger.debug(f'''File Hash: {file_hash}''')

			if contents.sha != file_hash:  #file has changed
				action = 'Updating'
				logger.info(f'''{action} {filepath}''')
				repo.update_file(contents.path, backupTime, filecontent, contents.sha, branch=branch)

			else:
				action = 'Skipping'
				logger.debug(f'''{action} {filepath}''')
		else:
			action = 'Adding'
			logger.info(f'''{action} {filepath}''')
			repo.create_file(filepath, "Original", filecontent, branch=branch)
   
	except Exception as e:
		msg = f'''Github error applying {action} to file {filepath}'''
		logMessage('error',msg,str(e),True)
		sendDuetGcode(f'''M291 S1 T0 P"{msg}"''')
		action = 'Error'
	return action

def removeDeletedFiles(repo, mainbranch, main_files,sourceFiles, backupTime):
	deletedfiles = []
	msg = f'''Delete unnecessary files from branch {mainbranch}'''
	logMessage('info',msg,'',True)
	for fileurl in main_files:
		if fileurl == 'README.md':  # Never delete 
			continue
		#Decide if it should be deleted
		protectedDir = False
		if fileurl not in sourceFiles: # A delete candidate		
			if noDelete != [] : # i.e. have to consider noDelete dirs
				for ignore_delete in noDelete: # Dont delete files in specified directories
					if fileurl.startswith(ignore_delete[0]): # file is in delete protected dir
						logger.debug(f'''{fileurl} not deleted (noDelete {ignore_delete[0]})''')
						protectedDir = True
						break # inner loop		
			if protectedDir:
				continue # Dont delete - check next file
			
			# Delete file
			try:
				contents = repo.get_contents(fileurl, ref=mainbranch)
				repo.delete_file(contents.path, backupTime , contents.sha, branch=mainbranch)
				logger.info(f'''Deleted {fileurl}''')
				deletedfiles.append(fileurl)
			except Exception as e:
				msg = f'''Error trying to delete {contents.path}'''
				logMessage('error',msg,str(e),True)
				sendDuetGcode(f'''M291 S1 T0 P"{msg}"''')

	return deletedfiles

def hash(f, content):
	try:
		#size = len(content.encode('utf-8'))  #string must be encoded as bytes
		size = len(content)  #string must be encoded as bytes
		githeader = f'''blob {size}\0'''
		githeader = bytes(githeader,'utf-8')
		file_hash = hashlib.sha1()
		file_hash.update(githeader)
		file_hash.update(content.encode('utf-8')) # Content must be encoded as bytes
		hash = file_hash.hexdigest()
	except Exception as e:
		msg = f'''Could not calculate hash for {f}'''
		logMessage('error',msg,str(e),True)
		return ''
	return hash

def update_readme(repository, main, main_files, addedfiles, updatedfiles, deletedfiles):
	# Update dates and times in README.md
	local_backup_dt = datetime.now()
	local_backup_str = local_backup_dt.strftime('%d %b %Y at %H:%M')
	utc_backup_dt = datetime.now() - timedelta(seconds = TimeZoneOffset)
	utc_backup_str = utc_backup_dt.strftime('%d %b %Y at %H:%M')

	'''
	Note the use of \n in markdown for the headings and <br> for line-by-line
	'''
	
	filecontent = f'''# Last backup was:\n'''
	filecontent = filecontent + f'''## {local_backup_str} Local Time (TZ = {TimeZoneOffsetHrs:+.1f} hrs)  \n'''
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
		for file in updatedfiles:
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
		msg = f'''Minimum version {pythonMajor}.{pythonMinor} is required. Exiting'''
		logMessage('critical',msg,'',True)
		force_quit(1)

def sig_handler(signum, frame):
	signame = signal.Signals(signum).name
	logger.info(f'Shutting down.  Recieved signal {signame} ({signum})')
	force_quit(0)
	#  forcing exit for windows compatability

def force_quit(code):
	# Note:  Some libraries will send warnings to stdout / std error
	# These will display if run from console standalone
	logger.info('Shutdown Requested')
	os._exit(code)

def Main():
	# shutdown with SIGINT (kill -2 <pid> or SIGTERM)
	signal.signal(signal.SIGINT, sig_handler)
	signal.signal(signal.SIGTERM, sig_handler)

	global sessionKey, printerUrl, TimeZoneOffset, TimeZoneOffsetHrs, logger
	global deleteFiles
	sessionKey = {} # session key if password used
	deleteFiles = True

	
	init()  #  Get options
	printerUrl = f'''http://{duetIP}'''
	setuplogging()
	setupLogfile()
	logger.info('Initial logfile started')
	logger.info(f'''{progName} -- {progVersion}''')

	check_for_mandatory()
	check_for_alias()
	checkPythonVersion()

	# Get time zone info
	TimeZoneOffset = datetime.now().astimezone().utcoffset().total_seconds()
	logger.debug(f'''Time Zone Offset Seconds = {TimeZoneOffset}''')
	TimeZoneOffsetHrs = TimeZoneOffset/3600
	logger.info(f'''Time Zone Offset Hours = {TimeZoneOffsetHrs:+.1f}''')

	# Log into Github repo and get last commit date
	repository, last_commit_git = loginGithub(userName, userToken, userRepo)
	if repository is None:
		msg = f'''Could not access {userRepo}'''
		logMessage('critical',msg,'',True)
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
		deleted_Files = [] # Files removed from Github

		if backupInt == 0:
			msg = "Single backup starting."
			sendDuetGcode(f'''M291 S1 T20 P"{msg}"''')
		else:
			msg = "Interval backup starting"

		logger.info(msg)

		# Log into Github again because considerable time may have elapsed
		repository, last_commit_git = loginGithub(userName, userToken, userRepo)
		if repository is None:
			msg = f'''Could not access {userRepo}'''
			logMessage('critical',msg,'',True)
			sendDuetGcode(f'''M291 S1 T0 P"{msg}"''')
			force_quit(1)

		list_options()

		# Get list of files in didirectories to be backed up
		source_Files = get_list_of_source_files(dirs)

		if source_Files != []: # will be empty if printer disconnected

			# get a list of all files in the repo
			main_Files = list_files_in_repo(repository, main)

			added_Files, updated_Files = backupFilesToBranch(repository,main, main_Files, source_Files,backupTime)

			if noDelete != [[]]: # Delete unnecessary files
				deleted_Files = removeDeletedFiles(repository,main, main_Files,source_Files, backupTime)
			else:
				msg = f'''No Deletions requested'''
				logMessage('info',msg,'',True)

			update_readme(repository, main, main_Files, added_Files, updated_Files, deleted_Files)
		
		if backupInt == 0:
			msg = 'Exiting normally after single backup'
			logMessage('info',msg,'',True)
			sendDuetGcode(f'''M291 S1 T0 P"{msg}"''')
			break
		if source_Files == []:
			#Likely could not connect
			recheck = int(backupInt*3600 / 4) # backupInt is hours
			rechecktime = timedelta(seconds = recheck).split(':')
			logMessage('info',f'''Could not get file list from printer, try again in {rechecktime[0]} hours {rechecktime[1]} minutes''','',True)
			time.sleep(recheck)

###########################
# Program  begins here
###########################

if __name__ == "__main__":  # Do not run anything below if the file is imported by another program
	try:
		Main()
	except SystemExit as e: # just in case something bubbles up ...
		msg = f'''Terminated with exit code {e.code}'''
		if logging:
			logging.shutdown()  #Flush and close the logs
			time.sleep(1) # Give it a chance to finish
		else:
			logger.info(msg)