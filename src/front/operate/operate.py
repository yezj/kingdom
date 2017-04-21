import time
import zlib
from twisted.internet import defer
from cyclone import escape, web
from front import storage
from front import utils
from front.utils import E
#from front.handlers.base import BaseHandler
from front.wiapi import *
from front.handlers.base import ApiHandler, ApiJSONEncoder

@handler
class AccountHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Operate account', '/operate/account/', [
        Param('bid', True, str, 1.11, 1.11, 'before id'),
        Param('nid', True, str, 2.10, 2.10, 'now id'),
        ], filters=[ps_filter], description="Operate account")
    def get(self):
        bid = self.get_argument('bid', None)
        if bid:
            bid = bid.split('.')[0]
        nid = self.get_argument('nid', None)
        if nid:
            nid = nid.split('.')[0]
        res = yield self.sql.runQuery("SELECT authstring FROM core_account WHERE user_id=%s OR user_id=%s", (bid, nid))
        baccount = res[0][0]
        naccount = res[1][0]
        if baccount and naccount:
            yield self.sql.runQuery("UPDATE core_account SET authstring=%s WHERE user_id=%s RETURNING id", (baccount, nid))
            yield self.sql.runQuery("UPDATE core_account SET authstring=%s WHERE user_id=%s RETURNING id", (naccount, bid))
            self.write("SUCCESS")
        else:
            raise web.HTTPError(400, "Argument error")
