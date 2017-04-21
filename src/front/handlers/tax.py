# -*- coding: utf-8 -*-

import random
import time
import zlib
import uuid
import json
import datetime
from twisted.internet import defer
from cyclone import escape, web
from front import storage
from front import utils
from front.utils import E
from front.wiapi import *
from front import D
from front.handlers.base import ApiHandler, ApiJSONEncoder

@handler
class GetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Tax get', '/tax/get/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Tax get")
    def post(self):
        uid = self.uid
        user = yield self.get_user(uid)
        taxmark = yield self.redis.get('taxmark:%s' % uid)
        if not taxmark:
            taxmark = 0
            yield self.redis.set('taxmark:%s' % uid, taxmark)
            if user['batts']:
                #all_batts = [str(D.TAX[one*3]).zfill(6) for one in xrange(0, len(D.TAX)/3)]
                now_batts = filter(lambda j:j in D.BATT, user['batts'].keys())
                now_batts = sorted(now_batts, reverse=True)
                awards = E.earn4tax(int(now_batts[0]))
                cwork = E.tagworks(user, {'TAX': 1})
                if cwork:
                    cuser = dict(works=user['works'])
                    yield self.set_user(uid, **cuser)
                ret = dict(out=dict(awards=awards, works=user['works'], taxmark=taxmark), timestamp=int(time.time()))
            else:
                ret = dict(out=dict(awards={}, taxmark=taxmark), timestamp=int(time.time()))
        else:
            ret = dict(out=dict(taxmark=taxmark), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)






