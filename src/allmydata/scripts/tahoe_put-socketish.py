#!/usr/bin/env python

import re, socket, sys

SERVERURL_RE=re.compile("http://([^:]*)(:([1-9][0-9]*))?")

def put(serverurl, vdrive, vdrive_fname, local_fname, verbosity):
    """
    @param verbosity: 0, 1, or 2, meaning quiet, verbose, or very verbose

    @return: a Deferred which eventually fires with the exit code
    """
    mo = SERVERURL_RE.match(serverurl)
    if not mo:
        raise ValueError("serverurl is required to look like \"http://HOSTNAMEORADDR:PORT\"")
    host = mo.group(1)
    port = int(mo.group(3))

    url = "/vdrive/" + vdrive + "/"
    if vdrive_fname:
        url += vdrive_fname

    if local_fname is None or local_fname == "-":
        infileobj = sys.stdin
    else:
        infileobj = open(local_fname, "rb")

    so = socket.socket()
    so.connect((host, port,))

    CHUNKSIZE=2**16
    data = "PUT %s HTTP/1.1\r\nHostname: %s\r\n\r\n" % (url, host,)
    while data:
        try:
            sent = so.send(data)
            print "XXXXXXXX I just sent %s" % (data[:sent],)
        except Exception, le:
            print "BOOOOO le: %r" % (le,)
            return -1

        if sent == len(data):
            data = infileobj.read(CHUNKSIZE)
        else:
            data = data[sent:]

    respbuf = []
    data = so.recv(CHUNKSIZE)
    while data:
        print "WHEEEEE okay now we've got some more data: %r" % (data,)
        respbuf.append(data)
        data = so.recv(CHUNKSIZE)

    so.shutdown(socket.SHUT_WR)
    data = so.recv(CHUNKSIZE)
    while data:
        print "WHEEEEE 22222 okay now we've got some more data: %r" % (data,)
        respbuf.append(data)
        data = so.recv(CHUNKSIZE)

def main():
    import optparse
    parser = optparse.OptionParser()
    parser.add_option("-d", "--vdrive", dest="vdrive", default="global")
    parser.add_option("-s", "--server", dest="server", default="http://tahoebs1.allmydata.com:8011")

    (options, args) = parser.parse_args()

    local_file = args[0]
    vdrive_file = None
    if len(args) > 1:
        vdrive_file = args[1]

    put(options.server, options.vdrive, vdrive_file, local_file)

if __name__ == '__main__':
    main()
