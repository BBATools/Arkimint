#!/usr/bin/python3

# TODO: Se også denne: https://github.com/yiwensong/ubuntu-setup?files=1

import sys

# Check Python version
if sys.version_info[0] < 3:
    print(
        'You have invoked installer with Python 2. It must be run with Python 3.'
    )
    sys.exit()
else:
    import os
    import pathlib
    import subprocess
    import urllib.request
    import json
    import re
    from datetime import datetime
    import time
    from pathlib import *


def read_user_prefs(preffile):
    r = re.compile(rb"\s*user_pref\(([\"'])(.+?)\1,\s*(.+?)\);")
    rv = {}
    for l in preffile:
        m = r.match(l)
        if not m:
            continue
        k, v = m.group(2), m.group(3)
        try:
            rv[k] = json.loads(v)
        except Exception as ex:
            print("failed to parse", k, v, ex)
    return rv


class Cmd:
    def __init__(self, cmdArgs, stdin=None):
        self.cmd = ' '.join(cmdArgs)
        self.cmdArgs = cmdArgs
        self.stdin = stdin
        self.stdout = None
        self.stderr = None
        self.returncode = None
        self.succeeded = None

        if stdin and type(stdin) is str:
            if stdin[-1] == '\n':
                self.stdin = str.encode(stdin[:-1])
            else:
                self.stdin = str.encode(stdin)


def runCmd(cmdArgs, stdin=None, piped=False):
    if len(cmdArgs) == 1 and '|' in cmdArgs[0]:
        args = [i.strip().split(' ') for i in cmdArgs[0].split('|')]
        return runCmd(args, piped=True)

    if piped:
        if len(cmdArgs) > 2:
            return runCmd(
                cmdArgs[-1], stdin=runCmd(cmdArgs[:-1], piped=True).stdout)
        elif len(cmdArgs) == 2:
            return runCmd(
                cmdArgs[1], stdin=runCmd(cmdArgs[0], piped=False).stdout)

    cmd = Cmd(cmdArgs, stdin)

    try:
        if cmd.stdin:
            if sys.version_info[1] < 7:  # Add capture_output for Python version 3.7 or greater
                result = subprocess.run(
                    cmd.cmdArgs,
                    input=cmd.stdin,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    #timeout=600,
                    check=True)
            else:
                result = subprocess.run(
                    cmd.cmdArgs,
                    input=cmd.stdin,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    capture_output=True,  # python >= 3.7
                    #timeout=600,
                    check=True)
        else:
            if sys.version_info[1] < 7:
                result = subprocess.run(
                    cmd.cmdArgs,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    #timeout=600,
                    check=True)

            else:
                result = subprocess.run(
                    cmd.cmdArgs,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    capture_output=True,  # python >= 3.7
                    #timeout=600,
                    check=True)

        cmd.stdout = result.stdout.decode("utf-8")
        cmd.stderr = result.stderr.decode("utf-8")

    except subprocess.CalledProcessError as e:
        cmd.succeeded = False
        cmd.returncode = e.returncode
        cmd.stdout = e.stdout.decode("utf-8")
        cmd.stderr = e.stderr.decode("utf-8")
    except subprocess.TimeoutExpired as e:

        cmd.succeeded = False
        cmd.stdout = 'COMMAND TIMEOUT ({}s)'.format(e.timeout)
    except Exception as e:
        cmd.succeeded = False
        cmd.stdout = ''
        if hasattr(e, 'message'):
            cmd.stderr = e.message
        else:
            cmd.stderr = str(e)
    else:
        cmd.returncode = 0
        cmd.succeeded = True
    finally:
        return cmd


def checkPackage(package):
    cmd = runCmd(['dpkg', '-s', package])

    if cmd.succeeded and 'Status: install ok installed' in cmd.stdout:
        return True
    else:
        return False


def getRepoList():
    repoList = []
    for root, dirs, files in os.walk('/etc/apt/'):
        for file in files:
            if file.endswith(".list"):
                with open(os.path.join(root, file)) as f:
                    lines = f.readlines()
                    for line in lines:
                        if re.match(
                                '^deb http:\/\/ppa\.launchpad\.net\/[a-z0-9\-]+\/[a-z0-9\-]+',
                                line):
                            data = line.split('/')
                            repoList.append('ppa:' + data[3] + '/' + data[4])

    return repoList


