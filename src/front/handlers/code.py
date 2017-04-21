# -*- coding: utf-8 -*-

import time
import zlib
import random
import string
from twisted.internet import defer
from cyclone import escape, web
from front import storage
from front.utils import E
from front.wiapi import *
from twisted.python import log
from front import utils
from front.handlers.base import ApiHandler, ApiJSONEncoder
from local_settings import ZONE_ID

@handler
class SetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @utils.signed
    @api('Code', '/code/', [
        Param('channel', False, str, 'putaogame', 'putaogame', 'channel'),
        Param('cdkey', False, str, '8v3bho1t', '8v3bho1t', 'cdkey'),
        Param('_sign', True, str, 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', 'gGRwMApTJ3VpZCcKcDEKUyc5JwpwMgpzLK', '_sign'),
        ], filters=[ps_filter], description="Code set")
    def post(self):
        try:
            cdkey = self.get_argument("cdkey")
            channel = self.get_argument("channel")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        uid = self.uid
        user = yield self.get_user(uid)
        channels = yield self.sql.runQuery("SELECT id FROM core_channel WHERE slug=%s LIMIT 1", (channel, ))
        if channels:
            channel, = channels[0]
        else:
            raise web.HTTPError(404)

        res = yield self.psql.runQuery("SELECT * FROM core_usercode WHERE user_id=%s AND code=%s AND zone_id=%s LIMIT 1", (uid, cdkey, ZONE_ID))
        if res:
            self.write(dict(err=E.ERR_CODE_ALREADYGOT, msg=E.errmsg(E.ERR_CODE_ALREADYGOT)))
            return
        codes = yield self.psql.runQuery("SELECT created_at, ended_at, gold, rock, feat, hp, prods, nums FROM core_code AS a,\
                                          core_code_channels AS b WHERE code=%s AND b.channel_id=%s AND a.id=b.code_id LIMIT 1",\
                                         (cdkey, channel))
        if codes:
            created_at, ended_at, gold, rock, feat, hp, prods, nums = codes[0]
            created_at = int(time.mktime(created_at.timetuple()))
            ended_at = int(time.mktime(ended_at.timetuple()))
            if ended_at >= int(time.time()) and created_at <= int(time.time()):
                pass
            else:
                self.write(dict(err=E.ERR_CODE_TIMEOUT, msg=E.errmsg(E.ERR_CODE_TIMEOUT)))
                return

            query = "INSERT INTO core_usercode(user_id, code, zone_id, channel_id, timestamp) VALUES (%s, %s, %s, %s, %s) RETURNING id"
            params = (uid, cdkey, ZONE_ID, channel, int(time.time()))
            try:
                res = yield self.psql.runQuery(query, params)

            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                self.write(dict(err=E.ERR_CODE_NOTFOUND, msg=E.errmsg(E.ERR_CODE_NOTFOUND)))
                return
        else:
            res = yield self.sql.runQuery("SELECT classify FROM core_code WHERE code=%s LIMIT 1", (cdkey, ))
            if res:
                classify, = res[0]
                res = yield self.sql.runQuery("SELECT 1 FROM core_code WHERE classify=%s AND user_id=%s", (classify, uid))
                if res:
                    self.write(dict(err=E.ERR_CODE_REPEAT, msg=E.errmsg(E.ERR_CODE_REPEAT)))
                    return
            else:
                self.write(dict(err=E.ERR_CODE_NOTFOUND, msg=E.errmsg(E.ERR_CODE_NOTFOUND)))
                return
            res = yield self.sql.runQuery("SELECT id, type, valided_at, created_at, gold, rock, feat, hp, prods, "
                                          "nums, classify FROM core_code WHERE code=%s LIMIT 1", (cdkey, ))
            if res:
                code_id, ctype, valided_at, created_at, gold, rock, feat, hp, prods, nums, classify = res[0]
                if ctype == E.used:
                    self.write(dict(err=E.ERR_CODE_ALREADYGOT, msg=E.errmsg(E.ERR_CODE_ALREADYGOT)))
                    return
                if valided_at >= int(time.time()) and created_at <= int(time.time()):
                    pass
                else:
                    self.write(dict(err=E.ERR_CODE_TIMEOUT, msg=E.errmsg(E.ERR_CODE_TIMEOUT)))
                    return
                yield self.set_code(user, cdkey)

        if prods:
            prods = dict(zip(prods.split(','), [int(n) for n in nums.split(',')]))
        else:
            prods = {}
        user['gold'] += gold
        user['rock'] += rock
        user['feat'] += feat
        cost = hp
        hp, tick = yield self.add_hp(user, hp, u'兑换码奖励')
        hp, tick = yield self.get_hp(user)
        for prod, n in prods.items():
            if prod in user['prods']:
                user['prods'][prod] += n
            else:
                user['prods'][prod] = n
            if user['prods'][prod] > 999:
                user['prods'][prod] = 999
            elif user['prods'][prod] == 0:
                del user['prods'][prod]
            else:pass
        awards = dict(gold=gold, rock=rock, hp=hp, feat=feat, prods=prods)
        cuser = dict(gold=user['gold'], rock=user['rock'], feat=user['feat'], prods=user['prods'])
        nuser = dict(gold=user['gold'], rock=user['rock'], hp=hp, feat=user['feat'], prods=user['prods'])
        logmsg = u'兑换码:兑换%s' % cdkey
        yield self.set_user(uid, logmsg, **cuser)
        ret = dict(out=dict(user=nuser, awards=awards), timestamp=int(time.time()))
        reb = zlib.compress(escape.json_encode(ret))
        self.write(ret)


@handler
class GenerateHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Generate code', '/gen/', [
        Param('created_date', True, str, '2015-9-17-5', '2015-9-17-5', u'开始时间'),
        Param('valided_date', True, str, '2015-9-30-5', '2015-9-30-5', u'失效时间'),
        Param('classify', True, str, '0', '0', u'兑换码类别'),
        Param('gold', True, int, 10, 10, 'gold'),
        Param('rock', True, int, 10, 10, 'rock'),
        Param('feat', True, int, 10, 10, 'feat'),
        Param('hp', True, int, 10, 10, 'hp'),
        Param('prods', True, str, '04001,04002', '04001,04002', 'prods'),
        Param('nums', True, str, '1,2', '1,2', 'nums'),
        Param('total', True, int, 10, 10, u'生成数量'),
        ], filters=[ps_filter], description="Generate code")
    def get(self):
        try:
            created_date = self.get_argument("created_date")
            valided_date = self.get_argument("valided_date")
            classify = self.get_argument("classify")
            gold = self.get_argument("gold")
            rock = self.get_argument("rock")
            feat = self.get_argument("feat")
            hp = self.get_argument("hp")
            prods = self.get_argument("prods")
            nums = self.get_argument("nums")
            total = self.get_argument("total")
        except Exception:
            raise web.HTTPError(400, "Argument error")

        created_date = int(time.mktime(time.strptime(created_date, "%Y-%m-%d-%H")))
        valided_date = int(time.mktime(time.strptime(valided_date, "%Y-%m-%d-%H")))
        code_list = []
        for one in xrange(0, int(total)):
            while True:
                field = string.lowercase + string.digits
                code = "".join(random.sample(field, 8))
                res = yield self.sql.runQuery("SELECT * FROM core_code WHERE code=%s LIMIT 1", (code, ))
                if res:
                    continue
                else:
                    query = "INSERT INTO core_code(code, type, valided_at, created_at, gold, rock, feat, hp, prods,\
                     nums, user_id, classify) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
                    params = (code, E.unused, valided_date, created_date, gold, rock, feat, hp, prods, nums, None, classify)
                    for i in range(5):
                        try:
                            rid = yield self.sql.runQuery(query, params)
                            break
                        except storage.IntegrityError:
                            log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                            continue
                    code_list.append(code)
                    break
        self.write(code_list)

