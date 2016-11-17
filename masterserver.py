#!/usr/bin/env python

VERSION = "1.5"
TITLE = "Mount & Blade Masterserver by Caesim [" + VERSION + "]"
CONFIG_FILE = "masterserver.ini"

import os, random, threading

import xml.etree.ElementTree as xmlTree

try:
    import urllib2 as urllib
    from urllib2 import URLError
except ImportError:
    import urllib.request as urllib
    from urllib.error import URLError

try:
    import ConfigParser as configparser
except ImportError:
    import configparser

try:
    import BaseHTTPServer as httpserver
except ImportError:
    import http.server as httpserver

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

try:
    import _winreg
except ImportError:
    pass

def patch_exe(path):
    f = open(path, "rb")
    exe = f.read()
    f.close()

    exe = exe.replace(b"http://warbandmain.taleworlds.com/", 
                      b"http://localhost/\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")

    f = open(path, "wb")
    f.write(exe)
    f.close()


def close(newline=True):
    """
        Closes the program along with the http server thread.
    """
    if newline: print("")
    os._exit(0)

def parse_config(config):
    if 'servers' in config and type(config['servers']) != list:
        config['servers'] = config['servers'].split(";")
        
    if 'keys' in config and type(config['keys']) != dict:
        keys = config['keys'].split(";")
        config['keys'] = {}
        for key in keys:
            if "=" not in key:
                config['keys'][''] = key
            else:
                module, value = key.split("=")
                config['keys'][module] = value

def use_section(config, section, log=False):
    for option in config_file.options(section):
        config[option] = config_file.get(section, option)
        if log: print(option + ": " + config[option])
    parse_config(config)

def urlget(url):
    try:
        request = urllib.Request(url, headers={"User-Agent": config['user_agent']})
        f = urllib.urlopen(request, timeout=float(config['timeout']))
    except URLError:
        return None
    ret = f.read()
    f.close()
    return ret

def has_response(response):
    return response != None and response != ""

config_file = configparser.SafeConfigParser()
config_file.read(CONFIG_FILE)
config_sections = config_file.sections()

config = {}
use_section(config, "default")


def http_server(config):
    class Masterserver(httpserver.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return

        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            output = ""

            uri = urlparse.urlparse(self.path)
            path = uri.path
            args = urlparse.parse_qs(uri.query, True)
            args = {key: (args[key][0] if len(args[key])>=1 else '') for key in args}

            if path.startswith("/handlerservers") and 'type' in args:
                req_type = args['type']
                gametype = "&gametype=" + args['gametype'] if 'gametype' in args else ''

                if req_type == "list":
                    output = "127.0.0.1|127.0.0.1:80"
                    for server in config['servers']:
                        response = urlget("http://" + server + "?type=list" + gametype)
                        if has_response(response):
                            if 'combine_lists' in config and config['combine_lists'] == "1":
                                output += "|" + response
                            else:
                                output = response
                                break
                elif req_type == "confirmping":
                    output = "1"
                elif req_type == "ping":
                    port = "&port=" + args['port'] if 'port' in args else ''
                    for server in config['servers']:
                        response = urlget("http://" + server + "?type=ping" + gametype + port + "&keys")
                        if has_response(response):
                            urlget("http://" + server + "?type=confirmping" + gametype + port + "&rand=" + response)
                        if 'add_to_all_lists' not in config or config['add_to_all_lists'] == "0":
                            break
                    output = "1"
                elif req_type == "chkserial":
                    if 'xid' in config:
                        output = config['xid']
                    elif 'id' in config:
                        output = config['id'] + "|" + config['id']
                    elif 'random_id' in config and config['random_id'] == "1":
                        rand = random.randrange(1000000,9999999)
                        output = str(rand) + "|" + str(rand)
                    elif 'steamfw' in config and config['steamfw'] == "1":
                        response = urlget("http://warbandmain.taleworlds.com/handlerservers.ashx?type=chksteamfw&serial=&ip=" + args['ip'] + gametype)
                        if has_response(response):
                            output = response
                    else:
                        module = args['gametype'] if "gametype" in args and args['gametype'] in config['keys'] else ''

                        try:
                            key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, r"Software\MountAndBladeWarbandKeys")
                            serial = _winreg.QueryValueEx(key, config['keys'][module])[0]
                        except NameError:
                            f = open("/home/%s/.mbwarband/%s" % (config['user'], config['keys'][module]), "r")
                            serial = f.read()
                            f.close()

                        for server in config['servers']:
                            response = urlget("http://" + server + "?type=chkserial&serial=" + serial + "&ip=" + args['ip'] + gametype)
                            if has_response(response):
                                output = response
                                break
                elif req_type == "remove":
                    port = "&port=" + args['port'] if 'port' in args else ''
                    for server in config['servers']:
                        urlget("http://" + server + "?type=remove" + gametype + port)
                        if 'add_to_all_lists' not in config or config['add_to_all_lists'] == "0":
                            break
                    output = "1"

            self.wfile.write(output.encode('ascii') if type(output) == str else output)

    http = httpserver.HTTPServer(('127.0.0.1', int(config['port'])), Masterserver)
    http.serve_forever()

try:
    thread = threading.Thread(target=http_server, args=(config,))
    thread.start()

    print("Server started")

    while True:
        try:
            try:
                cmd = raw_input(">>> ")
            except NameError:
                cmd = input(">>> ")
        except EOFError:
            close()

        if cmd != "":
            if " " in cmd:
                key, value = cmd.split(" ", 1)

                if key == "rm":
                    del config[value]
                    print("Removed", value)
                elif key == "use":
                    if value in config_sections:
                        use_section(config, value, True)
                    else:
                        print("Error: Unknown section")
                else:
                    config[key] = value
                    parse_config(config)
                    print(key + ": " + value)
            else:
                if cmd == "ls":
                    s = ""
                    for key in config:
                        s += key + ": "
                        if type(config[key]) == str:
                            s += config[key]
                        elif type(config[key]) == list:
                            s += "\n"
                            for item in config[key]:
                                s += "    " + item + "\n"
                            s = s[:-1]
                        elif type(config[key]) == dict:
                            s += "\n"
                            for key2 in config[key]:
                                s += "    " + key2 + ": " + config[key][key2] + "\n"
                            s = s[:-1]
                        s += "\n"
                    s = s[:-1]
                    print(s)
                elif cmd == "patch":
                    patch_exe(config['path'])
                elif cmd == "exit" or cmd == "":
                    close(False)
                elif cmd == "help":
                    print("Commands:")
                    print("  help               - shows all commands")
                    print("  <option> <value>   - sets and option to a value")
                    print("  rm <option>        - remove an option")
                    print("  ls                 - view a list of current options")
                    print("  use <section>      - applies contents of a section from ini")
                    print("  patch              - patches the game exe to work with this program")
                    print("  exit               - exit this program")
                    print("")
                    print("Options:")
                    print("  port <number>                - port on which to host the server (only in ini)")
                    print("  timeout <seconds>            - number of seconds before choosing a different masterserver")
                    print("  servers <loc1>[; ...]        - servers to use. if one doesn't work the next one will be used")
                    print("  keys [<module>=]<key>[; ...] - entry in registry where to find the serial key for each module. module defaults to native. native key is used for all modules with no explicit key")
                    print("  combine 1|0                  - combine server list from all masterservers")
                    print("  path <pathToGame>            - path to the game executable for use with the patch command")
                else:
                    print("Error: Unknown command")
except KeyboardInterrupt:
    close()