def notify(message):
    userID = runCmd(['id', '-u', os.environ['SUDO_USER']]).stdout.replace(
        '\n', '')
    runCmd([
        'sudo', '-u', os.environ['SUDO_USER'],
        'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{}/bus'.format(userID),
        'notify-send', '-i', 'utilities-terminal', 'Arkimint Installer',
        message
    ])


def waitForDpkgLock():
    tries = 0
    while True:
        dpkgLock = runCmd(['fuser', '/var/lib/dpkg/lock'])
        aptLock = runCmd(['fuser', '/var/lib/apt/lists/lock'])

        if dpkgLock.stdout != '' or aptLock.stdout != '':
            time.sleep(3)
            tries += 1
        else:
            return True
        if tries > 10:
            return False


class Zenity:
    def __init__(self):
        pass

    @staticmethod
    def password():
        runCmd(['sudo', '-k'])

        while True:
            getPasswordCmd = runCmd([
                'zenity', '--password', '--title=Arkimint Installer',
                '--window-icon=arkimint_fin_32px.png'
            ])

            if getPasswordCmd.succeeded:
                checkPasswordCmd = runCmd(
                    ['sudo', '-S', 'id', '-u'],
                    stdin=getPasswordCmd.stdout + '\n')

                if checkPasswordCmd.succeeded and checkPasswordCmd.stdout.replace(
                        '\n', '') == '0':
                    return getPasswordCmd.stdout.replace('\n', '')
                else:
                    runCmd([
                        'zenity', '--info', '--width=200',
                        '--title=Arkimint Installer',
                        '--text=Wrong password, try again'
                    ])
            else:
                sys.exit()

    @staticmethod
    def progressBar(pulsating=False,
                    noCancel=False,
                    title='',
                    text='',
                    percentage=0,
                    height=100,
                    width=500):
        args = ['zenity', '--progress']

        if pulsating:
            args.append('--pulsate')

        if noCancel:
            args.append('--no-cancel')

        args.append('--title={}'.format(title))
        args.append('--text={}'.format(text))
        args.append('--percentage={}'.format(percentage))
        args.append('--height={}'.format(height))
        args.append('--width={}'.format(width))
        args.append(
            '--window-icon=/usr/share/icons/Mint-X/categories/32/applications-development.png'
        )

        process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        def update(message='', percent=0):
            process.stdin.write((str(percent) + '\n').encode())
            process.stdin.flush()

            if message:
                process.stdin.write(('# %s\n' % str(message)).encode())
                process.stdin.flush()

            return process.returncode

        return update

    @staticmethod
    def error(message):
        runCmd([
            'zenity', '--error', '--title=Arkimint Installer', '--height=100',
            '--width=500',
            '--window-icon=/usr/share/icons/Mint-X/categories/32/applications-development.png',
            '--text={}'.format(message)
        ])

    @staticmethod
    def table(data):
        args = [
            'zenity', '--list', '--checklist', '--height=720', '--width=1000',
            '--title=Arkimint Installer',
            '--window-icon=/usr/share/icons/Mint-X/categories/32/applications-development.png',
            '--text=Select tasks to perform:', '--column=Selection',
            '--column=Task', '--column=Description'
        ]

        args.extend(data)

        return runCmd(args)

    @staticmethod
    def info(message):
        runCmd([
            'zenity', '--info', '--title=Arkimint Installer',
            '--window-icon=/usr/share/icons/Mint-X/categories/32/applications-development.png',
            '--height=100', '--width=200', '--text={}'.format(message)
        ])

    @staticmethod
    def question(message, height=100, width=200):
        question = runCmd([
            'zenity', '--question', '--title=Arkimint Installer',
            '--window-icon=/usr/share/icons/Mint-X/categories/32/applications-development.png',
            '--height={}'.format(height), '--width={}'.format(width),
            '--text={}'.format(message)
        ])

        return question.succeeded

    @staticmethod
    def textInfo(message):
        data = runCmd(['echo', message]).stdout
        runCmd(
            [
                'zenity', '--text-info', '--height=700', '--width=800',
                '--title=Arkimint Installer',
                '--window-icon=/usr/share/icons/Mint-X/categories/32/applications-development.png'
            ],
            stdin=data)

    @staticmethod
    def list(message, elements):
        cmd = [
            'zenity', '--list', '--height=500', '--width=500',
            '--title=Arkimint Installer',
            '--window-icon=/usr/share/icons/Mint-X/categories/32/applications-development.png',
            '--text={}'.format(message), '--hide-header', '--column',
            'Tasks with errors'
        ]

        cmd.extend(elements)
        runCmd(cmd)


