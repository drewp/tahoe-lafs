# -*- python -*-

"""
Run this tool with twistd in its own directory, with a file named 'urls.txt'
describing which nodes to query. It will request disk-usage numbers from the
nodes once per hour (or slower), and store them in a local database. It will
compute usage-per-unit time values over several time ranges and make them
available through an HTTP query (using ./webport). It will also provide an
estimate of how much time is left before the grid's storage is exhausted.

Each line of urls.txt points to a single node. Each node should have its own
dedicated disk: if multiple nodes share a disk, only list one of them in
urls.txt (otherwise that space will be double-counted, confusing the
results). Each line should be in the form:

 http://host:webport/statistics?t=json

"""

# TODO:
#  built-in graphs on web interface


import os.path, pprint, time, urllib
from datetime import timedelta
from twisted.application import internet, service, strports
from twisted.web import server, resource, http
from twisted.python import log
import simplejson
from axiom.attributes import AND
from axiom.store import Store
from epsilon import extime
from diskwatcher import Sample

#from axiom.item import Item
#from axiom.attributes import text, integer, timestamp

#class Sample(Item):
#    url = text()
#    when = timestamp()
#    used = integer()
#    avail = integer()

#s = Store("history.axiom")
#ns = Store("new-history.axiom")
#for sa in s.query(Sample):
#    diskwatcher.Sample(store=ns,
#                       url=sa.url, when=sa.when, used=sa.used, avail=sa.avail)
#print "done"

HOUR = 3600
DAY = 24*3600
WEEK = 7*DAY
MONTH = 30*DAY
YEAR = 365*DAY

