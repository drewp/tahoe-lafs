
import urllib

from twisted.internet import defer
from nevow import rend, tags as T
from nevow.inevow import IRequest

from allmydata.util import base32
from allmydata.interfaces import IDirectoryNode
from allmydata.web.common import getxmlfile

class MoreInfo(rend.Page):
    addSlash = False
    docFactory = getxmlfile("info.xhtml")

    def abbrev(self, storage_index_or_none):
        if storage_index_or_none:
            return base32.b2a(storage_index_or_none)[:6]
        return "LIT file"

    def get_type(self):
        node = self.original
        si = node.get_storage_index()
        if IDirectoryNode.providedBy(node):
            return "directory"
        if si:
            if node.is_mutable():
                return "mutable file"
            return "immutable file"
        return "LIT file"

    def render_title(self, ctx, data):
        node = self.original
        si = node.get_storage_index()
        t = "More Info for %s" % self.get_type()
        if si:
            t += " (SI=%s)" % self.abbrev(si)
        return ctx.tag[t]

    def render_header(self, ctx, data):
        return self.render_title(ctx, data)

    def render_type(self, ctx, data):
        return ctx.tag[self.get_type()]

    def render_si(self, ctx, data):
        si = self.original.get_storage_index()
        if not si:
            return "None"
        return ctx.tag[base32.b2a(si)]

    def render_size(self, ctx, data):
        node = self.original
        si = node.get_storage_index()
        if IDirectoryNode.providedBy(node):
            d = node._node.get_size_of_best_version()
        elif node.is_mutable():
            d = node.get_size_of_best_version()
        else:
            # for immutable files and LIT files, we get the size from the URI
            d = defer.succeed(node.get_size())
        d.addCallback(lambda size: ctx.tag[size])
        return d

    def render_directory_writecap(self, ctx, data):
        node = self.original
        if node.is_readonly():
            return ""
        if not IDirectoryNode.providedBy(node):
            return ""
        return ctx.tag[node.get_uri()]

    def render_directory_readcap(self, ctx, data):
        node = self.original
        if not IDirectoryNode.providedBy(node):
            return ""
        return ctx.tag[node.get_readonly_uri()]

    def render_directory_verifycap(self, ctx, data):
        node = self.original
        if not IDirectoryNode.providedBy(node):
            return ""
        return ctx.tag[node.get_verifier().to_string()]


    def render_file_writecap(self, ctx, data):
        node = self.original
        if IDirectoryNode.providedBy(node):
            node = node._node
        if node.is_readonly():
            return ""
        return ctx.tag[node.get_uri()]

    def render_file_readcap(self, ctx, data):
        node = self.original
        if IDirectoryNode.providedBy(node):
            node = node._node
        return ctx.tag[node.get_readonly_uri()]

    def render_file_verifycap(self, ctx, data):
        node = self.original
        if IDirectoryNode.providedBy(node):
            node = node._node
        verifier = node.get_verifier()
        if verifier:
            return ctx.tag[node.get_verifier().to_string()]
        return ""

    def get_root(self, ctx):
        req = IRequest(ctx)
        # the addSlash=True gives us one extra (empty) segment
        depth = len(req.prepath) + len(req.postpath) - 1
        link = "/".join([".."] * depth)
        return link

    def render_raw_link(self, ctx, data):
        node = self.original
        if IDirectoryNode.providedBy(node):
            node = node._node
        root = self.get_root(ctx)
        quoted_uri = urllib.quote(node.get_uri())
        text_plain_url = "%s/file/%s/@@named=/raw.txt" % (root, quoted_uri)
        return ctx.tag[text_plain_url]

    def render_is_checkable(self, ctx, data):
        node = self.original
        si = node.get_storage_index()
        if si:
            return ctx.tag
        # don't show checker button for LIT files
        return ""

    def render_check_form(self, ctx, data):
        check = T.form(action=".", method="post",
                       enctype="multipart/form-data")[
            T.fieldset[
            T.input(type="hidden", name="t", value="check"),
            T.input(type="hidden", name="return_to", value="."),
            T.legend(class_="freeform-form-label")["Check on this object"],
            T.div[
            "Verify every bit? (EXPENSIVE):",
            T.input(type="checkbox", name="verify"),
            ],
            T.div["Repair any problems?: ",
                  T.input(type="checkbox", name="repair")],
            T.div["Emit results in JSON format?: ",
                  T.input(type="checkbox", name="output", value="JSON")],

            T.input(type="submit", value="Check"),

            ]]
        return ctx.tag[check]

    def render_is_mutable_file(self, ctx, data):
        node = self.original
        if IDirectoryNode.providedBy(node):
            return ""
        if node.is_mutable() and not node.is_readonly():
            return ctx.tag
        return ""

    def render_overwrite_form(self, ctx, data):
        node = self.original
        root = self.get_root(ctx)
        action = "%s/uri/%s" % (root, urllib.quote(node.get_uri()))
        done_url = "%s/uri/%s?t=info" % (root, urllib.quote(node.get_uri()))
        overwrite = T.form(action=action, method="post",
                           enctype="multipart/form-data")[
            T.fieldset[
            T.input(type="hidden", name="t", value="upload"),
            T.input(type='hidden', name='when_done', value=done_url),
            T.legend(class_="freeform-form-label")["Overwrite"],
            "Upload new contents: ",
            T.input(type="file", name="file"),
            " ",
            T.input(type="submit", value="Replace Contents")
            ]]
        return ctx.tag[overwrite]

    def render_is_directory(self, ctx, data):
        node = self.original
        if IDirectoryNode.providedBy(node):
            return ctx.tag
        return ""

    def render_deep_check_form(self, ctx, data):
        deep_check = T.form(action=".", method="post",
                            enctype="multipart/form-data")[
            T.fieldset[
            T.input(type="hidden", name="t", value="deep-check"),
            T.input(type="hidden", name="return_to", value="."),
            T.legend(class_="freeform-form-label")["Run a deep-check operation (EXPENSIVE)"],
            T.div[
            "Verify every bit? (EVEN MORE EXPENSIVE):",
            T.input(type="checkbox", name="verify"),
            ],
            T.div["Repair any problems?: ",
                  T.input(type="checkbox", name="repair")],
            T.div["Emit results in JSON format?: ",
                  T.input(type="checkbox", name="output", value="JSON")],

            T.input(type="submit", value="Deep-Check"),

            ]]
        return ctx.tag[deep_check]

    def render_deep_size_form(self, ctx, data):
        deep_size = T.form(action=".", method="get",
                            enctype="multipart/form-data")[
            T.fieldset[
            T.input(type="hidden", name="t", value="deep-size"),
            T.legend(class_="freeform-form-label")["Run a deep-size operation (EXPENSIVE)"],
            T.input(type="submit", value="Deep-Size"),
            ]]
        return ctx.tag[deep_size]

    def render_deep_stats_form(self, ctx, data):
        deep_stats = T.form(action=".", method="get",
                            enctype="multipart/form-data")[
            T.fieldset[
            T.input(type="hidden", name="t", value="deep-stats"),
            T.legend(class_="freeform-form-label")["Run a deep-stats operation (EXPENSIVE)"],
            T.input(type="submit", value="Deep-Stats"),
            ]]
        return ctx.tag[deep_stats]

    def render_manifest_form(self, ctx, data):
        manifest = T.form(action=".", method="get",
                            enctype="multipart/form-data")[
            T.fieldset[
            T.input(type="hidden", name="t", value="manifest"),
            T.legend(class_="freeform-form-label")["Run a manifest operation (EXPENSIVE)"],
            T.input(type="submit", value="Manifest"),
            ]]
        return ctx.tag[manifest]


# TODO: edge metadata