class Alfred:
    def __init__(self, localRecipes=True):
        self.logFile = '/var/log/arkimint_installer.log'

        with open(self.logFile, 'a') as f:
            f.write(100 * '=' + '\n')
            f.write('NEW SESSION ' +
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '\n')
            f.write(runCmd(['lsb_release', '-d']).stdout)
            f.write(runCmd(['uname', '-a']).stdout)

        self.errors = []

        # Set language
        runCmd(['export', 'LC_ALL=C'])

        # Check Zenity package
        zenity = checkPackage('zenity')

        # Check distro
        # TODO: Fjerne distro check annet sted eller
        supportedDistro = False

        with open('/etc/os-release', 'r') as f:
            lines = f.readlines()

            for line in lines:
                if line == 'ID_LIKE=ubuntu\n' or line == 'ID_LIKE=debian\n' or line == 'ID=debian\n':
                    supportedDistro = True
                    break

        if not supportedDistro:
            message = "This is not an Ubuntu or Ubuntu derivative distro."

            if zenity:
                Zenity.error(message)
            else:
                print(message)

            sys.exit()

        # Check architecture
        arch = self.runAndLogCmd(['uname', '-m'])

        if arch.stdout != 'x86_64\n':
            message = "This is not a 64-bit system."

            if zenity:
                Zenity.error(message)
            else:
                print(message)

            sys.exit()

        # Check /var/lib/dpkg/lock to ensure we can install packages
        lock = runCmd(['fuser', '/var/lib/dpkg/lock'])

        if lock.stdout != '':
            message = 'Another program is installing or updating packages. Please wait until this process finishes and then launch Arkimint Installer again.'

            if zenity:
                Zenity.error(message)
            else:
                print(message)

            sys.exit()

        # Check connectivity
        ping = self.runAndLogCmd(['ping', '-c', '1', 'google.com'])

        if not ping.succeeded:
            message = 'There is no connection to the Internet. Please connect and then launch Arkimint Installer again.'

            if zenity:
                Zenity.error(message)
            else:
                print(message)

        # Repair installation interruptions
        self.runAndLogCmd(['dpkg', '--configure', '-a'])

        # Get repositories
        self.repoList = getRepoList()

        # Install Zenity if needed
        if not zenity:
            self.runAndLogCmd(['apt-get', 'install', '-y', 'zenity'])

        # Load recipes
        if localRecipes:
            bindir = os.path.abspath(os.path.dirname(__file__))
            with open(bindir + '/recipes.json', 'r') as f:
                self.recipes = json.load(f)
        else:
            url = 'https://raw.githubusercontent.com/derkomai/alfred/master/recipes.json'
            jsonData = urllib.request.urlopen(url).read().decode('utf-8')
            self.recipes = json.loads(jsonData)

        # Set recipe selections to false
        for i in range(len(self.recipes)):
            self.recipes[i]['selected'] = False

    def show(self):
        while True:
            # Build table
            tableData = []

            default_install = ["Arkimint Core", "Preservation Workbench"]
            for recipe in self.recipes:
                if recipe['name'] in default_install:
                    recipe['selected'] = True

                if recipe['selected']:
                    select = 'TRUE'
                else:
                    select = 'FALSE'

                tableData.append(select)
                tableData.append(recipe['name'])
                tableData.append(recipe['description'])

            table = Zenity.table(tableData)

            # Check for closed window / cancel button
            if not table.succeeded:
                sys.exit()

            # Check zero tasks selected
            if table.stdout == '':
                Zenity.info('No tasks were selected')

                for i in range(len(self.recipes)):
                    self.recipes[i]['selected'] = False

                continue
            else:
                taskList = table.stdout[:-1].split('|')  # Last char is \n
                self.taskList = []

                for i in range(len(self.recipes)):
                    if self.recipes[i]['name'] in taskList:
                        self.taskList.append(i)
                        self.recipes[i]['selected'] = True
                    else:
                        self.recipes[i]['selected'] = False
                break

    def process(self, proxy_address, proxy_port):
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

        # Get confirmation
        message = 'The selected tasks will be performed now. '
        message += "You won't be able to cancel this operation once started.\n\n"
        message += 'Are you sure you want to continue?'

        while True:
            if not Zenity.question(message, height=100, width=350):
                self.show()
            else:
                break

        # Collect commands info
        ppas = []
        packages = []
        # snaps = []
        # snapsWithOptions = []
        debs = []
        generics = []
        preInstall = []
        postInstall = []
        flatpaks = []

        for i in self.taskList:
            if self.recipes[i]['type'] == 'package':
                packages.extend(self.recipes[i]['recipe'])

            elif self.recipes[i]['type'] == 'flatpak':
                flatpaks.append(self.recipes[i]['recipe'])

            # elif self.recipes[i]['type'] == 'snap':
            # if len(self.recipes[i]['recipe']) == 1:
            # snaps.extend(self.recipes[i]['recipe'])
            # else:
            # snapsWithOptions.append(self.recipes[i]['recipe'])

            elif self.recipes[i]['type'] == 'ppa':
                ppas.append(self.recipes[i]['recipe'][0])
                packages.extend(self.recipes[i]['recipe'][1:])
            elif self.recipes[i]['type'] == 'deb':
                debs.append(self.recipes[i]['recipe'][0])
            elif self.recipes[i]['type'] == 'generic':
                generics.append(self.recipes[i]['recipe'])
            if 'preInstall' in self.recipes[i]:
                preInstall.append(self.recipes[i]['preInstall'])
            if 'postInstall' in self.recipes[i]:
                postInstall.append(self.recipes[i]['postInstall'])

        # Skip already installed ppas
        for i in reversed(range(len(ppas))):
            if ppas[i] in self.repoList:
                ppas.pop(i)

        # Skip already installed packages
        for i in reversed(range(len(packages))):
            if checkPackage(packages[i]):
                packages.pop(i)

        # Create progress bar
        updateBar = Zenity.progressBar(
            pulsating=True,
            noCancel=True,
            title='Arkimint Installer',
            text='Processing tasks')

        try:
            #Ensure git is installed
            if not checkPackage('git'):
                updateBar('Installing git')
                self.runAndLogCmd(
                    ['apt-get', 'install', '-y', 'git'], checkLock=True)

            #Set proxy for git if proxy values found
            # TODO: Test på virtuell
            if checkPackage('git') and proxy_address and proxy_port:
                self.runAndLogCmd([
                    'git', 'config', '--global', 'http.proxy',
                    'http://' + proxy_address + ':' + proxy_port
                ])
                self.runAndLogCmd([
                    'git', 'config', '--global',
                    'url.https://github.com/.insteadOf', 'git://github.com/'
                ])

            # Ensure software-properties-common is installed
            if len(ppas) > 0 and not checkPackage('software-properties-common'):
                updateBar('Installing software-properties-common')
                self.runAndLogCmd(
                    ['apt-get', 'install', '-y', 'software-properties-common'],
                    checkLock=True)

            # Ensure snapd is installed
            # if (len(snaps) > 0 or len(snapsWithOptions) > 0) and not checkPackage('snapd'):
            # updateBar('Installing snapd')
            # self.runAndLogCmd(['apt-get', 'install', '-y', 'snapd'], checkLock=True)

            #Ensure flatpak is installed
            if len(flatpaks) > 0 and not checkPackage('flatpak'):
                updateBar('Installing flatpak')
                self.runAndLogCmd(
                    ['apt-get', 'install', '-y', 'flatpak'], checkLock=True)

            # Ensure libnotify-bin is installed
            if not checkPackage('libnotify-bin'):
                updateBar('Installing libnotify-bin')
                self.runAndLogCmd(
                    ['apt-get', 'install', '-y', 'libnotify-bin'],
                    checkLock=True)

            # Run pre-installation tasks
            if len(preInstall) > 0:
                updateBar('Processing pre-installation tasks')
                for i in preInstall:
                    self.runAndLogCmd(i)

            # Process ppas
            if len(ppas) > 0:
                for ppa in ppas:
                    updateBar('Adding {}'.format(ppa))
                    self.runAndLogCmd(
                        ['add-apt-repository', '-y', ppa], checkLock=True)

            # Update
            if len(packages) > 0 or len(ppas) > 0:
                updateBar('Updating package list')
                self.runAndLogCmd(['apt-get', 'update'], checkLock=True)

            # Process packages
            if len(packages) > 0:
                for package in packages:
                    updateBar('Installing {}'.format(package))
                    cmd = ['apt-get', 'install', '-y']
                    cmd.append(package)
                    self.runAndLogCmd(cmd, checkLock=True)

            #Process flatpaks
            if len(flatpaks) > 0:
                for flatpak in flatpaks:  # Install one by one to avoid hanging
                    updateBar('Installing {}'.format(flatpak))
                    cmd = ['flatpak', 'install', '-y']
                    cmd.extend(flatpak)
                    self.runAndLogCmd(cmd)

            # Process snaps
            # if len(snaps) > 0:
            #     for snap in snaps: # Install one by one to avoid hanging
            #         updateBar('Installing {}'.format(snap))
            #         cmd = ['snap', 'install']
            #         cmd.append(snap)
            #         self.runAndLogCmd(cmd)

            # Process snaps with options
            # if len(snapsWithOptions) > 0:
            #     for snap in snapsWithOptions:
            #         updateBar('Installing {}'.format(snap[0]))
            #         cmd = ['snap', 'install']
            #         cmd.extend(snap)
            #         self.runAndLogCmd(cmd)

            # Process debs
            # WAIT: Legg inn bedre sjekk for wget så ikke kun får ap-feil hvis problemet er med wget
            if len(debs) > 0:
                for deb in debs:
                    updateBar('Installing {}'.format(deb))
                    self.runAndLogCmd(
                        ['wget', '-q', '-O', '/tmp/package.deb', deb])
                    self.runAndLogCmd(
                        ['apt-get', 'install', '-y', '/tmp/package.deb'],
                        checkLock=True)

            # Process generics
            if len(generics) > 0:
                for cmds in generics:
                    updateBar('Running {}'.format(' '.join(cmds)))
                    self.runAndLogCmd(cmds, checkLock=True)

            # Run post-installation tasks
            if len(postInstall) > 0:
                updateBar('Processing post-installation tasks')
                for i in postInstall:
                    self.runAndLogCmd(i)

            # Autoremove
            updateBar('Removing no longer needed packages')
            self.runAndLogCmd(['apt-get', 'autoremove', '-y'], checkLock=True)

            # Check errors and notify
            if len(self.errors) == 0:
                message = "All tasks completed succesfully. If you can't find some of the installed apps, reboot your computer."
            else:
                self.runAndLogCmd(['dpkg', '--configure', '-a'])
                message = 'Some tasks ended with errors and may not have been correctly installed. Check the lock at ' + self.logFile

            notify(message)
            updateBar(message)

            if len(self.errors) > 0:
                log = ''

                with open(self.logFile, 'r') as f:
                    lines = f.readlines()

                    for i in reversed(range(len(lines))):
                        if lines[i].startswith('NEW SESSION'):
                            log = ''.join(lines[i:])
                            break

                Zenity.list(
                    'The following tasks ended with errors and could not be completed:',
                    self.errors)

                if len(log) < 120000:
                    Zenity.textInfo(
                        'Ooops, some errors happened (sorry about that).' + log
                    )
                else:
                    Zenity.textInfo(
                        'Ooops, some errors happened (sorry about that)' +
                        log[:120000]
                    )  # TODO: Se original for å referere log-fil
        finally:
            # Change log ownership
            runCmd([
                'chown', '{}:{}'.format(os.environ['SUDO_USER'],
                                        os.environ['SUDO_USER']), self.logFile
            ])

    def runAndLogCmd(self, cmdArgs, checkLock=False):
        if checkLock:
            if not waitForDpkgLock(
            ):  # Wait for /var/lib/dpkg/lock to be released
                with open(self.logFile, 'a') as f:
                    f.write(100 * '-' + '\n')
                    f.write(
                        'LOCKED /var/lib/dpkg/lock or /var/lib/apt/lists/lock\n'
                    )
                    Zenity.error(
                        'Another program is installing or updating packages. Please wait until this process finishes and then launch Arkimint Installer again.'
                    )
                    sys.exit()

        with open(self.logFile, 'a') as f:
            f.write(100 * '-' + '\n')
            f.write('<COMMAND>: ' + ' '.join(cmdArgs) + '\n')

        cmd = runCmd(cmdArgs)

        with open(self.logFile, 'a') as f:
            if cmd.succeeded:
                f.write('<RESULT>: SUCCESS\n')
            else:
                f.write('<RESULT>: ERROR\n')
                self.errors.append(cmd.cmd)

            f.write('<STDOUT>:\n' + cmd.stdout + '\n')
            f.write('<STDERR>:\n' + cmd.stderr + '\n')

        return cmd


