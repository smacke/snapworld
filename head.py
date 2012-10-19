import BaseHTTPServer
import SocketServer

import os
import simplejson
import sys
import time
import urlparse

import client
import config

class Server(BaseHTTPServer.BaseHTTPRequestHandler):
    
    def do_GET(self):
        #print "GET path", self.path
        parsed_path = urlparse.urlparse(self.path)
        message_parts = [
                'CLIENT VALUES:',
                'client_address=%s (%s)' % (self.client_address,
                                            self.address_string()),
                'command=%s' % self.command,
                'path=%s' % self.path,
                'real path=%s' % parsed_path.path,
                'query=%s' % parsed_path.query,
                'request_version=%s' % self.request_version,
                '',
                'SERVER VALUES:',
                'server_type=%s' % "head server",
                'server_version=%s' % self.server_version,
                'sys_version=%s' % self.sys_version,
                'protocol_version=%s' % self.protocol_version,
                '',
                'HEADERS RECEIVED:',
                ]
        for name, value in sorted(self.headers.items()):
            message_parts.append('%s=%s' % (name, value.rstrip()))
        message_parts.append('')
        message = '\r\n'.join(message_parts)
        #print message

        subpath = self.path.split("/")
        #print subpath

        if self.path == "/start":
            print "starting host servers "

            master = self.config["master"]
            hosts = self.config["hosts"]
            for h in hosts:
                self.StartHostServer(h, master)

        elif self.path == "/quit":
            print "terminating host servers"

            master = self.config["master"]
            hosts = self.config["hosts"]
            for h in hosts:
                self.QuitHostServer(h)

            self.send_response(200)
            self.send_header('Content-Length', 0)
            self.end_headers()

            # set the flag to terminate the server
            self.server.running = False
            self.server.self_dummy()
            return

        elif self.path == "/dummy":
            print "dummy request"

            self.send_response(200)
            self.send_header('Content-Length', 0)
            self.end_headers()
            return

        elif self.path == "/config":
            print "get configuration"

            body = simplejson.dumps(self.config)
            self.send_response(200)
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
            return

        elif subpath[1] == "done":
            self.send_response(200)
            #self.send_header('Last-Modified', self.date_time_string(time.time()))
            self.send_header('Content-Length', 0)
            self.end_headers()

            if len(subpath) > 2:
                host = subpath[2]
                # TODO make this update thread safe, which it is not now
                self.server.done.add(host)
                print "host %s completed work" % (str(self.server.done))
                if len(self.server.done) == len(self.config["hosts"]):

                    print "all hosts completed"
                    #time.sleep(5)

                    # initialize a set of ready servers
                    self.server.ready = set()

                    # send a start message at the beginning
                    if not self.server.start:
                        self.server.start = True
                        (starthost, starttask) = self.GetStartInfo(self.config)
                        s = "send __Start__ message for task %s to host %s" % (
                                starttask, starthost)
                        print s
                        client.message(starthost,"__Main__",starttask,"__Start__")

                    # send a step start command to all the hosts
                    hosts = self.config["hosts"]
                    master = "%s:%s" % (
                        self.config["master"]["host"],
                        self.config["master"]["port"])
                    for h in hosts:
                        print "send prepare to", h
                        self.Prepare(h)
            return

        elif subpath[1] == "ready":
            self.send_response(200)
            #self.send_header('Last-Modified', self.date_time_string(time.time()))
            self.send_header('Content-Length', 0)
            self.end_headers()

            if len(subpath) > 2:
                host = subpath[2]
                # TODO make this update thread safe, which it is not now
                self.server.ready.add(host)
                print "host %s ready" % (str(self.server.ready))
                if len(self.server.ready) == len(self.config["hosts"]):

                    print "all hosts ready"
                    #time.sleep(5)
        
                    # initialize a set of done servers
                    self.server.done = set()

                    # send a step start command to all the hosts
                    hosts = self.config["hosts"]
                    master = "%s:%s" % (
                        self.config["master"]["host"],
                        self.config["master"]["port"])
                    for h in hosts:
                        print "send next step to", h
                        self.StartStep(h)
            return

        self.send_response(200)
        #self.send_header('Last-Modified', self.date_time_string(time.time()))
        self.end_headers()
        self.wfile.write(message)
        return

    def do_POST(self):
        print "POST path", self.path
        # Parse the form data posted
        form = cgi.FieldStorage(
            fp=self.rfile, 
            headers=self.headers,
            environ={'REQUEST_METHOD':'POST',
                     'CONTENT_TYPE':self.headers['Content-Type'],
                     })

        # Begin the response
        self.send_response(200)
        self.end_headers()
        self.wfile.write('Client: %s\n' % str(self.client_address))
        self.wfile.write('User-agent: %s\n' % str(self.headers['user-agent']))
        self.wfile.write('Path: %s\n' % self.path)
        self.wfile.write('Form data:\n')

        # Echo back information about what was posted in the form
        for field in form.keys():
            field_item = form[field]
            if field_item.filename:
                # The field contains an uploaded file
                file_data = field_item.file.read()
                file_len = len(file_data)
                del file_data
                self.wfile.write('\tUploaded %s as "%s" (%d bytes)\n' % \
                        (field, field_item.filename, file_len))
            else:
                # Regular form value
                self.wfile.write('\t%s=%s\n' % (field, form[field].value))
        return

    def StartHostServer(self, remote, master):
        print "starting host server on host %s, port %s" % (
                    remote["host"], remote["port"])

        #cmd = "ssh %s python git/rok/snapworld/host.py -i %s -p %s -m %s:%s" % (
        cmd = "ssh %s python git/rok/snapworld/host.py -d -i %s -p %s -m %s:%s" % (
                    remote["host"], remote["id"], remote["port"],
                    master["host"], master["port"])
        print cmd
        os.system(cmd)

    def GetStartInfo(self, config):
        starttask = "%s-0" % (config["route"]["__Start__"])
        starthost = config["tasks"][starttask]

        hosts = config["hosts"]
        for host in hosts:
            if host["id"] == starthost:
                result = "%s:%s" % (host["host"], host["port"])
                return result, starttask

        return None

    def StartStep(self, host):
        haddr = "%s:%s" % (host["host"], host["port"])
        client.step(haddr)

    def Prepare(self, host):
        haddr = "%s:%s" % (host["host"], host["port"])
        client.prepare(haddr)

    def QuitHostServer(self, host):
        haddr = "%s:%s" % (host["host"], host["port"])
        client.quit(haddr)

class ThreadedHTTPServer(SocketServer.ThreadingMixIn,
                            BaseHTTPServer.HTTPServer):
    """Handle requests in a separate thread."""

    def execute(self):
        while self.running:
            self.handle_request()

        print "exit"
        sys.exit(0)

    def self_dummy(self):
        haddr = "%s:%s" % (self.host, self.port)
        client.dummy(haddr)

if __name__ == '__main__':

    dconf = config.readconfig("snapw.config")
    print dconf

    master = dconf["master"]

    host = master["host"]
    port = int(master["port"])

    server = ThreadedHTTPServer((host, port), Server)
    server.host = host
    server.port = port
    server.done = set()
    server.ready = set()
    server.start = False
    server.running = True

    handler = BaseHTTPServer.BaseHTTPRequestHandler
    handler.config = dconf

    dconf["tasks"] = config.assign(dconf)

    print 'Starting head server on port %d, use <Ctrl-C> to stop' % (port)
    server.execute()

