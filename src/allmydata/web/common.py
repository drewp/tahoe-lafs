
from twisted.web import http, server
from zope.interface import Interface
from nevow import loaders, appserver
from nevow.inevow import IRequest
from nevow.util import resource_filename
from allmydata.interfaces import ExistingChildError, NoSuchChildError, \
     FileTooLargeError, NotEnoughSharesError

class IOpHandleTable(Interface):
    pass

def getxmlfile(name):
    return loaders.xmlfile(resource_filename('allmydata.web', '%s' % name))

def boolean_of_arg(arg):
    # TODO: ""
    assert arg.lower() in ("true", "t", "1", "false", "f", "0", "on", "off")
    return arg.lower() in ("true", "t", "1", "on")

def get_root(ctx_or_req):
    req = IRequest(ctx_or_req)
    # the addSlash=True gives us one extra (empty) segment
    depth = len(req.prepath) + len(req.postpath) - 1
    link = "/".join([".."] * depth)
    return link

def get_arg(ctx_or_req, argname, default=None, multiple=False):
    """Extract an argument from either the query args (req.args) or the form
    body fields (req.fields). If multiple=False, this returns a single value
    (or the default, which defaults to None), and the query args take
    precedence. If multiple=True, this returns a tuple of arguments (possibly
    empty), starting with all those in the query args.
    """
    req = IRequest(ctx_or_req)
    results = []
    if argname in req.args:
        results.extend(req.args[argname])
    if req.fields and argname in req.fields:
        results.append(req.fields[argname].value)
    if multiple:
        return tuple(results)
    if results:
        return results[0]
    return default

def abbreviate_time(data):
    # 1.23s, 790ms, 132us
    if data is None:
        return ""
    s = float(data)
    if s >= 1.0:
        return "%.2fs" % s
    if s >= 0.01:
        return "%dms" % (1000*s)
    if s >= 0.001:
        return "%.1fms" % (1000*s)
    return "%dus" % (1000000*s)

def abbreviate_rate(data):
    # 21.8kBps, 554.4kBps 4.37MBps
    if data is None:
        return ""
    r = float(data)
    if r > 1000000:
        return "%1.2fMBps" % (r/1000000)
    if r > 1000:
        return "%.1fkBps" % (r/1000)
    return "%dBps" % r

def abbreviate_size(data):
    # 21.8kB, 554.4kB 4.37MB
    if data is None:
        return ""
    r = float(data)
    if r > 1000000000:
        return "%1.2fGB" % (r/1000000000)
    if r > 1000000:
        return "%1.2fMB" % (r/1000000)
    if r > 1000:
        return "%.1fkB" % (r/1000)
    return "%dB" % r

def text_plain(text, ctx):
    req = IRequest(ctx)
    req.setHeader("content-type", "text/plain")
    req.setHeader("content-length", len(text))
    return text

class WebError(Exception):
    def __init__(self, text, code=http.BAD_REQUEST):
        self.text = text
        self.code = code

# XXX: to make UnsupportedMethod return 501 NOT_IMPLEMENTED instead of 500
# Internal Server Error, we either need to do that ICanHandleException trick,
# or make sure that childFactory returns a WebErrorResource (and never an
# actual exception). The latter is growing increasingly annoying.

def should_create_intermediate_directories(req):
    t = get_arg(req, "t", "").strip()
    return bool(req.method in ("PUT", "POST") and
                t not in ("delete", "rename", "rename-form", "check"))


class MyExceptionHandler(appserver.DefaultExceptionHandler):
    def simple(self, ctx, text, code=http.BAD_REQUEST):
        req = IRequest(ctx)
        req.setResponseCode(code)
        req.setHeader("content-type", "text/plain;charset=utf-8")
        if isinstance(text, unicode):
            text = text.encode("utf-8")
        req.write(text)
        # TODO: consider putting the requested URL here
        req.finishRequest(False)

    def renderHTTP_exception(self, ctx, f):
        if f.check(ExistingChildError):
            return self.simple(ctx,
                               "There was already a child by that "
                               "name, and you asked me to not "
                               "replace it.",
                               http.CONFLICT)
        elif f.check(NoSuchChildError):
            name = f.value.args[0]
            return self.simple(ctx,
                               "No such child: %s" % name.encode("utf-8"),
                               http.NOT_FOUND)
        elif f.check(NotEnoughSharesError):
            return self.simple(ctx, str(f), http.GONE)
        elif f.check(WebError):
            return self.simple(ctx, f.value.text, f.value.code)
        elif f.check(FileTooLargeError):
            return self.simple(ctx, str(f.value), http.REQUEST_ENTITY_TOO_LARGE)
        elif f.check(server.UnsupportedMethod):
            # twisted.web.server.Request.render() has support for transforming
            # this into an appropriate 501 NOT_IMPLEMENTED or 405 NOT_ALLOWED
            # return code, but nevow does not.
            req = IRequest(ctx)
            method = req.method
            return self.simple(ctx,
                               "I don't know how to treat a %s request." % method,
                               http.NOT_IMPLEMENTED)
        super = appserver.DefaultExceptionHandler
        return super.renderHTTP_exception(self, ctx, f)

class NeedOperationHandleError(WebError):
    pass

class RenderMixin:

    def renderHTTP(self, ctx):
        request = IRequest(ctx)

        # if we were using regular twisted.web Resources (and the regular
        # twisted.web.server.Request object) then we could implement
        # render_PUT and render_GET. But Nevow's request handler
        # (NevowRequest.gotPageContext) goes directly to renderHTTP. Copy
        # some code from the Resource.render method that Nevow bypasses, to
        # do the same thing.
        m = getattr(self, 'render_' + request.method, None)
        if not m:
            from twisted.web.server import UnsupportedMethod
            raise UnsupportedMethod(getattr(self, 'allowedMethods', ()))
        return m(ctx)