def main():
    if str(Path.home()) == "/root":
        print("Run as user, not as root!")
        sys.exit()

    # Fix desktop file icon
    bindir = os.path.abspath(os.path.dirname(__file__))
    desktop_file = os.path.abspath(
        os.path.join(bindir, '..', 'Arkimint_installer.desktop'))
    icon_file = os.path.abspath(os.path.join(bindir, 'arkimint_fin_32px.png'))
    # TODO: Hvordan ha icon_file som arg til alle zenity def?
    subprocess.run(
        ["sed -i 's:Icon=.*:Icon=" + icon_file + ":g' " + desktop_file + ";"],
        shell=True)

    # Ensure some folders exist:
    ensure_dirs = [
        'bin', 'Projects', '.local/share/applications', '.config/autostart',
        '.local/bin'
    ]
    for dir in ensure_dirs:
        pathlib.Path(str(Path.home()) + '/' + dir).mkdir(
            parents=True, exist_ok=True)

    # Remove som folders we don't need if empty
    del_dirs = [
        'Music', 'Templates', 'Videos', 'Public', 'Public', 'Pictures',
        'Documents'
    ]
    for dir in del_dirs:
        path = pathlib.Path(str(Path.home()) + '/' + dir)
        if os.path.isdir(path) and len(os.listdir(path)) == 0:
            path.rmdir()

    # Fix paths and zenity:
    with open(str(Path.home()) + '/.bashrc', 'r+') as f:
        if not 'PATH=$HOME/bin:$PATH' in f.read():
            f.write('PATH=$HOME/bin:$PATH' + '\n')
        f.seek(0)
        if not 'PATH=$HOME/.local/bin:$PATH' in f.read():
            f.write('PATH=$HOME/.local/bin:$PATH' + '\n')
        f.seek(0)
        if not '''alias zenity="zenity 2> >(grep -v 'GtkDialog' >&2)"''' in f.read(
        ):
            f.write('''alias zenity="zenity 2> >(grep -v 'GtkDialog' >&2)"''' +
                    '\n')

    # Check proxy /fix firefox search provider:
    ff_subfolders = [
        f.path for f in os.scandir(str(Path.home()) + "/.mozilla/firefox")
        if f.is_dir()
    ]
    proxy_address = None
    proxy_port = None
    for folder in ff_subfolders:
        if folder.endswith(".default-release"):
            with open("{}/prefs.js".format(folder), "rb") as p:
                prefs = read_user_prefs(p)
                for k, v in prefs.items():
                    if k == b'network.proxy.http':
                        proxy_address = v
                    if k == b'network.proxy.http_port':
                        proxy_port = str(v)
                    if k == b'browser.urlbar.placeholderName' and v == 'Yahoo!':
                        # TODO: Denne klarte ikke endre search provider på latop på proxy nett
                        search_prov_path = folder + '/search.json.mozlz4'
                        if os.path.exists(search_prov_path):
                            os.remove(search_prov_path)

    if proxy_address and proxy_port:
        svn_folder = str(Path.home()) + '/.subversion'
        pathlib.Path(svn_folder).mkdir(parents=True, exist_ok=True)
        svn_servers = svn_folder + '/servers'
        pathlib.Path(svn_servers).touch()
        with open(svn_servers, 'r+') as f:
            if not 'http-proxy-host' in f.read():
                f.write('http-proxy-host = ' + proxy_address + '\n' \
                        'http-proxy-port = ' + proxy_port)

    # Check root privileges
    if os.geteuid() == 0:
        if proxy_address and proxy_port:
            with open('/etc/environment', 'r+') as f:
                if not 'http_proxy' in f.read():
                    f.write('http_proxy=http://' + proxy_address + ':' + proxy_port + '/' + '\n' \
                            'https_proxy=http://' + proxy_address + ':' + proxy_port + '/' + '\n' \
                            'no_proxy=localhost,127.0.0.0,127.0.1.1,127.0.1.1,local.home')

            with open('/etc/wgetrc', 'r+') as f:
                proxy_set = False
                for line in f.readlines():
                    if line.startswith('http_proxy'):
                        proxy_set = True
                if not proxy_set:
                    f.write('http_proxy=http://' + proxy_address + ':' + proxy_port + '/' + '\n' \
                            'https_proxy=http://' + proxy_address + ':' + proxy_port + '/')

            docker_folder = '/etc/systemd/system/docker.service.d/'
            pathlib.Path(docker_folder).mkdir(parents=True, exist_ok=True)
            docker_conf = docker_folder + '/http-proxy.conf'
            pathlib.Path(docker_conf).touch()
            with open(docker_conf, 'r+') as f:
                if not 'Environment=HTTP_PROXY' in f.read():
                    f.write('Environment=HTTP_PROXY=http://' + proxy_address + ':' + proxy_port + '/' + '\n' \
                            'Environment=HTTPS_PROXY=http://' + proxy_address + ':' + proxy_port + '/' + '\n' \
                            'Environment=NO_PROXY=localhost,127.0.0.1,localaddress,.localdomain.com')

            #self.runAndLogCmd(['git', 'config', '--global', 'http.proxy'])

            #git config --global http.proxy http://85.19.187.24:8080
            #git config --global url.https://github.com/.insteadOf git://github.com/

        #runCmd(['sudo', 'usermod', '-aG', 'vboxsf', '$USER'])
        # TODO: vboxsf gruppe mangler -> gjøre hva først. Sjekk om på virtuell hvordan?
        #runCmd(['sudo', 'usermod', '-aG', 'vboxsf', '$USER'])

        alfred = Alfred()
        alfred.show()
        alfred.process(proxy_address, proxy_port)
    else:
        subprocess.run(
            [
                " \
                cat /etc/lsb-release > /tmp/distro_check; \
                echo $DESKTOP_SESSION >> /tmp/distro_check \
                "
            ],
            shell=True)

        supported = False
        arr = ['Linux Mint 19.2 Tina', 'xfce']
        with open('/tmp/distro_check', 'r+') as f:
            data = f.read()
            if all(x in data for x in arr):
                supported = True

        if supported:
            # Check Zenity and run as superuser
            if checkPackage('zenity'):
                runCmd(
                    ['sudo', 'python3', sys.argv[0]], stdin=Zenity.password())
            else:
                import getpass
                password = getpass.getpass("Password: ")
                current_script = os.path.realpath(__file__)
                subprocess.run(
                    [
                        'echo "{}" | sudo -kS python3 {}'.format(
                            password, current_script)
                    ],
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True)
        else:
            print('Not supported distro')  # WAIT: Make zenity message


if __name__ == '__main__':
    main()