class DiskWatcher(service.MultiService, resource.Resource):
    POLL_INTERVAL = 60#1*HOUR
    AVERAGES = {"60s": 60,
                "5m": 5*60,
                "30m": 30*60,
                "1hr": 1*HOUR,
                "1day": 1*DAY,
                "2wk": 2*WEEK,
                "4wk": 4*WEEK,
                }

    def __init__(self):
        assert os.path.exists("diskwatcher.tac") # run from the right directory
        service.MultiService.__init__(self)
        resource.Resource.__init__(self)
        self.store = Store("history.axiom")
        ts = internet.TimerService(self.POLL_INTERVAL, self.poll)
        ts.setServiceParent(self)

    def startService(self):
        service.MultiService.startService(self)

        try:
            desired_webport = open("webport", "r").read().strip()
        except EnvironmentError:
            desired_webport = None
        webport = desired_webport or "tcp:0"
        root = self
        serv = strports.service(webport, server.Site(root))
        serv.setServiceParent(self)
        if not desired_webport:
            got_port = serv._port.getHost().port
            open("webport", "w").write("tcp:%d\n" % got_port)


    def get_urls(self):
        for url in open("urls.txt","r").readlines():
            if "#" in url:
                url = url[:url.find("#")]
            url = url.strip()
            if not url:
                continue
            yield url

    def poll(self):
        log.msg("polling..")
        attempts = 0
        fetched = 0
        for url in self.get_urls():
            attempts += 1
            try:
                when = extime.Time()
                data = simplejson.load(urllib.urlopen(url))
                total = data[u"stats"][u"storage_server.disk_total"]
                used = data[u"stats"][u"storage_server.disk_used"]
                avail = data[u"stats"][u"storage_server.disk_avail"]
                #print "%s : total=%s, used=%s, avail=%s" % (url,
                #                                            total, used, avail)
                s = Sample(store=self.store,
                           url=unicode(url), when=when, used=used, avail=avail)
                fetched += 1
            except:
                log.msg("error while fetching: %s" % url)
                log.err()
        log.msg("fetched %d of %d" % (fetched, attempts))

    def calculate(self):
        timespans = []
        total_avail_space = self.find_total_avail_space()
        pairs = [ (timespan,name)
                  for name,timespan in self.AVERAGES.items() ]
        pairs.sort()
        for (timespan,name) in pairs:
            growth = self.growth(timespan)
            print name, total_avail_space, growth
            if growth is not None:
                try:
                    timeleft = total_avail_space / growth
                except ZeroDivisionError:
                    timeleft = None
                timespans.append( (name, timespan, growth, timeleft) )
        return timespans

    def find_total_avail_space(self):
        # this returns the sum of disk-avail stats for all servers that 1)
        # are listed in urls.txt and 2) have responded recently.
        now = extime.Time()
        recent = now - timedelta(seconds=2*self.POLL_INTERVAL)
        total_avail_space = 0
        for url in self.get_urls():
            url = unicode(url)
            latest = list(self.store.query(Sample,
                                           AND(Sample.url == url,
                                               Sample.when > recent),
                                           sort=Sample.when.descending,
                                           limit=1))
            if latest:
                total_avail_space += latest[0].avail
        return total_avail_space


    def growth(self, timespan):
        """Calculate the bytes-per-second growth of the total disk-used stat,
        over a period of TIMESPAN seconds (i.e. between the most recent
        sample and the latest one that's at least TIMESPAN seconds ago),
        summed over all nodes which 1) are listed in urls.txt, 2) have
        responded recently, and 3) have a response at least as old as
        TIMESPAN. If there are no nodes which meet these criteria, we'll
        return None; this is likely to happen for the longer timespans (4wk)
        until the gatherer has been running and collecting data for that
        long."""

        td = timedelta(seconds=timespan)
        now = extime.Time()
        then = now - td
        recent = now - timedelta(seconds=2*self.POLL_INTERVAL)

        total_growth = 0.0
        num_nodes = 0

        for url in self.get_urls():
            url = unicode(url)
            latest = list(self.store.query(Sample,
                                           AND(Sample.url == url,
                                               Sample.when > recent),
                                           sort=Sample.when.descending,
                                           limit=1))
            if not latest:
                #print "no latest sample from", url
                continue # skip this node
            latest = latest[0]
            old = list(self.store.query(Sample,
                                        AND(Sample.url == url,
                                            Sample.when < then),
                                        sort=Sample.when.descending,
                                        limit=1))
            if not old:
                #print "no old sample from", url
                continue # skip this node
            old = old[0]
            duration = latest.when.asPOSIXTimestamp() - old.when.asPOSIXTimestamp()
            if not duration:
                print "only one sample from", url
                continue

            rate = float(latest.used - old.used) / duration
            #print url, rate
            total_growth += rate
            num_nodes += 1

        if not num_nodes:
            return None
        return total_growth

    def getChild(self, path, req):
        if path == "":
            return self
        return resource.Resource.getChild(self, path, req)

    def abbreviate_time(self, s):
        def _plural(count, unit):
            count = int(count)
            if count == 1:
                return "%d %s" % (count, unit)
            return "%d %ss" % (count, unit)
        if s is None:
            return "unknown"
        if s < 120:
            return _plural(s, "second")
        if s < 3*HOUR:
            return _plural(s/60, "minute")
        if s < 2*DAY:
            return _plural(s/HOUR, "hour")
        if s < 2*MONTH:
            return _plural(s/DAY, "day")
        if s < 4*YEAR:
            return _plural(s/MONTH, "month")
        return _plural(s/YEAR, "year")

    def render(self, req):
        t = req.args.get("t", ["html"])[0]
        ctype = "text/plain"
        data = ""
        if t == "html":
            data = ""
            for (name, timespan, growth, timeleft) in self.calculate():
                data += "%f bytes per second, %s remaining (over %s)\n" % \
                        (growth, self.abbreviate_time(timeleft), name)
        elif t == "json":
            current = self.calculate()
            #data = str(current) + "\n" # isn't that convenient? almost.
            data = simplejson.dumps(current, indent=True)
        else:
            req.setResponseCode(http.BAD_REQUEST)
            data = "Unknown t= %s\n" % t
        req.setHeader("content-type", ctype)
        return data

application = service.Application("disk-watcher")
DiskWatcher().setServiceParent(application)
