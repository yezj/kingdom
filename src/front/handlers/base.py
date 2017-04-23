# -*- coding: utf-8 -*-

import base64
import pickle
import time
import uuid
import json
import datetime
import random
import decimal
from itertools import *
from cyclone import web, escape
from django.db.models.query import QuerySet
from django.core.serializers.json import DjangoJSONEncoder
from twisted.internet import defer
from twisted.python import log
from front import storage, D
from front.utils import E
#from M2Crypto import RSA, BIO, EVP
from local_settings import ZONE_ID


class BaseHandler(web.RequestHandler, storage.DatabaseMixin):
    def get_current_user(self):
        return None

    # def generate_token(self, **kwargs):
    #     token = base64.urlsafe_b64encode(pickle.dumps(kwargs))
    #     return token

    @storage.databaseSafe
    @defer.inlineCallbacks
    def generate_sign(self, idcard, zone):
        firstsign = False
        ahex, aid = idcard.split('h', 1)
        res = yield self.sql.runQuery("SELECT state, user_id FROM core_account WHERE accountid=%s AND hex=%s LIMIT 1",
                                      (aid, ahex))
        if not res:
            raise E.USERNOTFOUND
        state, uid = res[0]
        if not uid and state == 0:
            firstsign = True
            uid = yield self.create_user()
            query = "UPDATE core_account SET user_id=%s, accountid=%s WHERE id=%s"
            params = (uid, str(aid), aid)
            for i in range(5):
                try:
                    yield self.sql.runOperation(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        if state != 0:
            if state == 2:
                raise E.USERABNORMAL
            elif state == 3:
                raise E.USERBEBANKED
            else:
                raise E.UNKNOWNERROR
        token = dict(uid=str(uid))
        s = base64.urlsafe_b64encode(pickle.dumps(token)).rstrip('=')
        sign = s[-1] + s[1:-1] + s[0]

        yield self.predis.lpush('all:log:sign', pickle.dumps([int(time.time()), ZONE_ID, uid, aid, firstsign, state]))
        defer.returnValue(sign)

    def ping_server(self):
        return dict(domain=self.settings['domain'], notice='')

    @storage.databaseSafe
    @defer.inlineCallbacks
    def bind_token(self, idcard, authstring):
        ahex, aid = idcard.split('h', 1)
        res = yield self.sql.runQuery(
            "SELECT state, user_id FROM core_account WHERE id=%s AND hex=%s AND authstring=%s LIMIT 1",
            (aid, ahex, authstring))
        if res:
            IS_BINDED = True
        else:
            query = "UPDATE core_account SET authstring=%s, timestamp=%s WHERE id=%s AND hex=%s RETURNING id"
            params = (authstring, int(time.time()), aid, ahex)
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
            IS_BINDED = False

        defer.returnValue(IS_BINDED)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def refresh_idcard(self, idcard, model, serial, channel, access_token):
        if idcard:
            ahex, aid = idcard.split('h', 1)
            query = "UPDATE core_account SET model=%s, serial=%s, timestamp=%s WHERE id=%s AND hex=%s RETURNING id"
            params = (model, serial, int(time.time()), aid, ahex)
            for i in range(5):
                try:
                    res = yield self.sql.runQuery(query, params)
                    if not res:
                        idcard = None
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        if not idcard:
            res = yield self.sql.runQuery("SELECT hex, id FROM core_account WHERE authstring=%s LIMIT 1",
                                          (access_token,))
            if res:
                ahex, aid = res[0]
                idcard = '%sh%s' % (ahex, aid)
            else:
                ahex = uuid.uuid4().hex
                query = "INSERT INTO core_account(hex, state, user_id, model, serial, authmode, authstring, channel_id,\
                 created, timestamp, accountid) VALUES (%s, 0, NULL, %s, %s, '', %s, %s, %s, %s, '') RETURNING id"
                params = (ahex, model, serial, access_token, channel, int(time.time()), int(time.time()))
                for i in range(5):
                    try:
                        res = yield self.sql.runQuery(query, params)
                        aid = res[0][0]
                        idcard = '%sh%s' % (ahex, aid)
                        break
                    except storage.IntegrityError:
                        log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                        continue
        defer.returnValue(idcard)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_nickname(self):
        for i in xrange(10, len(D.PREFIX) + 10, 10):
            randname = [(one[0] + one[1]).decode('utf-8') for one in product(D.PREFIX[:i], D.POSTFIX[:i])]
            res = yield self.sql.runQuery("SELECT nickname FROM core_user")
            usedname = [r[0] for r in res]
            nickname = list(set(randname) - set(usedname))
            random.shuffle(nickname)
            if len(nickname) >= 100:
                nickname = nickname[:100]
                break
            else:
                continue
        defer.returnValue(nickname)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def create_user(self):
        nuser = E.initdata4user()
        query = "INSERT INTO core_user(secret, name, nickname, avat, xp, gold, rock, feat, book, vrock, jextra, " \
                "jheros, jprods, jbatts, jseals, jtasks, jworks, jmails, jdoors, jbeautys, jactivities, jrecharge, jinsts, timestamp) VALUES " \
                "(%(secret)s, %(name)s, %(nickname)s, %(avat)s, %(xp)s, %(gold)s, %(rock)s, %(feat)s, %(book)s, %(vrock)s, %(jextra)s, " \
                "%(jheros)s, %(jprods)s, %(jbatts)s, %(jseals)s, %(jtasks)s, %(jworks)s, %(jmails)s, %(jdoors)s, %(jbeautys)s, %(jactivities)s, " \
                "%(jrecharge)s, %(jinsts)s, %(timestamp)s) RETURNING id"
        params = nuser
        params['name'] = str(uuid.uuid4().hex)[:20]
        params['secret'] = str(uuid.uuid4().hex)[:20]
        for i in range(5):
            try:
                res = yield self.sql.runQuery(query, params)
                uid, = res[0]
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        for lot in D.LOTT.keys():
            query = "INSERT INTO core_freelott(user_id, lotttype, times, timestamp, free) VALUES (%s, %s, %s, %s, %s) RETURNING id"
            params = (uid, lot, 0, int(time.time()), True)
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue

        # query = "INSERT INTO core_arena(user_id, arena_coin, before_rank, now_rank, last_rank, jguards, jpositions, formation, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
        # params = (uid, 0, uid, uid, uid, nuser['jheros'], D.USERARENA['jpositions'], E.default_formation, int(time.time()))
        #
        # for i in range(5):
        #     try:
        #         yield self.sql.runQuery(query, params)
        #         break
        #     except storage.IntegrityError:
        #         log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
        #         continue

        query = "INSERT INTO core_hunt(user_id, jguards, formation, timestamp) VALUES (%s, %s, %s, %s) RETURNING id"
        params = (uid, nuser['jheros'], E.default_formation, int(time.time()))
        for i in range(5):
            try:
                yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue

        mail = D.TRIOMAIL
        yield self.send_mails(mail['sender'], uid, mail['title'], mail['content'], mail['jawards'])
        yield self.set_arena(uid)
        yield self.redis.set('arenatimes:%s' % uid, 0)
        yield self.redis.set('arenatime:%s' % uid, int(time.time()))
        defer.returnValue(uid)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_notice(self):
        notice_dict = {}
        notices = yield self.sql.runQuery("SELECT notice_id, position FROM core_noticeship")
        if notices:
            for n in notices:
                res = yield self.sql.runQuery(
                    "SELECT id, title, content, screenshot, sign, created_at, ended_at, url FROM core_notice WHERE id=%s",
                    (n[0],))
                nid, title, content, screenshot, sign, created_at, ended_at, url = res[0]
                if screenshot and FileObject(screenshot).exists():
                    url = FileObject(screenshot).url
                else:
                    url = url
                    # created_at, ended_at = res[0]
                created_at = int(time.mktime(created_at.timetuple()))
                ended_at = int(time.mktime(ended_at.timetuple()))
                now = int(time.mktime(datetime.datetime.now().timetuple()))
                if now >= created_at and now <= ended_at:
                    notice_dict[nid] = dict(title=title, content=content, url=url, sign=sign, create_at=created_at,
                                            ended_at=ended_at, position=n[1])

        defer.returnValue(notice_dict)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_user(self, uid):
        user = yield self.get_cache("user:%s" % uid)
        if not user:
            res = yield self.sql.runQuery("SELECT name, nickname, avat, xp, gold, rock, feat, book, jextra, jheros, jprods,\
             jbatts, jseals, jtasks, jworks, jmails, jdoors, vrock, jbeautys, jactivities, jrecharge, jinsts FROM core_user WHERE id=%s LIMIT 1",
                                          (uid,))
            if not res:
                user = None
            else:
                r = res[0]
                try:
                    user = dict(uid=uid, name=r[0], nickname=r[1], avat=r[2], xp=r[3], gold=r[4], rock=r[5], feat=r[6],
                                book=r[7], vrock=r[17])
                    user['extra'] = r[8] and escape.json_decode(r[8]) or {}
                    user['heros'] = r[9] and escape.json_decode(r[9]) or {}
                    user['prods'] = r[10] and escape.json_decode(r[10]) or {}
                    user['batts'] = r[11] and escape.json_decode(r[11]) or {}
                    user['seals'] = r[12] and escape.json_decode(r[12]) or {}
                    user['tasks'] = r[13] and escape.json_decode(r[13]) or {}
                    user['works'] = r[14] and escape.json_decode(r[14]) or {}
                    user['mails'] = r[15] and escape.json_decode(r[15]) or {}
                    user['doors'] = r[16] and escape.json_decode(r[16]) or {}
                    user['beautys'] = r[18] and escape.json_decode(r[18]) or {}
                    user['activities'] = r[19] and escape.json_decode(r[19]) or {}
                    user['recharge'] = r[20] and escape.json_decode(r[20]) or {}
                    user['insts'] = r[21] and escape.json_decode(r[21]) or {}
                    res = yield self.sql.runQuery(
                        "SELECT user_id FROM core_firstlott WHERE user_id=%s AND first=True AND lotttype=%s LIMIT 1",
                        (uid, E.lott_by_rock))
                    if res:
                        firstlott = 1
                    else:
                        firstlott = 0
                    user['first_by_rock'] = firstlott
                    yield self.set_cache("user:%s" % uid, user)
                except Exception:
                    user = None
        defer.returnValue(user)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_user(self, uid, reason=None, name=None, nickname=None, avat=None, xp=None, gold=None, rock=None, feat=None,
                 book=None, extra=None, \
                 heros=None, prods=None, batts=None, seals=None, tasks=None, works=None, mails=None, doors=None,
                 vrock=None, beautys=None, \
                 activities=None, recharge=None, insts=None):
        olduser = yield self.get_user(uid)
        suser = {'uid': uid}
        subqueries = []
        if name is not None:
            suser['name'] = name
            subqueries.append("name=%(name)s")
        if nickname is not None:
            suser['nickname'] = nickname
            subqueries.append("nickname=%(nickname)s")
        if avat is not None:
            suser['avat'] = avat
            subqueries.append("avat=%(avat)s")
        if xp is not None:
            suser['xp'] = xp
            subqueries.append("xp=%(xp)s")
        if gold is not None:
            suser['gold'] = gold
            subqueries.append("gold=%(gold)s")
        if rock is not None:
            suser['rock'] = rock
            subqueries.append("rock=%(rock)s")
        if feat is not None:
            suser['feat'] = feat
            subqueries.append("feat=%(feat)s")
        if book is not None:
            suser['book'] = book
            subqueries.append("book=%(book)s")
        if vrock is not None:
            suser['vrock'] = vrock
            subqueries.append("vrock=%(vrock)s")
        if extra is not None:
            suser['jextra'] = escape.json_encode(extra)
            subqueries.append("jextra=%(jextra)s")
        if heros is not None:
            suser['jheros'] = escape.json_encode(heros)
            subqueries.append("jheros=%(jheros)s")
        if prods is not None:
            suser['jprods'] = escape.json_encode(prods)
            subqueries.append("jprods=%(jprods)s")
        if batts is not None:
            suser['jbatts'] = escape.json_encode(batts)
            subqueries.append("jbatts=%(jbatts)s")
        if seals is not None:
            suser['jseals'] = escape.json_encode(seals)
            subqueries.append("jseals=%(jseals)s")
        if tasks is not None:
            suser['jtasks'] = escape.json_encode(tasks)
            subqueries.append("jtasks=%(jtasks)s")
        if works is not None:
            suser['jworks'] = escape.json_encode(works)
            subqueries.append("jworks=%(jworks)s")
        if mails is not None:
            suser['jmails'] = escape.json_encode(mails)
            subqueries.append("jmails=%(jmails)s")
        if doors is not None:
            suser['jdoors'] = escape.json_encode(doors)
            subqueries.append("jdoors=%(jdoors)s")
        if beautys is not None:
            suser['jbeautys'] = escape.json_encode(beautys)
            subqueries.append("jbeautys=%(jbeautys)s")
        if activities is not None:
            suser['jactivities'] = escape.json_encode(activities)
            subqueries.append("jactivities=%(jactivities)s")
        if recharge is not None:
            suser['jrecharge'] = escape.json_encode(recharge)
            subqueries.append("jrecharge=%(jrecharge)s")
        if insts is not None:
            suser['jinsts'] = escape.json_encode(insts)
            subqueries.append("jinsts=%(jinsts)s")

        suser['timestamp'] = str(int(time.time()))
        subqueries.append("timestamp=%(timestamp)s")
        res = yield self.sql.runQuery(
            "SELECT user_id FROM core_firstlott WHERE user_id=%s AND first=True AND lotttype=%s LIMIT 1",
            (uid, E.lott_by_rock))
        if res:
            firstlott = E.true
        else:
            firstlott = E.false
        # SQL UPDATE START
        query = "UPDATE core_user SET " + ",".join(
            subqueries) + " WHERE id=%(uid)s RETURNING name, nickname, avat, xp, gold, rock, feat, book, jextra," \
                          "jheros, jprods, jbatts, jseals, jtasks, jworks, jmails, jdoors, vrock, jbeautys, jactivities, jrecharge, jinsts"
        params = suser
        user = None
        for i in range(5):
            try:
                res = yield self.sql.runQuery(query, params)
                if not res:
                    user = None
                    yield self.del_cache("user:%s" % uid)
                else:
                    r = res[0]
                    user = dict(uid=uid, name=r[0], nickname=r[1], avat=r[2], xp=r[3], gold=r[4], rock=r[5], feat=r[6],
                                book=r[7], vrock=r[17])
                    user['extra'] = r[8] and escape.json_decode(r[8]) or {}
                    user['heros'] = r[9] and escape.json_decode(r[9]) or {}
                    user['prods'] = r[10] and escape.json_decode(r[10]) or {}
                    user['batts'] = r[11] and escape.json_decode(r[11]) or {}
                    user['seals'] = r[12] and escape.json_decode(r[12]) or {}
                    user['tasks'] = r[13] and escape.json_decode(r[13]) or {}
                    user['works'] = r[14] and escape.json_decode(r[14]) or {}
                    user['mails'] = r[15] and escape.json_decode(r[15]) or {}
                    user['doors'] = r[16] and escape.json_decode(r[16]) or {}
                    user['beautys'] = r[18] and escape.json_decode(r[18]) or {}
                    user['activities'] = r[19] and escape.json_decode(r[19]) or {}
                    user['recharge'] = r[20] and escape.json_decode(r[20]) or {}
                    user['insts'] = r[21] and escape.json_decode(r[21]) or {}
                    user['first_by_rock'] = firstlott
                    yield self.set_cache("user:%s" % uid, user)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        # SQL UPDATE END
        if reason:
            changed = {}
            if olduser['gold'] != user['gold']:
                changed['gold'] = (olduser['gold'], user['gold'])
            if olduser['rock'] != user['rock']:
                changed['rock'] = (olduser['rock'], user['rock'])
            if olduser['feat'] != user['feat']:
                changed['feat'] = (olduser['feat'], user['feat'])
            changedprods = {}
            olduserprodkeys = set(olduser['prods'].keys())
            userprodkeys = set(user['prods'].keys())
            delkeys = olduserprodkeys - userprodkeys
            for key in delkeys:
                changedprods[key] = (olduser['prods'][key], 0)
            newkeys = userprodkeys - olduserprodkeys
            for key in newkeys:
                changedprods[key] = (0, user['prods'][key])
            samekeys = userprodkeys & olduserprodkeys
            for key in samekeys:
                if olduser['prods'][key] != user['prods'][key]:
                    changedprods[key] = (olduser['prods'][key], user['prods'][key])
            if changedprods:
                changed['prods'] = changedprods
            value = json.dumps(changed)
            yield self.predis.lpush('all:log:user', pickle.dumps([int(time.time()), ZONE_ID, uid, value, reason]))
        defer.returnValue(user)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_seal(self, uid):
        user = []
        res = yield self.sql.runQuery("SELECT seals FROM core_fourteensealsecond WHERE user_id=%s LIMIT 1", (uid,))
        if not res:
            user = None
        else:
            r = res[0]
            try:
                user = r[0] and escape.json_decode(r[0]) or {}
            except Exception:
                user = None
        defer.returnValue(user)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_seal(self, uid, seals=None):
        suser = {'uid': uid}
        subqueries = []
        if seals is not None:
            suser['seals'] = escape.json_encode(seals)
            subqueries.append("seals=%(seals)s")
        query = "SELECt id FROM core_fourteensealsecond WHERE user_id=%(uid)s;"
        res = yield self.sql.runQuery(query, suser);
        if not res:
            query = "INSERT INTO core_fourteensealsecond (user_id, seals) VALUES (%(uid)s, %(seals)s) RETURNING user_id,seals;"
        else:
            query = "UPDATE core_fourteensealsecond SET " + ",".join(
                subqueries) + " WHERE user_id=%(uid)s RETURNING user_id,seals;"
        user = None
        params = suser
        for i in range(5):
            try:
                yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(user)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_hp(self, user):
        uid = user['uid']
        hpmax = E.hpmax(user['xp']) + E.incr4hp(user['vrock'])
        hpup = E.hpup
        hptick = E.hptick
        timenow = int(time.time()) - self.settings["timepoch"]
        hp = yield self.redis.hget("hp", uid)
        tick = 0
        if not hp:
            res = yield self.sql.runQuery("SELECT hp, timestamp FROM core_hp WHERE user_id=%s LIMIT 1", (uid,))
            if res:
                hp = res[0][1] * 100000 + res[0][0]
                yield self.redis.hset("hp", uid, hp)
            else:
                hpcur = hpmax
                yield self.sql.runQuery("INSERT INTO core_hp (user_id, hp, timestamp) VALUES (%s, %s, %s) RETURNING id",
                                        (uid, hpcur, timenow))
                yield self.redis.hset("hp", uid, timenow * 100000 + hpcur)
        if hp:
            timestamp, hpsnap = divmod(hp, 100000)
            if hpsnap >= hpmax:
                hpcur = hpsnap
            else:
                timenow = int(time.time()) - self.settings["timepoch"]
                n, r = divmod((timenow - timestamp), hptick)
                hpuped = hpsnap + n * hpup
                if hpuped < hpmax:
                    hpcur = hpuped
                    if r != 0:
                        tick = hptick - r
                    else:
                        tick = hptick
                else:
                    hpcur = hpmax
        defer.returnValue((hpcur, tick))

    @storage.databaseSafe
    @defer.inlineCallbacks
    def add_hp(self, user, value, reason=''):
        uid = user['uid']
        hpmax = E.hpmax(user['xp']) + E.incr4hp(user['vrock'])
        hpup = E.hpup
        hptick = E.hptick
        timenow = int(time.time()) - self.settings["timepoch"]
        hpcur, tick = yield self.get_hp(user)
        hpnow = hpcur + value
        if hpnow < hpmax:
            if hpnow < 0:
                hpnow = 0
            if 0 < tick:
                timetick = timenow - (hptick - tick)
            else:
                tick = hptick
                timetick = timenow
        else:
            timetick = timenow
        yield self.redis.hset("hp", uid, timetick * 100000 + hpnow)
        res = yield self.sql.runQuery("UPDATE core_hp SET hp=%s, timestamp=%s WHERE user_id=%s RETURNING id",
                                      (hpnow, timetick, uid))
        if not res:
            res = yield self.sql.runQuery("INSERT INTO core_hp (user_id, hp, timestamp) VALUES (%s, %s, %s)",
                                          (uid, hpnow, timetick))
        yield self.predis.lpush('all:log:hp',
                                pickle.dumps([int(time.time()), ZONE_ID, uid, value, hpcur, hpmax, reason]))
        defer.returnValue((hpnow, tick))

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_sp(self, user):
        uid = user['uid']
        spmax = E.spmax(user['vrock'])
        spup = E.spup
        sptick = E.sptick
        timenow = int(time.time()) - self.settings["timepoch"]
        sp = yield self.predis.hget("sp:%s" % ZONE_ID, uid)
        tick = 0
        if not sp:
            spcur = spmax
            yield self.predis.hset("sp:%s" % ZONE_ID, uid, timenow * 10000 + spcur)
        else:
            timestamp, spsnap = divmod(sp, 10000)
            if spsnap >= spmax:
                spcur = spsnap
            else:
                timenow = int(time.time()) - self.settings["timepoch"]
                n, r = divmod((timenow - timestamp), sptick)
                spuped = spsnap + n * spup
                if spuped < spmax:
                    spcur = spuped
                    if r != 0:
                        tick = sptick - r
                    else:
                        tick = sptick
                else:
                    spcur = spmax
        defer.returnValue((spcur, tick))

    @storage.databaseSafe
    @defer.inlineCallbacks
    def add_sp(self, user, value):
        uid = user['uid']
        spmax = E.spmax(user['vrock'])
        spup = E.spup
        sptick = E.sptick
        sp = yield self.predis.hget("sp:%s" % ZONE_ID, uid)
        tick = 0
        timenow = int(time.time()) - self.settings["timepoch"]
        if not sp:
            spcur, stick = yield self.get_sp(user)
        else:
            timestamp, spsnap = divmod(sp, 10000)
            if spsnap >= spmax:
                spcur = spsnap
            else:
                n, r = divmod((timenow - timestamp), sptick)
                spuped = spsnap + n * spup
                if spuped < spmax:
                    spcur = spuped
                    if r != 0:
                        tick = sptick - r
                    else:
                        tick = sptick
                else:
                    spcur = spmax
        spnow = spcur + value
        if spnow < spmax:
            if spnow < 0:
                spnow = 0
            if 0 < tick < sptick:
                timetick = timenow - (sptick - tick)
            else:
                tick = sptick
                timetick = timenow
        else:
            timetick = timenow
        yield self.predis.hset("sp:%s" % ZONE_ID, uid, timetick * 10000 + spnow)
        yield self.predis.lpush('all:log:sp', pickle.dumps([int(time.time()), ZONE_ID, uid, value, spcur, spmax]))
        defer.returnValue((spnow, tick))

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_prop(self, uid, label):
        prop = yield self.get_cache("prop:%s:%s" % (uid, label))
        if not prop:
            res = yield self.sql.runQuery("SELECT num,txt FROM core_prop WHERE user_id=%s AND label=%s LIMIT 1",
                                          (uid, label))
            if not res:
                prop = dict(uid=uid, label=label, num=None, txt=None)
                # SQL UPDATE START
                query = "INSERT INTO core_prop(user_id, label, num, txt, timestamp) VALUES (%(uid)s, %(label)s, %(num)s, %(txt)s," \
                        + str(int(time.time())) + ") RETURNING id"
                params = prop
                for i in range(5):
                    try:
                        yield self.sql.runQuery(query, params)
                        break
                    except storage.IntegrityError:
                        log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                        continue
                        # SQL UPDATE END
            else:
                r = res[0]
                prop = dict(uid=uid, label=label, num=r[0], txt=r[1])
            yield self.set_cache(("prop:%s:%s" % (uid, label)), prop)
        defer.returnValue(prop)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_prop(self, uid, label, num=None, txt=None):
        prop = yield self.get_prop(uid, label)
        if prop:
            if num is not None:
                prop['num'] = num
            if txt is not None:
                prop['txt'] = txt
            yield self.set_cache(("prop:%s:%s" % (uid, label)), prop)
            # SQL UPDATE START
            query = "UPDATE core_prop SET num=%(num)s, txt=%(txt)s, timestamp=" \
                    + str(int(time.time())) + "WHERE user_id=%(uid)s AND label=%(label)s RETURNING id"
            params = prop
            for i in range(5):
                try:
                    res = yield self.sql.runQuery(query, params)
                    if not res:
                        query2 = "INSERT INTO core_prop(user_id, label, num, txt, timestamp) VALUES (%(uid)s, %(label)s, %(num)s, %(txt)s, " \
                                 + str(int(time.time())) + ") RETURNING id"
                        params2 = prop
                        for ii in range(5):
                            try:
                                yield self.sql.runQuery(query2, params2)
                                break
                            except storage.IntegrityError:
                                log.msg("SQL integrity error, retry(%i): %s" % (ii, (query2 % params2)))
                                continue
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
                    # SQL UPDATE END
        defer.returnValue(prop)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_mails(self, user, mids):
        mails = [key for key in user['mails'] if user['mails'][key] == 0]
        ballmails = yield self.redis.get("allmails:%s" % user['uid'])
        if not ballmails:
            allmails = {}
            if mails:
                res = yield self.sql.runQuery(
                    "SELECT id, sender, title, content, jawards, created_at, type FROM core_mail WHERE to_id=%s or"
                    " to_id ISNULL AND id in %s AND created_at::DATE=NOW()::DATE ORDER BY type ASC, created_at DESC",
                    (user['uid'], tuple(mails)))
                if res:
                    for r in res:
                        mid = str(r[0])
                        mail = dict(mid=mid, sender=r[1], title=r[2], content=r[3],
                                    timestamp=time.mktime(r[5].timetuple()), type=r[6])
                        mail['awards'] = r[4] and escape.json_decode(r[4]) or {}
                        allmails[mid] = mail
            yield self.redis.set("allmails:%s" % user['uid'], pickle.dumps(allmails))
        else:
            allmails = pickle.loads(ballmails)
        mails = []
        for mid in mids:
            if mid in allmails:
                mails.append(allmails[mid])
        defer.returnValue(mails)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_mails(self, user):
        uid = user['uid']
        res = yield self.sql.runQuery(
            "SELECT id, sender, title, content, jawards, created_at FROM core_mail WHERE to_id=%s or to_id ISNULL AND"
            " created_at::DATE=NOW()::DATE ORDER BY type ASC, created_at DESC",
            (uid,))
        for r in res:
            if str(r[0]) not in user['mails']:
                user['mails'][r[0]] = -1

        cuser = dict(mails=user['mails'])
        yield self.set_user(uid, **cuser)
        defer.returnValue(user['mails'])

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_mails(self, user):
        allmails = {}
        res = yield self.sql.runQuery(
            "SELECT id, sender, title, content, jawards, created_at, type FROM core_mail WHERE to_id=%s or to_id ISNULL"
            " AND created_at::DATE=NOW()::DATE ORDER BY type ASC, created_at DESC",
            (user['uid'],))
        if res:
            for r in res:
                mid = str(r[0])
                mail = dict(mid=mid, sender=r[1], title=r[2], content=r[3], timestamp=time.mktime(r[5].timetuple()),
                            type=r[6])
                if r[6] == 1:
                    if str(mid) not in user['mails']:
                        user['mails'][mid] = 0
                    mail['awards'] = r[4] and escape.json_decode(r[4]) or {}
                    allmails[mid] = mail
                else:
                    if str(r[0]) in user['mails']:
                        if user['mails'][str(r[0])] == 1:
                            pass
                        else:
                            mail['awards'] = r[4] and escape.json_decode(r[4]) or {}
                            allmails[mid] = mail
                    else:
                        mail['awards'] = r[4] and escape.json_decode(r[4]) or {}
                        allmails[mid] = mail
                        user['mails'][mid] = 0
        yield self.redis.set("allmails:%s" % user['uid'], pickle.dumps(allmails))
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def send_mails(self, sender, to_id, title, content, awards):
        query = "INSERT INTO core_mail(sender, to_id, title, content, jawards, comment, created_at, type) VALUES" \
                " (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
        params = (sender, to_id, title, content, escape.json_encode(awards), '', datetime.datetime.now(), 0)
        # print query, params
        for i in range(5):
            try:
                yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue

        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def check_redpot(self, user):
        # lottmark
        lott = yield self.update_lott(user)
        free_by_gold = 0
        free_by_rock = 0
        if lott[E.lott_by_gold]['left_times'] > 0 and lott[E.lott_by_gold]['interval'] == 0:
            free_by_gold = 1
        if lott[E.lott_by_rock]['left_times'] > 0 and lott[E.lott_by_rock]['interval'] == 0:
            free_by_rock = 1
        lottmark = free_by_gold or free_by_rock
        # mailmark
        cuser = {}
        mailcomming = E.checkmails(user)
        if mailcomming:
            cuser['mails'] = user['mails']
            yield self.set_user(user['uid'], **cuser)
        mails = yield self.set_mails(user)
        mailmark = 0
        if E.false in mails.values():
            mailmark = 1
        # arenamark
        if user['xp'] / 100000 < D.ARENA_OPEN_LIMIT:
            arenamark = 0
        else:
            arenamark = yield self.redis.get('arenamark:%s' % user['uid'])
            if not arenamark:
                arenamark = 0
        defer.returnValue((lottmark, mailmark, arenamark))

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_firstlott(self, user, lotttype):
        res = yield self.sql.runQuery(
            "SELECT user_id FROM core_firstlott WHERE user_id=%s AND first=True AND lotttype=%s LIMIT 1",
            (user['uid'], lotttype))
        firstlott = False
        if not res:
            query = "INSERT INTO core_firstlott(user_id, first, created_at, lotttype) VALUES (%s, %s, %s, %s) RETURNING id"
            params = (user['uid'], True, int(time.time()), lotttype)
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue

            firstlott = True
        defer.returnValue(firstlott)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_daylott(self, user):
        res = yield self.sql.runQuery("select updated_at::date from core_daylott where updated_at::date=current_date")
        times = None
        if not res:
            query = "INSERT INTO core_daylott(user_id, times, updated_at) VALUES (%s, %s, %s) RETURNING times"
            params = (user['uid'], 1, datetime.datetime.now())
            for i in range(5):
                try:
                    times = yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        else:
            query = "UPDATE core_daylott SET times=times+1, updated_at=%s WHERE user_id=%s RETURNING times"
            params = (datetime.datetime.now(), user['uid'])
            for i in range(5):
                try:
                    times = yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        defer.returnValue(times)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_freelott(self, is_free, user, ltype):
        query = "UPDATE core_freelott SET times=times+1, free=%s, timestamp=%s WHERE user_id=%s AND lotttype=%s RETURNING times"
        params = (is_free, int(time.time()), user['uid'], ltype)
        for i in range(5):
            try:
                yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_lott(self, user):
        lott = D.LOTT
        for lot in lott.keys():
            res = yield self.sql.runQuery(
                "select free, timestamp from core_freelott where user_id=%s and lotttype=%s limit 1",
                (user['uid'], lot))
            if res:
                lottfree = yield self.redis.get('lottfree:%s:%s' % (user['uid'], lot))
                freetimes = yield self.redis.get('freetimes:%s:%s' % (user['uid'], lot))
                if not freetimes:
                    freetimes = 0
                if res[0][0] == True:
                    if lot == E.lott_by_gold and freetimes > E.limit_by_gold:
                        lott[lot]['left_times'] = 0
                    else:
                        if lot == E.lott_by_gold:
                            lott[lot]['left_times'] = E.limit_by_gold - freetimes
                        else:
                            lott[lot]['left_times'] = 1

                    lott[lot]['interval'] = 0
                    yield self.redis.set('lottfree:%s:%s' % (user['uid'], lot), True)

                else:
                    if lot == E.lott_by_gold and freetimes > E.limit_by_gold:
                        lott[lot]['interval'] = 0
                        lott[lot]['left_times'] = 0
                        continue
                    if lot == E.lott_by_gold:
                        interval_times = E.timer_by_gold
                        lott[lot]['left_times'] = E.limit_by_gold - freetimes
                    else:
                        interval_times = E.timer_by_rock
                        lott[lot]['left_times'] = 1
                    interval = int(time.time()) - int(res[0][1])
                    if interval <= 0:
                        interval = 0
                    if interval > interval_times:
                        lott[lot]['interval'] = 0
                        yield self.update_freelott(True, user, lot)
                        if lott[lot]['left_times'] > 0:
                            yield self.redis.set('lottfree:%s:%s' % (user['uid'], lot), True)
                    else:
                        lott[lot]['interval'] = interval_times - interval
        defer.returnValue(lott)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_prodproba(self):
        res = yield self.sql.runQuery("SELECT lotttype, times, proba FROM core_prodproba")
        proba1 = {}
        proba2 = {}
        if res:
            for r in res:
                lotttype, times, proba = r
                if lotttype == 1:
                    proba1[times] = [str(one) for one in proba.split(',')]
                elif lotttype == 2:
                    proba2[times] = [str(one) for one in proba.split(',')]
                else:
                    pass
        prodproba = {1: proba1, 2: proba2}

        prodreward = {}
        res = yield self.sql.runQuery("SELECT lotttype, prod, maxnum, minnum FROM core_prodreward")
        if res:
            for r in res:
                prodreward[str(r[0])] = []
            for r in res:
                lotttype, prod, maxnum, minnum = r
                if str(lotttype) in prodreward:
                    prodreward[str(lotttype)].append([str(prod), maxnum, minnum])

        defer.returnValue((prodproba, prodreward))

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_arenacoin(self, user, arena_coin):
        query = "update core_arena set arena_coin=arena_coin+%s WHERE user_id=%s RETURNING arena_coin"
        params = (arena_coin, user['uid'])
        for i in range(5):
            try:
                arena_coin = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        yield self.set_arena(user['uid'])
        defer.returnValue(arena_coin)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_arenaresult(self, user, cid, result):
        uid = user['uid']
        now_rank = before_rank = 0
        if int(result) == 1:
            res = yield self.sql.runQuery(
                "SELECT a.now_rank, b.now_rank, a.before_rank, a.last_rank FROM (SELECT user_id, now_rank, before_rank, last_rank FROM core_arena WHERE user_id=%s) AS a, "
                "(SELECT user_id, now_rank, before_rank FROM core_arena WHERE user_id=%s) AS b", (uid, cid))
            if res:
                for r in res:
                    now_rank, before_rank, last_rank = r[0], r[2], r[3]
                    if r[0] > r[1]:
                        now_rank = r[1]
                        last_rank = r[0]
                        query = "UPDATE core_arena SET now_rank=%s, last_rank=%s WHERE user_id=%s  RETURNING id"
                        params = (now_rank, last_rank, uid)
                        for i in range(5):
                            try:
                                yield self.sql.runQuery(query, params)
                                break
                            except storage.IntegrityError:
                                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                                continue
                        query = "UPDATE core_arena SET now_rank=%s WHERE user_id=%s RETURNING id"
                        params = (r[0], cid)
                        for i in range(5):
                            try:
                                yield self.sql.runQuery(query, params)
                                break
                            except storage.IntegrityError:
                                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                                continue

            query = "INSERT INTO core_arenaresult(user_id, competitor_id, result, ascend, timestamp) VALUES (%s, %s, %s, %s, %s) RETURNING id"
            params = (uid, cid, result, last_rank - now_rank, int(time.time()))
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
            yield self.set_arena(uid)
            yield self.set_arena(cid)
            defer.returnValue((now_rank, before_rank, last_rank))
        else:
            query = "INSERT INTO core_arenaresult(user_id, competitor_id, result, ascend, timestamp) VALUES (%s, %s, %s, %s, %s) RETURNING id"
            params = (uid, cid, result, 0, int(time.time()))
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
            defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_arenarank(self, user, now_rank, before_rank, last_rank):
        now_rank, before_rank, last_rank = now_rank, before_rank, last_rank
        if now_rank < before_rank:
            query = "UPDATE core_arena SET before_rank=%s WHERE user_id=%s RETURNING id"
            params = (now_rank, user['uid'])
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
            rock = E.arenamatch(now_rank, before_rank)
            if rock:
                awards = dict(rock=rock)
            else:
                awards = {}
            yield self.set_mails(user)
            now_rank, before_rank = now_rank, now_rank
        defer.returnValue((now_rank, before_rank, last_rank, awards))

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_arenaguard(self, uid, heros, positions, formation):
        jpos = dict(zip(heros, positions))
        res = yield self.sql.runQuery(
            "SELECT a.jheros, b.jguards, b.jpositions FROM core_user AS a, core_arena AS b WHERE a.id=b.user_id AND a.id=%s" % uid)
        if res:
            for r in res:
                jheros = r[0] and escape.json_decode(r[0]) or {}
                jguards = {}
                jpositions = {}
                jguards_list = filter(lambda j: j in jheros, heros)
                for j in jguards_list:
                    jguards[j] = jheros[j]
                    jpositions[j] = jpos[j]
                query = "UPDATE core_arena SET jguards=%s, jpositions=%s, formation=%s WHERE user_id=%s RETURNING id"
                params = (escape.json_encode(jguards), escape.json_encode(jpositions), formation, uid)
                # print query % params
                for i in range(5):
                    try:
                        yield self.sql.runQuery(query, params)
                        break
                    except storage.IntegrityError:
                        log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                        continue
        yield self.set_arena(uid)
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_arena(self, uid):
        res = yield self.sql.runQuery("SELECT a.id, b.arena_coin, b.now_rank, a.jheros, b.jguards, b.formation, a.xp,"
                                      " a.nickname, a.avat, b.before_rank, b.last_rank, b.jpositions FROM core_user AS a,\
                                       core_arena AS b WHERE a.id=b.user_id AND a.id=%s", (uid,))
        if res:
            arenas = {r[0]: dict(uid=r[0],
                                 arena_coin=r[1],
                                 now_rank=r[2],
                                 heros=r[3] and escape.json_decode(r[3]) or {},
                                 guards=r[4] and escape.json_decode(r[4]) or {},
                                 win_times=0,
                                 formation=r[5],
                                 xp=r[6],
                                 nickname=r[7],
                                 avat=r[8],
                                 before_rank=r[9],
                                 last_rank=r[10],
                                 positions=r[11] and escape.json_decode(r[11]) or {}
                                 ) for r in res}
            for k, v in arenas.iteritems():
                yield self.redis.set('arenas:%s' % k, pickle.dumps(v))
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_arena(self, uid):
        arenas = yield self.redis.get('arenas:%s' % uid)
        if arenas:
            arenas = pickle.loads(arenas)
            # yield self.set_arena(uid)
        else:
            res = yield self.sql.runQuery(
                "SELECT a.id, b.arena_coin, b.now_rank, a.jheros, b.jguards, b.formation, a.xp,"
                " a.nickname, a.avat, b.before_rank, b.last_rank, b.jpositions FROM core_user AS a,\
                 core_arena AS b WHERE a.id=b.user_id AND a.id=%s LIMIT 1", (uid,))
            if res:
                for r in res:
                    arenas = dict(uid=r[0],
                                  arena_coin=r[1],
                                  now_rank=r[2],
                                  heros=r[3] and escape.json_decode(r[3]) or {},
                                  guards=r[4] and escape.json_decode(r[4]) or {},
                                  win_times=0,
                                  formation=r[5],
                                  xp=r[6],
                                  nickname=r[7],
                                  avat=r[8],
                                  before_rank=r[9],
                                  last_rank=r[10],
                                  positions=r[11] and escape.json_decode(r[11]) or {}
                                  )
            else:
                arenas = None
        defer.returnValue(arenas)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def random_competitor(self, arena, uid, num):
        arena_rule = []
        for i in xrange(0, len(D.ARENARULE) / 8):
            if arena['now_rank'] >= D.ARENARULE[i * 8] and arena['now_rank'] <= D.ARENARULE[i * 8 + 1]:
                arena_rule.extend(
                    [D.ARENARULE[i * 8 + 2], D.ARENARULE[i * 8 + 3], D.ARENARULE[i * 8 + 4], D.ARENARULE[i * 8 + 5], \
                     D.ARENARULE[i * 8 + 6], D.ARENARULE[i * 8 + 7]])
                break
        left = {}
        res = yield self.sql.runQuery(
            "SELECT user_id, now_rank FROM core_arena WHERE user_id<>%s AND now_rank>=%s AND now_rank<=%s AND now_rank<%s ORDER BY now_rank DESC, RANDOM() DESC limit %s",
            (uid, arena_rule[0], arena_rule[1], arena['now_rank'], num))
        for r in res:
            arenas = yield self.get_arena(r[0])
            cuser = yield self.get_user(r[0])
            beautys = yield self.get_beautys(cuser)
            if arenas:
                guards = {}
                for key in arenas['guards'].keys():
                    guards[key] = cuser['heros'].get(key, {})
                left[r[0]] = dict(uid=arenas['uid'], guards=guards, now_rank=arenas['now_rank'],
                                  nickname=arenas['nickname'], \
                                  xp=arenas['xp'], avat=arenas['avat'], win_times=arenas['win_times'],
                                  formation=arenas['formation'], \
                                  positions=arenas['positions'], beautys=beautys)
        middle = {}
        res = yield self.sql.runQuery(
            "SELECT user_id, now_rank FROM core_arena WHERE user_id<>%s AND now_rank>=%s AND now_rank<=%s AND now_rank<%s ORDER BY now_rank DESC, RANDOM() DESC limit %s",
            (uid, arena_rule[2], arena_rule[3], arena['now_rank'], num))
        for r in res:
            arenas = yield self.get_arena(r[0])
            cuser = yield self.get_user(r[0])
            beautys = yield self.get_beautys(cuser)
            if arenas:
                guards = {}
                for key in arenas['guards'].keys():
                    guards[key] = cuser['heros'].get(key, {})
                middle[r[0]] = dict(uid=arenas['uid'], guards=guards, now_rank=arenas['now_rank'],
                                    nickname=arenas['nickname'], \
                                    xp=arenas['xp'], avat=arenas['avat'], win_times=arenas['win_times'],
                                    formation=arenas['formation'], \
                                    positions=arenas['positions'], beautys=beautys)
        right = {}
        res = yield self.sql.runQuery(
            "SELECT user_id, now_rank FROM core_arena WHERE user_id<>%s AND now_rank>=%s AND now_rank<=%s AND now_rank<%s ORDER BY now_rank DESC, RANDOM() DESC limit %s",
            (uid, arena_rule[4], arena_rule[5], arena['now_rank'], num))
        for r in res:
            arenas = yield self.get_arena(r[0])
            cuser = yield self.get_user(r[0])
            beautys = yield self.get_beautys(cuser)
            if arenas:
                guards = {}
                for key in arenas['guards'].keys():
                    guards[key] = cuser['heros'].get(key, {})
                right[r[0]] = dict(uid=arenas['uid'], guards=guards, now_rank=arenas['now_rank'],
                                   nickname=arenas['nickname'], \
                                   xp=arenas['xp'], avat=arenas['avat'], win_times=arenas['win_times'],
                                   formation=arenas['formation'], \
                                   positions=arenas['positions'], beautys=beautys)

        competitor = dict(left=left, middle=middle, right=right)
        defer.returnValue(competitor)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def create_mine(self, uid, guards, heros, formation, mtype, size, pos):
        jguards_list = filter(lambda j: j in heros, guards)
        jguards = jstocks = {}
        for j in jguards_list:
            jguards[j] = heros[j]
        sword = E.count4sword(guards, heros)
        duration = E.duration4mine(mtype, size)
        created_at = int(time.time())
        ended_at = int(time.time()) + duration
        query = "INSERT INTO core_mine(user_id, jguards, formation, sword, type, size, status, jstocks, jpositions,\
         created_at, ended_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
        params = (uid, escape.json_encode(jguards), formation, sword, mtype, size, E.busy, escape.json_encode(jstocks), \
                  escape.json_encode(pos), created_at, ended_at)
        for i in range(5):
            try:
                mid, = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(mid)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_mine(self, uid, mid, jguards, formation, created_at, stocks, mtype, heros, pos):
        sword = E.count4sword(jguards.keys(), heros)
        rate = E.earn4mine(jguards.keys(), heros, mtype)
        times = float(int(time.time()) - int(created_at)) / 3600
        feat = stocks.get('feat', 0) + int(rate.get('feat', 0) * times)
        rock = stocks.get('rock', 0) + int(rate.get('rock', 0) * times)
        gold = stocks.get('gold', 0) + int(rate.get('gold', 0) * times)
        jstocks = dict(feat=feat, rock=rock, gold=gold)
        query = "UPDATE core_mine SET jguards=%s, formation=%s, sword=%s, created_at=%s, jstocks=%s,\
         jpositions=%s WHERE user_id=%s AND id=%s RETURNING id"
        params = (escape.json_encode(jguards), formation, sword, int(time.time()), escape.json_encode(jstocks), \
                  escape.json_encode(pos), uid, mid)
        for i in range(5):
            try:
                mid = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(mid)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_mine(self, uid, mid):
        res = yield self.sql.runQuery("SELECT a.id, a.jguards, a.formation, a.sword, a.type, a.size, a.status,\
         a.created_at, a.ended_at, b.jheros, a.jstocks, a.jpositions FROM core_mine AS a, core_user AS b WHERE a.user_id=%s\
          AND a.id=%s AND status=%s AND a.user_id=b.id", (uid, mid, E.busy))
        if res:
            for r in res:
                guards = r[1] and escape.json_decode(r[1]) or {}
                heros = r[9] and escape.json_decode(r[9]) or {}
                stocks = r[10] and escape.json_decode(r[10]) or {}
                positions = r[11] and escape.json_decode(r[11]) or {}
                if not stocks:
                    stocks = dict(gold=0, feat=0, rock=0)
                jguards_list = filter(lambda j: j in heros, guards.keys())
                jguards = {}
                for j in jguards_list:
                    jguards[j] = heros[j]
                mine = dict(
                    id=r[0],
                    guards=jguards,
                    formation=r[2],
                    sword=r[3],
                    type=r[4],
                    size=r[5],
                    status=r[6],
                    created_at=r[7],
                    ended_at=r[8],
                    stocks=stocks,
                    positions=positions,
                )
        else:
            mine = {}
        defer.returnValue(mine)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_mine_guards(self, uid, mid=None):
        all_guards = []
        now_guards = []
        mineguards = yield self.redis.keys("mineguards:%s:*" % uid)
        for one in mineguards:
            guards = yield self.redis.get("%s" % one)
            if guards:
                guards = pickle.loads(guards)
                all_guards.extend(guards)
        all_guards = list(set(all_guards))
        if mid:
            now_guards = yield self.redis.get("mineguards:%s:%s" % (uid, mid))
            if now_guards:
                now_guards = pickle.loads(now_guards)
        defer.returnValue((all_guards, now_guards))

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_prison(self, user):
        res = yield self.sql.runQuery(
            "SELECT prisoner_id, status, created_at, ended_at, position FROM core_prison WHERE user_id=%s",
            (user['uid'],))
        prisoners = {}
        if res:
            for r in res:
                if r[1]:
                    if int(time.time()) - r[2] > E.timer_by_reclaim:
                        interval = 0
                    else:
                        interval = E.timer_by_reclaim - (int(time.time()) - r[2])
                    if interval < 0:
                        interval = 0
                else:
                    interval = 0
                prisoner = yield self.get_user(r[0])
                prisoners[r[4]] = dict(uid=r[0], status=r[1], created_at=r[2], interval=interval, xp=prisoner['xp'],
                                       avat=prisoner['avat'], nickname=prisoner['nickname'], heros=prisoner['heros'])
        defer.returnValue(prisoners)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def init_prison(self, user, cid, position, start=0):
        xp = user['xp']
        # 根据等级开放监狱数量
        res = yield self.sql.runQuery(
            "SELECT status, created_at FROM core_prison WHERE user_id=%s AND prisoner_id=%s AND position=%s LIMIT 1",
            (user['uid'], cid, position))
        if res:

            query = "UPDATE core_prison SET status=%s, created_at=%s, ended_at=%s WHERE user_id=%s AND prisoner_id=%s AND position=%s RETURNING id"
            params = (E.idle, int(time.time()), int(time.time()), user['uid'], cid, position)

            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        else:
            query = "INSERT INTO core_prison(user_id, prisoner_id, status, created_at, ended_at, position) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id"
            params = (user['uid'], cid, E.idle, int(time.time()), int(time.time()), position)
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        res = yield self.sql.runQuery(
            "SELECT prisoner_id, status, created_at, ended_at, position FROM core_prison WHERE user_id=%s",
            (user['uid'],))
        if res:
            prisoners = {r[4]: dict(status=r[1], created_at=r[2], ended_at=r[3], position=r[4], uid=r[0]) for r in res}
            yield self.redis.set('prisoners:%s' % user['uid'], pickle.dumps(prisoners))
        defer.returnValue(prisoners)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_prison(self, user, cid, status, start=0):
        xp = user['xp']
        # 根据等级开放监狱数量
        res = yield self.sql.runQuery(
            "SELECT status, created_at FROM core_prison WHERE user_id=%s AND prisoner_id=%s LIMIT 1",
            (user['uid'], cid))
        if res:
            if not start:
                query = "UPDATE core_prison SET status=%s, created_at=%s, ended_at=%s WHERE user_id=%s AND prisoner_id=%s RETURNING id"
                params = (status, int(time.time()), int(time.time()), user['uid'], cid)
            else:
                query = "UPDATE core_prison SET status=%s, created_at=%s, ended_at=%s WHERE user_id=%s AND prisoner_id=%s RETURNING id"
                params = (E.idle, int(time.time()), int(time.time()), user['uid'], cid)

            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        else:
            query = "INSERT INTO core_prison(user_id, prisoner_id, status, created_at, ended_at) VALUES (%s, %s, %s, %s, %s) RETURNING id"
            params = (user['uid'], cid, status, int(time.time()), int(time.time()))
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        res = yield self.sql.runQuery(
            "SELECT prisoner_id, status, created_at, ended_at FROM core_prison WHERE user_id=%s", (user['uid'],))
        if res:
            wardens = {r[0]: dict(status=r[1], created_at=r[2], ended_at=r[3]) for r in res}
            yield self.redis.set('wardens:%s' % user['uid'], pickle.dumps(wardens))
        defer.returnValue(wardens)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_release(self, user, cid, status):
        query = "INSERT INTO core_release(user_id, prisoner_id, status, created_at) VALUES (%s, %s, %s, %s) RETURNING id"
        params = (user['uid'], cid, status, int(time.time()))
        for i in range(5):
            try:
                pid = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(pid)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_card(self, user):
        t = datetime.datetime.today().date()
        timestamp = int(time.mktime(t.timetuple()))
        res = yield self.sql.runQuery("SELECT created_at, ended_at FROM core_card WHERE user_id=%s LIMIT 1",
                                      (user['uid'],))
        lefttime = 0
        if res:
            created_at, ended_at = res[0]
            t = datetime.datetime.today().date()
            today = int(time.mktime(t.timetuple()))
            # lefttime = (ended_at - int(time.mktime(t.timetuple())))/3600/24
            lefttime = (ended_at - created_at) / 3600 / 24
            if lefttime < 0:
                lefttime = '-1'
            if ended_at < today:
                lefttime = '-1'
                # created_at, ended_at = res[0]
                # lefttime = (ended_at - created_at)/24/3600
        defer.returnValue(lefttime)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_card(self, user, gid):
        is_first = 0
        t = datetime.datetime.today().date()
        timestamp = int(time.mktime(t.timetuple()))
        res = yield self.sql.runQuery("SELECT created_at, ended_at FROM core_card WHERE user_id=%s AND gid=%s LIMIT 1",
                                      (user['uid'], gid))
        if res:
            created_at, ended_at = res[0]
            if timestamp >= created_at and timestamp < ended_at:
                created_at = created_at
                ended_at = ended_at + 30 * 24 * 3600
            if timestamp >= ended_at:
                created_at = timestamp
                ended_at = timestamp + 30 * 24 * 3600
                is_first = 1
            if timestamp < created_at:
                created_at = created_at
                ended_at = ended_at + 30 * 24 * 3600
            query = "UPDATE core_card SET created_at=%s, ended_at=%s WHERE user_id=%s AND gid=%s RETURNING id"
            params = (created_at, ended_at, user['uid'], gid)
            lefttime = (ended_at - created_at) / 24 / 3600
            for i in range(5):
                try:
                    cid = yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        else:
            is_first = 1
            query = "INSERT INTO core_card(user_id, gid, created_at, ended_at) VALUES (%s, %s, %s, %s) RETURNING id"
            created_at = timestamp
            ended_at = created_at + 30 * 24 * 3600
            lefttime = (ended_at - created_at) / 24 / 3600
            params = (user['uid'], gid, created_at, ended_at)
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        defer.returnValue([lefttime, is_first])

    @storage.databaseSafe
    @defer.inlineCallbacks
    def draw_card(self, user):
        lefttime = 0
        # t = datetime.datetime.today().date()
        tomorrow = (datetime.datetime.today() + datetime.timedelta(days=1)).date()
        timestamp = int(time.mktime(tomorrow.timetuple()))
        res = yield self.sql.runQuery("SELECT created_at, ended_at FROM core_card WHERE user_id=%s LIMIT 1",
                                      (user['uid'],))
        if res:
            created_at, ended_at = res[0]
            if timestamp >= created_at and timestamp < ended_at:
                query = "UPDATE core_card SET created_at=%s, ended_at=%s WHERE user_id=%s RETURNING id"
                created_at = timestamp  # + 24*3600
                params = (created_at, ended_at, user['uid'])
                lefttime = (ended_at - created_at) / 24 / 3600
                for i in range(5):
                    try:
                        cid = yield self.sql.runQuery(query, params)
                        break
                    except storage.IntegrityError:
                        log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                        continue

        defer.returnValue(lefttime)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def send_hebdomail(self, user, day):
        mail = None
        if day == 1:
            mail = D.HEBDOMAIL1
        elif day == 2:
            mail = D.HEBDOMAIL2
        elif day == 3:
            mail = D.HEBDOMAIL3
        elif day == 4:
            mail = D.HEBDOMAIL4
        elif day == 5:
            mail = D.HEBDOMAIL5
        elif day == 6:
            mail = D.HEBDOMAIL6
        elif day == 7:
            mail = D.HEBDOMAIL7
        else:
            pass
        if mail:
            yield self.send_mails(mail['sender'], user['uid'], mail['title'], mail['content'], mail['jawards'])
            yield self.predis.set('hebdo:%s:%s:%s' % (ZONE_ID, user['uid'], day), E.true)
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_buyrecord(self, user, gid):
        res = yield self.sql.runQuery("SELECT * FROM core_buyrecord WHERE user_id=%s LIMIT 1", (user['uid'],))
        if not res:
            mail = D.TRIOMAIL
            yield self.send_mails(mail['sender'], user['uid'], mail['title'], mail['content'], mail['jawards'])

        query = "INSERT INTO core_buyrecord(user_id, gid, created_at) VALUES (%s, %s, %s) RETURNING id"
        params = (user['uid'], gid, int(time.time()))
        for i in range(5):
            try:
                rid = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(rid)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def first_payrecord(self, uid):
        putao = yield self.sql.runQuery("SELECT * FROM core_payrecord WHERE user_id=%s LIMIT 1", (uid,))
        ali = yield self.sql.runQuery("SELECT * FROM core_alipayrecord WHERE user_id=%s LIMIT 1", (uid,))
        xm = yield self.sql.runQuery("SELECT * FROM core_xmpayrecord WHERE user_id=%s LIMIT 1", (uid,))
        dangbei = yield self.sql.runQuery("SELECT * FROM core_dangbeipayrecord WHERE user_id=%s LIMIT 1", (uid,))
        letv = yield self.sql.runQuery("SELECT * FROM core_letvpayrecord WHERE user_id=%s LIMIT 1", (uid,))
        atet = yield self.sql.runQuery("SELECT * FROM core_atetpayrecord WHERE user_id=%s LIMIT 1", (uid,))
        cm = yield self.sql.runQuery("SELECT * FROM core_cmpayrecord WHERE user_id=%s AND hret='0' LIMIT 1", (uid,))
        lg = yield self.sql.runQuery("SELECT * FROM core_lgpayrecord WHERE user_id=%s LIMIT 1", (uid,))
        if putao or ali or xm or dangbei or letv or cm or lg or atet:
            status = 1
        else:
            status = 0
        defer.returnValue(status)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_payrecord(self, uid, pid, trans_no, result, trade_time, amount, currency):
        # res = yield self.sql.runQuery("SELECT * FROM core_payrecord WHERE user_id=%s LIMIT 1", (uid, ))
        status = yield self.first_payrecord(uid)
        if not status:
            mail = D.PAYMAIL
            yield self.send_mails(mail['sender'], uid, mail['title'], mail['content'], mail['jawards'])

        query = "INSERT INTO core_payrecord(user_id, pid, trans_no, result, trade_time, amount, currency, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
        params = (uid, pid, str(trans_no), str(result), trade_time, amount, str(currency), int(time.time()))
        for i in range(5):
            try:
                rid = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(rid)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_alipayrecord(self, uid, pid, app_order_id, coin_order_id, consume_amount, credit_amount, Ts, is_success,
                         error_code, sign):
        # res = yield self.sql.runQuery("SELECT * FROM core_alipayrecord WHERE user_id=%s LIMIT 1", (uid, ))
        # if not res:
        status = yield self.first_payrecord(uid)
        if not status:
            mail = D.PAYMAIL
            yield self.send_mails(mail['sender'], uid, mail['title'], mail['content'], mail['jawards'])
        res = yield self.sql.runQuery("SELECT * FROM core_alipayrecord WHERE app_order_id=%s", (app_order_id,))
        if not res:
            query = "INSERT INTO core_alipayrecord(user_id, pid, app_order_id, coin_order_id, consume_amount, credit_amount, ts,\
             is_success, error_code, sign, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
            params = (
                uid, pid, app_order_id, coin_order_id, consume_amount, credit_amount, Ts, is_success, error_code, sign, \
                int(time.time()))
            # print query % params
            for i in range(5):
                try:
                    rid = yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        else:
            rid = None
        defer.returnValue(rid)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_xmpayrecord(self, uid, pid, orderId, orderStatus, payFee, payTime):
        # res = yield self.sql.runQuery("SELECT * FROM core_xmpayrecord WHERE user_id=%s LIMIT 1", (uid, ))
        # if not res:
        status = yield self.first_payrecord(uid)
        if not status:
            mail = D.PAYMAIL
            yield self.send_mails(mail['sender'], uid, mail['title'], mail['content'], mail['jawards'])

        query = "INSERT INTO core_xmpayrecord(user_id, pid, app_order_id, orderstatus, payfee, paytime, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id"
        params = (uid, pid, orderId, orderStatus, payFee, payTime, int(time.time()))
        for i in range(5):
            try:
                rid = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(rid)

    @defer.inlineCallbacks
    def set_dangbeipayrecord(self, uid, app_order_id, pid, extra, fee, out_trade_no, state):
        # res = yield self.sql.runQuery("SELECT * FROM core_dangbeipayrecord WHERE user_id=%s LIMIT 1", (uid, ))
        # if not res:
        status = yield self.first_payrecord(uid)
        if not status:
            mail = D.PAYMAIL
            yield self.send_mails(mail['sender'], uid, mail['title'], mail['content'], mail['jawards'])

        query = "INSERT INTO core_dangbeipayrecord(user_id, pid, app_order_id, state ,fee, out_trade_no, extra,\
         paied_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
        params = (uid, pid, app_order_id, state, fee, out_trade_no, extra, int(time.time()))
        for i in range(5):
            try:
                rid = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(rid)

    @defer.inlineCallbacks
    def set_atetpayrecord(self, uid, app_order_id, pid, exOrderno, amount, counts, paypoint, paytype, cpprivateinfo,
                          result):
        status = yield self.first_payrecord(uid)
        if not status:
            mail = D.PAYMAIL
            yield self.send_mails(mail['sender'], uid, mail['title'], mail['content'], mail['jawards'])

        query = "INSERT INTO core_atetpayrecord(user_id, pid, app_order_id, result ,amount,counts,paypoint, exorderno, cpprivateinfo,paytype,\
         paied_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
        params = (
            uid, pid, app_order_id, result, amount, counts, paypoint, exOrderno, cpprivateinfo, paytype,
            int(time.time()))
        for i in range(5):
            try:
                rid = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                raise
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(rid)

    @defer.inlineCallbacks
    def set_letvpayrecord(self, uid, app_order_id, externalProductId, total, quantity):
        # res = yield self.sql.runQuery("SELECT * FROM core_letvpayrecord WHERE user_id=%s LIMIT 1", (uid, ))
        # if not res:
        status = yield self.first_payrecord(uid)
        if not status:
            mail = D.PAYMAIL
            yield self.send_mails(mail['sender'], uid, mail['title'], mail['content'], mail['jawards'])

        query = "INSERT INTO core_letvpayrecord(user_id, pid, app_order_id, total, quantity,\
         created_at) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id"
        params = (uid, externalProductId, app_order_id, total, quantity, int(time.time()))
        for i in range(5):
            try:
                rid = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(rid)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_cmpayrecord(self, uid, pid, amount, orderId, contentId, consumeCode, cpid, hRet):
        # res = yield self.sql.runQuery("SELECT * FROM core_cmpayrecord WHERE user_id=%s LIMIT 1", (uid, ))
        # if not res:
        status = yield self.first_payrecord(uid)
        if not status and hRet == '0':
            mail = D.PAYMAIL
            yield self.send_mails(mail['sender'], uid, mail['title'], mail['content'], mail['jawards'])

        query = "INSERT INTO core_cmpayrecord(user_id, pid, amount, app_order_id, contentid, consumecode, cpid,\
         hret, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
        params = (uid, pid, amount, orderId, contentId, consumeCode, cpid, hRet, int(time.time()))
        for i in range(5):
            try:
                rid = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(rid)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_lgpayrecord(self, uid, pid, app_order_id, transaction_id, fee):
        # res = yield self.sql.runQuery("SELECT * FROM core_lgpayrecord WHERE user_id=%s LIMIT 1", (uid, ))
        # if not res:
        status = yield self.first_payrecord(uid)
        if not status:
            mail = D.PAYMAIL
            yield self.send_mails(mail['sender'], uid, mail['title'], mail['content'], mail['jawards'])

        query = "INSERT INTO core_lgpayrecord(user_id, pid, app_order_id, transaction_id, fee,\
         created_at) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id"
        params = (uid, pid, app_order_id, transaction_id, fee, int(time.time()))
        for i in range(5):
            try:
                rid = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(rid)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_payrecord(self, user, rockstore):
        payrecords = {}
        for i in xrange(0, len(rockstore) / 8):
            res = yield self.sql.runQuery("select created_at from core_payrecord where user_id=%s and pid=%s limit 1",
                                          (user['uid'], rockstore[i * 8]))
            lefttime = '-1'
            if res:
                if rockstore[i * 8 + 2] == 0:
                    if rockstore[i * 8 + 3] == 1:
                        res = yield self.sql.runQuery(
                            "SELECT created_at, ended_at FROM core_card WHERE user_id=%s AND gid=%s LIMIT 1",
                            (user['uid'], rockstore[i * 8]))
                        if res:
                            created_at, ended_at = res[0]
                            t = datetime.datetime.today().date()
                            lefttime = (ended_at - int(time.mktime(t.timetuple()))) / 3600 / 24
                            if lefttime < 0:
                                lefttime = '-1'
                        payrecords[rockstore[i * 8]] = lefttime

                    elif rockstore[i * 8 + 3] == 2:
                        payrecords[rockstore[i * 8]] = lefttime
                    else:

                        gid, = [rockstore[j * 8] for j in xrange(0, len(rockstore) / 8) if
                                rockstore[j * 8 + 1] == rockstore[i * 8 + 1] and rockstore[j * 8 + 3] == 2]
                        payrecords[gid] = lefttime
            else:
                if rockstore[i * 8 + 2] == 0:
                    payrecords[rockstore[i * 8]] = lefttime
        yield self.predis.set('payrecords:%s:%s' % (ZONE_ID, user['uid']), pickle.dumps(payrecords))
        defer.returnValue(payrecords)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_alipayrecord(self, user, rockstore):
        payrecords = {}
        for i in xrange(0, len(rockstore) / 8):
            res = yield self.sql.runQuery(
                "select created_at from core_alipayrecord where user_id=%s and pid=%s limit 1",
                (user['uid'], rockstore[i * 8]))
            lefttime = '-1'
            if res:
                if rockstore[i * 8 + 2] == 0:
                    if rockstore[i * 8 + 3] == 1:
                        res = yield self.sql.runQuery(
                            "SELECT created_at, ended_at FROM core_card WHERE user_id=%s AND gid=%s LIMIT 1",
                            (user['uid'], rockstore[i * 8]))
                        if res:
                            created_at, ended_at = res[0]
                            t = datetime.datetime.today().date()
                            lefttime = (ended_at - int(time.mktime(t.timetuple()))) / 3600 / 24
                            if lefttime < 0:
                                lefttime = '-1'
                        payrecords[rockstore[i * 8]] = lefttime

                    elif rockstore[i * 8 + 3] == 2:
                        payrecords[rockstore[i * 8]] = lefttime
                    else:

                        gid, = [rockstore[j * 8] for j in xrange(0, len(rockstore) / 8) if
                                rockstore[j * 8 + 1] == rockstore[i * 8 + 1] and rockstore[j * 8 + 3] == 2]
                        payrecords[gid] = lefttime
            else:
                if rockstore[i * 8 + 2] == 0:
                    payrecords[rockstore[i * 8]] = lefttime
        yield self.predis.set('payrecords:%s:%s' % (ZONE_ID, user['uid']), pickle.dumps(payrecords))
        defer.returnValue(payrecords)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_xmpayrecord(self, user, rockstore):
        payrecords = {}
        for i in xrange(0, len(rockstore) / 8):
            res = yield self.sql.runQuery("select created_at from core_xmpayrecord where user_id=%s and pid=%s limit 1",
                                          (user['uid'], rockstore[i * 8]))
            lefttime = '-1'
            if res:
                if rockstore[i * 8 + 2] == 0:
                    if rockstore[i * 8 + 3] == 1:
                        res = yield self.sql.runQuery(
                            "SELECT created_at, ended_at FROM core_card WHERE user_id=%s AND gid=%s LIMIT 1",
                            (user['uid'], rockstore[i * 8]))
                        if res:
                            created_at, ended_at = res[0]
                            t = datetime.datetime.today().date()
                            lefttime = (ended_at - int(time.mktime(t.timetuple()))) / 3600 / 24
                            if lefttime < 0:
                                lefttime = '-1'
                        payrecords[rockstore[i * 8]] = lefttime

                    elif rockstore[i * 8 + 3] == 2:
                        payrecords[rockstore[i * 8]] = lefttime
                    else:

                        gid, = [rockstore[j * 8] for j in xrange(0, len(rockstore) / 8) if
                                rockstore[j * 8 + 1] == rockstore[i * 8 + 1] and rockstore[j * 8 + 3] == 2]
                        payrecords[gid] = lefttime
            else:
                if rockstore[i * 8 + 2] == 0:
                    payrecords[rockstore[i * 8]] = lefttime
        yield self.predis.set('payrecords:%s:%s' % (ZONE_ID, user['uid']), pickle.dumps(payrecords))
        defer.returnValue(payrecords)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_letvpayrecord(self, user, rockstore):
        payrecords = {}
        for i in xrange(0, len(rockstore) / 8):
            res = yield self.sql.runQuery(
                "select created_at from core_letvpayrecord where user_id=%s and pid=%s limit 1",
                (user['uid'], rockstore[i * 8]))
            lefttime = '-1'
            if res:
                if rockstore[i * 8 + 2] == 0:
                    if rockstore[i * 8 + 3] == 1:
                        res = yield self.sql.runQuery(
                            "SELECT created_at, ended_at FROM core_card WHERE user_id=%s AND gid=%s LIMIT 1",
                            (user['uid'], rockstore[i * 8]))
                        if res:
                            created_at, ended_at = res[0]
                            t = datetime.datetime.today().date()
                            lefttime = (ended_at - int(time.mktime(t.timetuple()))) / 3600 / 24
                            if lefttime < 0:
                                lefttime = '-1'
                        payrecords[rockstore[i * 8]] = lefttime

                    elif rockstore[i * 8 + 3] == 2:
                        payrecords[rockstore[i * 8]] = lefttime
                    else:

                        gid, = [rockstore[j * 8] for j in xrange(0, len(rockstore) / 8) if
                                rockstore[j * 8 + 1] == rockstore[i * 8 + 1] and rockstore[j * 8 + 3] == 2]
                        payrecords[gid] = lefttime
            else:
                if rockstore[i * 8 + 2] == 0:
                    payrecords[rockstore[i * 8]] = lefttime
        yield self.predis.set('payrecords:%s:%s' % (ZONE_ID, user['uid']), pickle.dumps(payrecords))
        defer.returnValue(payrecords)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_cmpayrecord(self, user, rockstore):
        payrecords = {}
        for i in xrange(0, len(rockstore) / 8):
            res = yield self.sql.runQuery("select created_at from core_cmpayrecord where user_id=%s and pid=%s limit 1",
                                          (user['uid'], rockstore[i * 8]))
            lefttime = '-1'
            if res:
                if rockstore[i * 8 + 2] == 0:
                    if rockstore[i * 8 + 3] == 1:
                        res = yield self.sql.runQuery(
                            "SELECT created_at, ended_at FROM core_card WHERE user_id=%s AND gid=%s LIMIT 1",
                            (user['uid'], rockstore[i * 8]))
                        if res:
                            created_at, ended_at = res[0]
                            t = datetime.datetime.today().date()
                            lefttime = (ended_at - int(time.mktime(t.timetuple()))) / 3600 / 24
                            if lefttime < 0:
                                lefttime = '-1'
                        payrecords[rockstore[i * 8]] = lefttime

                    elif rockstore[i * 8 + 3] == 2:
                        payrecords[rockstore[i * 8]] = lefttime
                    else:

                        gid, = [rockstore[j * 8] for j in xrange(0, len(rockstore) / 8) if
                                rockstore[j * 8 + 1] == rockstore[i * 8 + 1] and rockstore[j * 8 + 3] == 2]
                        payrecords[gid] = lefttime
            else:
                if rockstore[i * 8 + 2] == 0:
                    payrecords[rockstore[i * 8]] = lefttime
        yield self.predis.set('payrecords:%s:%s' % (ZONE_ID, user['uid']), pickle.dumps(payrecords))
        defer.returnValue(payrecords)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_lgpayrecord(self, user, rockstore):
        payrecords = {}
        for i in xrange(0, len(rockstore) / 8):
            res = yield self.sql.runQuery("select created_at from core_lgpayrecord where user_id=%s and pid=%s limit 1",
                                          (user['uid'], rockstore[i * 8]))
            lefttime = '-1'
            if res:
                if rockstore[i * 8 + 2] == 0:
                    if rockstore[i * 8 + 3] == 1:
                        res = yield self.sql.runQuery(
                            "SELECT created_at, ended_at FROM core_card WHERE user_id=%s AND gid=%s LIMIT 1",
                            (user['uid'], rockstore[i * 8]))
                        if res:
                            created_at, ended_at = res[0]
                            t = datetime.datetime.today().date()
                            lefttime = (ended_at - int(time.mktime(t.timetuple()))) / 3600 / 24
                            if lefttime < 0:
                                lefttime = '-1'
                        payrecords[rockstore[i * 8]] = lefttime

                    elif rockstore[i * 8 + 3] == 2:
                        payrecords[rockstore[i * 8]] = lefttime
                    else:
                        gid, = [rockstore[j * 8] for j in xrange(0, len(rockstore) / 8) if
                                rockstore[j * 8 + 1] == rockstore[i * 8 + 1] and rockstore[j * 8 + 3] == 2]
                        payrecords[gid] = lefttime
            else:
                if rockstore[i * 8 + 2] == 0:
                    payrecords[rockstore[i * 8]] = lefttime
        yield self.predis.set('payrecords:%s:%s' % (ZONE_ID, user['uid']), pickle.dumps(payrecords))
        defer.returnValue(payrecords)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_huntrecord(self, user, cid, awards):
        query = "INSERT INTO core_huntresult(winner_id, loser_id, jawards, timestamp) VALUES (%s, %s, %s, %s) RETURNING id"
        params = (user['uid'], cid, escape.json_encode(awards), int(time.time()))
        for i in range(5):
            try:
                rid = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_soulbox(self, uid):
        weekday = datetime.date.today().weekday()
        res = yield self.sql.runQuery("SELECT type, prod, rock FROM core_soulbox WHERE week=%s", (weekday,))
        box = []
        if res:
            for r in res:
                box.append(dict(type=r[0], prod=r[1].zfill(5), rock=r[2]))
        defer.returnValue(box)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_beautys(self, user):
        res = yield self.sql.runQuery("SELECT beautyid FROM core_beauty")
        beautys = {}
        for r in res:
            if r[0] in user['beautys']:
                beautys[r[0]] = user['beautys'][r[0]]
            else:
                beautys[r[0]] = -1
        defer.returnValue(beautys)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_code(self, user, code):
        query = "UPDATE core_code SET type=%s, user_id=%s WHERE code=%s RETURNING id"
        params = (E.used, user['uid'], code)
        for i in range(5):
            try:
                yield self.sql.runOperation(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_rockstore(self, channel_id):
        res = yield self.sql.runQuery("SELECT pid, code, sequence, type, value, extra, times, price FROM core_product_channels AS a,\
         core_product AS b WHERE a.product_id=b.id AND a.channel_id=%s", (channel_id,))
        rockstore = []
        for r in res:
            rockstore.extend(list(r))
        defer.returnValue(rockstore)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_dayrecharge(self, user, channel):
        if channel == 'putaogame':
            query = "SELECT SUM(c.value) FROM core_payrecord AS a, core_account AS b,\
             core_product AS c WHERE a.user_id=b.user_id AND a.pid=c.pid AND a.user_id=%s AND to_timestamp(a.created_at)::date=%s"

        elif channel == 'pt_xiaomi':
            query = "SELECT SUM(c.value) FROM core_xmpayrecord AS a, core_account AS b,\
             core_product AS c WHERE a.user_id=b.user_id AND a.pid=c.pid AND a.user_id=%s AND to_timestamp(a.created_at)::date=%s"

        elif channel == 'pt_letv':
            query = "SELECT SUM(c.value) FROM core_letvpayrecord AS a, core_account AS b,\
             core_product AS c WHERE a.user_id=b.user_id AND a.pid=c.pid AND a.user_id=%s AND to_timestamp(a.created_at)::date=%s"

        elif channel == 'pt_chinamobile':
            query = "SELECT SUM(c.value) FROM core_cmpayrecord AS a, core_account AS b,\
             core_product AS c WHERE a.user_id=b.user_id AND a.pid=c.pid AND a.user_id=%s AND to_timestamp(a.created_at)::date=%s"

        elif channel == 'pt_lovegame':
            query = "SELECT SUM(c.value) FROM core_lgpayrecord AS a, core_account AS b,\
             core_product AS c WHERE a.user_id=b.user_id AND a.pid=c.pid AND a.user_id=%s AND to_timestamp(a.created_at)::date=%s"

        elif channel == 'pt_ali':
            query = "SELECT SUM(c.value) FROM core_alipayrecord AS a, core_account AS b,\
             core_product AS c WHERE a.user_id=b.user_id AND a.pid=c.pid AND a.user_id=%s AND to_timestamp(a.created_at)::date=%s"
        elif channel == 'atet':
            query = "SELECT SUM(c.value) FROM core_atetpayrecord AS a, core_account AS b,\
             core_product AS c WHERE a.user_id=b.user_id AND a.pid=c.pid AND a.user_id=%s AND to_timestamp(a.paied_at)::date=%s"

        elif channel == 'dangbei':
            query = "SELECT SUM(c.value) FROM core_dangbeipayrecord AS a, core_account AS b,\
             core_product AS c WHERE a.user_id=b.user_id AND a.pid=c.pid AND a.user_id=%s AND to_timestamp(a.paied_at)::date=%s"
        else:
            query = "SELECT SUM(c.value) FROM core_payrecord AS a, core_account AS b,\
             core_product AS c WHERE a.user_id=b.user_id AND a.pid=c.pid AND a.user_id=%s AND to_timestamp(a.created_at)::date=%s"
        params = (user['uid'], str(datetime.datetime.today().date()))
        res = yield self.sql.runQuery(query, params)
        amount, = res[0]
        if not amount:
            amount = 0
        res = yield self.sql.runQuery("SELECT a.rid, a.total, a.created_at, a.ended_at FROM core_dayrecharge AS a, core_dayrecharge_channels AS b,\
         core_channel as c WHERE b.channel_id=c.id AND a.id=b.dayrecharge_id AND c.slug=%s", (channel,))
        if res:
            for r in res:
                rid, total, created_at, ended_at = r
                created_at = int(time.mktime(created_at.timetuple()))
                ended_at = int(time.mktime(ended_at.timetuple()))
                now = int(time.mktime(datetime.datetime.now().timetuple()))
                recharge = yield self.predis.get(
                    'recharge:%s:%s:%s:%s' % (ZONE_ID, user['uid'], rid, str(datetime.datetime.today().date())))
                if now >= created_at and now <= ended_at:
                    if int(total) <= int(amount):
                        if not recharge:
                            status = 0
                        elif recharge == -1:
                            status = 0
                        else:
                            status = recharge
                    else:
                        if recharge:
                            status = recharge
                        else:
                            status = -1
                    yield self.predis.set(
                        'recharge:%s:%s:%s:%s' % (ZONE_ID, user['uid'], rid, str(datetime.datetime.today().date())),
                        status)
        defer.returnValue(amount)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_expedition(self, user):
        uid = user['uid']
        sword = E.calc_topsword(user)
        # print uid, sword
        expedition = yield self.predis.hget("expeditions:%s" % ZONE_ID, uid)
        expedzuids = yield self.predis.hget("expedzuids:%s" % ZONE_ID, uid)
        reset = yield self.redis.get('expedresets:%s' % uid)
        if not reset:
            left_times = E.expedmaxtimes(user['vrock'])
        else:
            left_times = E.expedmaxtimes(user['vrock']) - reset
            if left_times < 0:
                left_times = 0
        if not expedzuids:
            zuid_list = []
        else:
            zuid_list = pickle.loads(expedzuids)
        if expedition:
            expedition = pickle.loads(expedition)
            expedition['reset'] = left_times
        else:
            all_expedition = yield self.predis.get('all:expedition:match')
            # print datetime.datetime.now()
            if all_expedition:
                all_expedition = pickle.loads(all_expedition)
                comps = {}
                for ex in all_expedition:
                    if ex['mode'] == 1:
                        min, max = ex['rule'].split(':')
                        if sword >= int(min) and sword <= int(max):
                            for key, value in ex['opponents'].items():
                                # print key, value
                                log.msg("expedition uid %s sword %s, key is %s, value lens is %s" % (
                                    uid, sword, key, len(value)))
                                if value:
                                    for i in xrange(1, 11):
                                        cuid = random.choice(value)
                                        if isinstance(cuid, basestring):
                                            if (cuid in zuid_list) and (i != 10):
                                                continue
                                            else:
                                                cuser = yield self.predis.hget('all:users', cuid)
                                                cuser = pickle.loads(cuser)
                                                out = {
                                                    'zuid': cuser['id'],
                                                    'nickname': cuser['nickname'],
                                                    'avat': cuser['avat'],
                                                    'xp': cuser['xp'],
                                                    'heros': {hid: cuser['heros'][hid] for hid in cuser['tophids']},
                                                    'beautys': cuser['beautys'],
                                                    'positions': cuser['toppositions'],
                                                    'formation': cuser['topformation']
                                                }
                                                cuser = out
                                                zuid_list.append(cuid)
                                                break
                                        else:
                                            if (cuid['zuid'] in zuid_list) and (i != 10):
                                                continue
                                            else:
                                                cuser = cuid
                                                zuid_list.append(cuser['zuid'])
                                                break
                                    for hero in cuser['heros'].keys():
                                        cuser['heros'][hero]['blood'] = 0
                                        cuser['heros'][hero]['gas'] = 0
                                    comps[key] = cuser
                # print 'all_expedition', all_expedition
                # print 'comps', comps
                heros = user['heros']
                our = {hid: dict(blood=0, gas=0) for hid in heros}
                our['exped_coin'] = yield self.get_expedcoin(user)
                expedition = dict(our=our, comps=comps, reset=left_times)
                print datetime.datetime.now()
                yield self.predis.hset("expeditions:%s" % ZONE_ID, uid, pickle.dumps(expedition))
                yield self.predis.hset("expedzuids:%s" % ZONE_ID, uid, pickle.dumps(zuid_list))
            else:
                expedition = {}

        defer.returnValue(expedition)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_expedition(self, user, label, our, comps):
        expedition = yield self.get_expedition(user)
        expedition['our'] = our
        cuser = expedition['comps'][label]
        for key, value in comps.items():
            if key in cuser['heros']:
                cuser['heros'][key]['blood'] = value['blood']
                cuser['heros'][key]['gas'] = value['gas']
        yield self.predis.hset("expeditions:%s" % ZONE_ID, user['uid'], pickle.dumps(expedition))
        defer.returnValue(expedition)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_expedcoin(self, user, exped_coin):
        res = yield self.sql.runQuery("SELECT * FROM core_userexped WHERE user_id=%s", (user['uid'],))
        if res:
            query = "UPDATE core_userexped SET exped_coin=exped_coin+%s WHERE user_id=%s RETURNING exped_coin"
            params = (exped_coin, user['uid'])
        else:
            query = "INSERT INTO core_userexped (user_id, exped_coin) VALUES (%s, %s) RETURNING exped_coin"
            params = (user['uid'], exped_coin)
        res = yield self.sql.runQuery(query, params)
        exped_coin, = res[0]
        defer.returnValue(exped_coin)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_expedcoin(self, user):
        res = yield self.sql.runQuery("SELECT exped_coin FROM core_userexped WHERE user_id=%s LIMIT 1", (user['uid'],))
        if res:
            exped_coin, = res[0]
        else:
            query = "INSERT INTO core_userexped (user_id, exped_coin) VALUES (%s, %s) RETURNING exped_coin"
            params = (user['uid'], 0)
            res = yield self.sql.runQuery(query, params)
            exped_coin, = res[0]
        defer.returnValue(exped_coin)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def open_market(self, user, times):
        market = 0
        uid = user['uid']
        marketopen = yield self.redis.get('marketopen:%s' % uid)
        if E.vip(user['vrock']) < 9 and not marketopen:
            marketseed = yield self.predis.get('marketseed')
            if not marketseed:
                marketseed = random.randint(40, 51)
                yield self.predis.set('marketseed', marketseed)
            batttimes = (yield self.predis.hget("batttimes:%s" % ZONE_ID, uid)) or 0
            if not batttimes:
                batttimes = 0
            if ((batttimes + 1 * times) == marketseed) or (
                            batttimes < marketseed and (batttimes + 1 * times) > marketseed):
                market = 1
                yield self.redis.setex('market:%s' % uid, 3600, int(time.time()) + 3600)
                yield self.redis.delete('marketprod:%s' % uid)
                yield self.redis.set('marketopen:%s' % uid, market)
                # print 'batttimes', batttimes+1*times, marketseed
        yield self.predis.hincrby("batttimes:%s" % ZONE_ID, uid, 1 * times)
        defer.returnValue(market)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def open_bmmarket(self, user, times):
        blackmarket = 0
        uid = user['uid']
        bmopen = yield self.redis.get('bmopen:%s' % uid)
        if E.vip(user['vrock']) < 11 and not bmopen:
            bmseed = yield self.predis.get('bmseed')
            if not bmseed:
                bmseed = random.randint(12, 16)
                yield self.predis.set('bmseed', bmseed)
            hardbatttimes = (yield self.predis.hget("hardbatttimes:%s" % ZONE_ID, uid)) or 0
            if not hardbatttimes:
                hardbatttimes = 0
            if (hardbatttimes + 1 * times) == bmseed or (
                            hardbatttimes < bmseed and (hardbatttimes + 1 * times) > bmseed):
                blackmarket = 1
                yield self.redis.setex("blackmarket:%s" % uid, 3600, int(time.time()) + 3600)
                yield self.redis.delete('bmprod:%s' % uid)
                yield self.redis.set('bmopen:%s' % uid, blackmarket)
                # print 'hardbatttimes', hardbatttimes+1*times, bmseed
        yield self.predis.hincrby("hardbatttimes:%s" % ZONE_ID, uid, 1 * times)
        defer.returnValue(blackmarket)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_consume(self, user):
        consume = {}
        event = yield self.sql.runQuery("SELECT DISTINCT a.bid, a.created_at, a.ended_at FROM core_bigevent AS a,\
          core_consume AS b WHERE a.id=b.bigevent_id ORDER BY a.bid")
        for e in event:
            bid, created_at, ended_at = e
            created_at = int(time.mktime(created_at.timetuple()))
            ended_at = int(time.mktime(ended_at.timetuple()))
            now = int(time.mktime(datetime.datetime.now().timetuple()))
            if now >= created_at and now <= ended_at:
                res = yield self.sql.runQuery(
                    "SELECT SUM(rock) FROM core_userconsume WHERE user_id=%s AND bid=%s LIMIT 1", \
                    (user['uid'], bid))
                if res:
                    rock, = res[0]
                    if not rock:
                        rock = 0
                else:
                    rock = 0
                consume[bid] = int(rock)

        defer.returnValue(consume)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_consume(self, user, rock):
        event = yield self.sql.runQuery("SELECT DISTINCT a.bid, a.created_at, a.ended_at FROM core_bigevent AS a,\
            core_consume AS b WHERE a.id=b.bigevent_id ORDER BY a.bid")
        for e in event:
            bid, created_at, ended_at = e
            created_at = int(time.mktime(created_at.timetuple()))
            ended_at = int(time.mktime(ended_at.timetuple()))
            now = int(time.mktime(datetime.datetime.now().timetuple()))
            if now >= created_at and now <= ended_at:
                query = "INSERT INTO core_userconsume (user_id, bid, rock) VALUES (%s, %s, %s) RETURNING id"
                params = (user['uid'], bid, rock)
                for i in range(5):
                    try:
                        yield self.sql.runQuery(query, params)
                        break
                    except storage.IntegrityError:
                        log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                        continue
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_consumeresult(self, user, bid, rid):
        res = yield self.sql.runQuery("SELECT * FROM core_userconsumerecord WHERE user_id=%s AND bid=%s AND rid=%s", \
                                      (user['uid'], bid, rid))
        if not res:
            query = "INSERT INTO core_userconsumerecord (user_id, bid, rid) VALUES (%s, %s, %s) RETURNING id"
            params = (user['uid'], bid, rid)
            for i in range(5):
                try:
                    rock = yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_propexchange(self, user, rid):
        res = yield self.sql.runQuery("SELECT * FROM core_userpropexchange WHERE user_id=%s AND rid=%s",
                                      (user['uid'], rid))
        if res:
            query = "UPDATE core_userpropexchange SET times=times+1 WHERE user_id=%s AND rid=%s RETURNING times"
            params = (user['uid'], rid)
        else:
            query = "INSERT INTO core_userpropexchange (user_id, rid, times) VALUES (%s, %s, %s) RETURNING times"
            params = (user['uid'], rid, 1)
        res = yield self.sql.runQuery(query, params)
        if res:
            times, = res[0]
        else:
            times = 0
        defer.returnValue(times)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_inpour(self, user, rock):
        event = yield self.sql.runQuery("SELECT DISTINCT ON (a.bid)a.bid, a.created_at, a.ended_at, b.rid FROM core_bigevent AS a,\
          core_inpour AS b WHERE a.id=b.bigevent_id ORDER BY a.bid")
        for e in event:
            bid, created_at, ended_at, rid = e
            created_at = int(time.mktime(created_at.timetuple()))
            ended_at = int(time.mktime(ended_at.timetuple()))
            now = int(time.mktime(datetime.datetime.now().timetuple()))
            if now >= created_at and now <= ended_at:
                query = "INSERT INTO core_userinpour (user_id, bid, rock) VALUES (%s, %s, %s) RETURNING id"
                params = (user['uid'], bid, rock)
                for i in range(5):
                    try:
                        yield self.sql.runQuery(query, params)
                        break
                    except storage.IntegrityError:
                        log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                        continue
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_inpour(self, user):
        event = yield self.sql.runQuery("SELECT DISTINCT ON (a.bid)a.bid, a.created_at, a.ended_at, b.rid FROM core_bigevent AS a,\
          core_inpour AS b WHERE a.id=b.bigevent_id ORDER BY a.bid")
        inpour = {}
        for e in event:
            bid, created_at, ended_at, rid = e
            created_at = int(time.mktime(created_at.timetuple()))
            ended_at = int(time.mktime(ended_at.timetuple()))
            now = int(time.mktime(datetime.datetime.now().timetuple()))
            if now >= created_at and now <= ended_at:
                res = yield self.sql.runQuery(
                    "SELECT SUM(rock) FROM core_userinpour WHERE user_id=%s AND bid=%s LIMIT 1", \
                    (user['uid'], bid))
                if res:
                    rock, = res[0]
                    if not rock:
                        rock = 0
                else:
                    rock = 0
                inpour[bid] = int(rock)
        defer.returnValue(inpour)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_inpourresult(self, user, bid, rid):
        res = yield self.sql.runQuery("SELECT * FROM core_userinpourrecord WHERE user_id=%s AND bid=%s AND rid=%s", \
                                      (user['uid'], bid, rid))
        if not res:
            query = "INSERT INTO core_userinpourrecord (user_id, bid, rid) VALUES (%s, %s, %s) RETURNING id"
            params = (user['uid'], bid, rid)
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_zhangfeiresult(self, user, bid):
        res = yield self.sql.runQuery("SELECT * FROM core_userzhangfeirecord WHERE user_id=%s AND bid=%s",
                                      (user['uid'], bid))
        if not res:
            query = "INSERT INTO core_userzhangfeirecord (user_id, bid) VALUES (%s, %s) RETURNING id"
            params = (user['uid'], bid)
            for i in range(5):
                try:
                    rock = yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_versuscoin(self, user, versus_coin):
        res = yield self.sql.runQuery("SELECT state FROM core_userstate WHERE user_id=%s LIMIT 1", (user['uid'],))
        if res:
            query = "update core_userstate set versus_coin=versus_coin+%s WHERE user_id=%s RETURNING versus_coin, state"
            params = (versus_coin, user['uid'])
            for i in range(5):
                try:
                    res = yield self.sql.runQuery(query, params)
                    # print res
                    versus_coin, sid = res[0]
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
            yield self.set_versus(user['uid'], str(sid))
        else:
            query = "INSERT INTO core_userstate (user_id, state, versus_coin, timestamp) VALUES (%s, %s, %s, %s) RETURNING id"
            params = (user['uid'], -1, versus_coin, int(time.time()))
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue

        defer.returnValue(versus_coin)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_versusresult(self, user, cid, result, sid):
        uid = user['uid']
        now_rank = before_rank = 0
        if int(result) == 1:
            query = "SELECT a.now_rank, b.now_rank, a.before_rank, a.last_rank FROM (SELECT user_id, now_rank, before_rank,\
                    last_rank FROM %s" % D.VERSUSSTATE[
                sid] + " WHERE user_id=%s) AS a, " + "(SELECT user_id, now_rank, before_rank FROM %s" % D.VERSUSSTATE[
                sid] + " WHERE user_id=%s) AS b"
            # print 'query', query % (uid, cid)
            res = yield self.sql.runQuery(query, (uid, cid))
            if res:
                for r in res:
                    now_rank, before_rank, last_rank = r[0], r[2], r[3]
                    if r[0] > r[1]:
                        now_rank = r[1]
                        last_rank = r[0]
                        query = "UPDATE %s" % D.VERSUSSTATE[
                            sid] + " SET now_rank=%s, last_rank=%s WHERE user_id=%s  RETURNING id"
                        params = (now_rank, last_rank, uid)
                        for i in range(5):
                            try:
                                yield self.sql.runQuery(query, params)
                                break
                            except storage.IntegrityError:
                                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                                continue
                        query = "UPDATE %s" % D.VERSUSSTATE[sid] + " SET now_rank=%s WHERE user_id=%s RETURNING id"
                        params = (r[0], cid)
                        for i in range(5):
                            try:
                                yield self.sql.runQuery(query, params)
                                break
                            except storage.IntegrityError:
                                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                                continue

            query = "INSERT INTO %s" % "".join([D.VERSUSSTATE[sid],
                                                "result"]) + " (user_id, competitor_id, result, ascend, timestamp) VALUES (%s, %s, %s, %s, %s) RETURNING id"
            params = (uid, cid, result, last_rank - now_rank, int(time.time()))
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
            yield self.set_versus(uid, sid)
            yield self.set_versus(cid, sid)
            defer.returnValue((now_rank, before_rank, last_rank))
        else:
            query = "INSERT INTO %s" % "".join([D.VERSUSSTATE[sid],
                                                "result"]) + " (user_id, competitor_id, result, ascend, timestamp) VALUES (%s, %s, %s, %s, %s) RETURNING id"
            params = (uid, cid, result, 0, int(time.time()))
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
            defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_versusrank(self, user, now_rank, before_rank, last_rank, sid):
        now_rank, before_rank, last_rank = now_rank, before_rank, last_rank
        if now_rank < before_rank:
            query = "UPDATE %s" % D.VERSUSSTATE[sid] + " SET before_rank=%s WHERE user_id=%s RETURNING id"
            params = (now_rank, user['uid'])
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
            rock = E.versusmatch(now_rank, before_rank)
            if rock:
                awards = dict(rock=rock)
            else:
                awards = {}
            yield self.set_mails(user)
            now_rank, before_rank = now_rank, now_rank
        defer.returnValue((now_rank, before_rank, last_rank, awards))

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_versusguard(self, uid, sid, heros1, positions1, formation1, heros2, positions2, formation2):
        jpos1 = dict(zip(heros1, positions1))
        jpos2 = dict(zip(heros2, positions2))
        res = yield self.sql.runQuery(
            "SELECT a.jheros, b.jguards1, b.jpositions1, b.jguards2, b.jpositions2 FROM core_user AS a,"
            " %s AS b" % D.VERSUSSTATE[sid] + " WHERE a.id=b.user_id AND a.id=%s" % uid)
        if res:
            for r in res:
                jheros = r[0] and escape.json_decode(r[0]) or {}
                jguards1 = {}
                jpositions1 = {}
                jguards_list1 = filter(lambda j: j in jheros, heros1)
                for j in jguards_list1:
                    jguards1[j] = jheros[j]
                    jpositions1[j] = jpos1[j]
                jguards2 = {}
                jpositions2 = {}
                jguards_list2 = filter(lambda j: j in jheros, heros2)
                for j in jguards_list2:
                    jguards2[j] = jheros[j]
                    jpositions2[j] = jpos2[j]
                query = "UPDATE %s" % D.VERSUSSTATE[sid] + " SET jguards1=%s, jpositions1=%s, formation1=%s, jguards2=%s,\
                 jpositions2=%s, formation2=%s WHERE user_id=%s RETURNING id"
                params = (escape.json_encode(jguards1), escape.json_encode(jpositions1), formation1, \
                          escape.json_encode(jguards2), escape.json_encode(jpositions2), formation2, uid)
                # print query % params
                for i in range(5):
                    try:
                        yield self.sql.runQuery(query, params)
                        break
                    except storage.IntegrityError:
                        log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                        continue
        yield self.set_versus(uid, sid)
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_versus(self, uid, sid):
        if str(sid) != '-1':
            query = "SELECT a.id, a.id, b.now_rank, a.jheros, b.jguards1, b.formation1, a.xp, a.nickname, a.avat, b.before_rank,\
                     b.last_rank, b.jpositions1, b.timestamp, b.jguards2, b.jpositions2, b.formation2 FROM core_user AS a,\
                     %s AS b WHERE a.id=b.user_id" % D.VERSUSSTATE[sid] + " AND a.id=%s"
            res = yield self.sql.runQuery(query, (uid,))
            if res:
                versus = {r[0]: dict(uid=r[0],
                                     now_rank=r[2],
                                     heros=r[3] and escape.json_decode(r[3]) or {},
                                     guards1=r[4] and escape.json_decode(r[4]) or {},
                                     win_times=0,
                                     formation1=r[5],
                                     xp=r[6],
                                     nickname=r[7],
                                     avat=r[8],
                                     before_rank=r[9],
                                     last_rank=r[10],
                                     positions1=r[11] and escape.json_decode(r[11]) or {},
                                     timestamp=r[12],
                                     guards2=r[13] and escape.json_decode(r[13]) or {},
                                     positions2=r[14] and escape.json_decode(r[14]) or {},
                                     formation2=r[15],
                                     ) for r in res}
                for k, v in versus.iteritems():
                    yield self.redis.set('versus:%s' % k, pickle.dumps(v))
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_versus(self, uid, sid):
        versus = yield self.redis.get('versus:%s' % uid)
        if versus:
            versus = pickle.loads(versus)
            # yield self.set_arena(uid)
        else:
            query = "SELECT a.id, a.id, b.now_rank, a.jheros, b.jguards1, b.formation1, a.xp, a.nickname, a.avat, b.before_rank,\
                     b.last_rank, b.jpositions1, b.timestamp, b.jguards2, b.jpositions2, b.formation2 FROM core_user AS a,\
                     %s AS b" % D.VERSUSSTATE[sid] + " WHERE a.id=b.user_id AND a.id=%s LIMIT 1"
            res = yield self.sql.runQuery(query, (uid,))
            if res:
                for r in res:
                    versus = dict(uid=r[0],
                                  now_rank=r[2],
                                  heros=r[3] and escape.json_decode(r[3]) or {},
                                  guards1=r[4] and escape.json_decode(r[4]) or {},
                                  win_times=0,
                                  formation1=r[5],
                                  xp=r[6],
                                  nickname=r[7],
                                  avat=r[8],
                                  before_rank=r[9],
                                  last_rank=r[10],
                                  positions1=r[11] and escape.json_decode(r[11]) or {},
                                  timestamp=r[12],
                                  guards2=r[13] and escape.json_decode(r[13]) or {},
                                  positions2=r[14] and escape.json_decode(r[14]) or {},
                                  formation2=r[15],
                                  )

            else:
                versus = None
        defer.returnValue(versus)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def random_versus_competitor(self, versus, uid, num, sid):
        # print versus
        versus_rule = []
        now_rank = versus['now_rank']
        for i in xrange(0, len(D.VERSUSRULE) / 8):
            if now_rank >= D.VERSUSRULE[i * 8] and now_rank <= D.VERSUSRULE[i * 8 + 1]:
                versus_rule.extend(
                    [D.VERSUSRULE[i * 8 + 2], D.VERSUSRULE[i * 8 + 3], D.VERSUSRULE[i * 8 + 4], D.VERSUSRULE[i * 8 + 5], \
                     D.VERSUSRULE[i * 8 + 6], D.VERSUSRULE[i * 8 + 7]])
                break
        left = {}
        query = "SELECT user_id, now_rank FROM %s" % D.VERSUSSTATE[sid] + " WHERE user_id<>%s AND now_rank>=%s\
                 AND now_rank<=%s AND now_rank<%s ORDER BY now_rank DESC, RANDOM() DESC limit %s"
        # print query % (uid, versus_rule[0], versus_rule[1], now_rank, num)
        res = yield self.sql.runQuery(query, (uid, versus_rule[0], versus_rule[1], now_rank, num))
        # print res
        for r in res:
            versus = yield self.get_versus(r[0], sid)
            # print 222, r[0], versus
            cuser = yield self.get_user(r[0])
            beautys = yield self.get_beautys(cuser)
            if versus:
                guards1 = {}
                for key in versus['guards1'].keys():
                    guards1[key] = cuser['heros'].get(key, {})
                guards2 = {}
                for key in versus['guards2'].keys():
                    guards2[key] = cuser['heros'].get(key, {})
                left[r[0]] = dict(uid=versus['uid'],
                                  guards1=guards1,
                                  guards2=guards2,
                                  now_rank=versus['now_rank'],
                                  nickname=versus['nickname'],
                                  xp=versus['xp'],
                                  avat=versus['avat'],
                                  win_times=versus['win_times'],
                                  formation1=versus['formation1'],
                                  formation2=versus['formation2'],
                                  positions1=versus['positions1'],
                                  positions2=versus['positions2'],
                                  beautys=beautys)
        # print 'left', left, query, versus_rule[2], versus_rule[3], versus, num
        middle = {}
        # print query % (uid, versus_rule[2], versus_rule[3], now_rank, num)
        res = yield self.sql.runQuery(query, (uid, versus_rule[2], versus_rule[3], now_rank, num))
        # print res
        for r in res:
            versus = yield self.get_versus(r[0], sid)
            # print 'versus', versus
            cuser = yield self.get_user(r[0])
            beautys = yield self.get_beautys(cuser)
            if versus:
                guards1 = {}
                for key in versus['guards1'].keys():
                    guards1[key] = cuser['heros'].get(key, {})
                guards2 = {}
                for key in versus['guards2'].keys():
                    guards2[key] = cuser['heros'].get(key, {})
                middle[r[0]] = dict(uid=versus['uid'],
                                    guards1=guards1,
                                    guards2=guards2,
                                    now_rank=versus['now_rank'],
                                    nickname=versus['nickname'],
                                    xp=versus['xp'],
                                    avat=versus['avat'],
                                    win_times=versus['win_times'],
                                    formation1=versus['formation1'],
                                    formation2=versus['formation2'],
                                    positions1=versus['positions1'],
                                    positions2=versus['positions2'],
                                    beautys=beautys)
        right = {}
        # print query % (uid, versus_rule[4], versus_rule[5], now_rank, num)
        res = yield self.sql.runQuery(query, (uid, versus_rule[4], versus_rule[5], now_rank, num))
        for r in res:
            versus = yield self.get_versus(r[0], sid)
            cuser = yield self.get_user(r[0])
            beautys = yield self.get_beautys(cuser)
            if versus:
                guards1 = {}
                for key in versus['guards1'].keys():
                    guards1[key] = cuser['heros'].get(key, {})
                guards2 = {}
                for key in versus['guards2'].keys():
                    guards2[key] = cuser['heros'].get(key, {})
                right[r[0]] = dict(uid=versus['uid'],
                                   guards1=guards1,
                                   guards2=guards2,
                                   now_rank=versus['now_rank'],
                                   nickname=versus['nickname'],
                                   xp=versus['xp'],
                                   avat=versus['avat'],
                                   win_times=versus['win_times'],
                                   formation1=versus['formation1'],
                                   formation2=versus['formation2'],
                                   positions1=versus['positions1'],
                                   positions2=versus['positions2'],
                                   beautys=beautys)

        competitor = dict(left=left, middle=middle, right=right)
        defer.returnValue(competitor)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_userstate(self, uid):
        res = yield self.sql.runQuery("SELECT state FROM core_userstate WHERE user_id=%s LIMIT 1", (uid,))
        if res:
            state, = res[0]
        else:
            state = -1
        defer.returnValue(state)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def join_state(self, user, sid):
        heros = user['heros']
        guards1 = escape.json_encode({'01001': heros['01001']})
        guards2 = escape.json_encode({'01002': heros['01002']})
        positions1 = escape.json_encode({"01001": "-1"})
        positions2 = escape.json_encode({"01002": "-1"})
        formation1 = 1
        formation2 = 1
        seq = D.VERSUSSTATE[sid] + "_id_seq"
        query = "SELECT * from core_userstate WHERE user_id=%s LIMIT 1"
        params = (user['uid'],)
        res = yield self.sql.runQuery(query, params)
        if res:
            query = "UPDATE core_userstate SET state=%s WHERE user_id=%s RETURNING id"
            params = (sid, user['uid'])
            # print query % params
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        else:
            query = "INSERT INTO core_userstate (user_id, state, versus_coin, timestamp) VALUES (%s, %s, %s, %s) RETURNING id"
            params = (user['uid'], sid, 0, int(time.time()))
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue

        query = "INSERT INTO %s" % D.VERSUSSTATE[sid] + "(user_id, before_rank, now_rank, last_rank, jguards1,\
                jpositions1, formation1, jguards2, jpositions2, formation2, timestamp) VALUES (%s, currval(%s),\
                 currval(%s), currval(%s), %s, %s, %s, %s, %s, %s, %s) RETURNING id"

        params = (
            user['uid'], seq, seq, seq, guards1, positions1, formation1, guards2, positions2, formation2,
            int(time.time()))
        # print query % params
        for i in range(5):
            try:
                yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def leave_state(self, user, sid):
        query = "UPDATE core_userstate SET state=%s WHERE user_id=%s RETURNING id"
        params = (-1, user['uid'])
        # print query % params
        for i in range(5):
            try:
                yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue

        guards1 = escape.json_encode({"01001": {"equips": [0, 0, 0, 0, 0, 0], "star": 1, "color": 1, "hp": 100,
                                                "skills": [1, 0, 0, 0], "hid": "01001", "xp": 10}, \
                                      "01002": {"equips": [0, 0, 0, 0, 0, 0], "star": 0, "color": 0, "hp": 100,
                                                "skills": [0, 0, 0, 0], "hid": "01002", "xp": 10}})
        positions1 = escape.json_encode({"01001": "1", "01002": "2"})
        formation1 = 1
        guards2 = escape.json_encode({"01021": {"equips": [0, 0, 0, 0, 0, 0], "star": 1, "color": 0, "hp": 100,
                                                "skills": [0, 0, 0, 0], "hid": "01021", "xp": 10}, \
                                      "01024": {"equips": [0, 0, 0, 0, 0, 0], "star": 2, "color": 1, "hp": 100,
                                                "skills": [0, 0, 0, 0], "hid": "01024", "xp": 10}})
        positions2 = escape.json_encode({"01021": "1", "01024": "2"})
        formation2 = 1
        # uid = yield self.create_user()
        query = "SELECT id FROM %s" % D.VERSUSSTATE[sid] + " WHERE user_id=%s LIMIT 1"
        params = (user['uid'],)
        res = yield self.sql.runQuery(query, params)
        if res:
            id, = res[0]
            uid = yield self.create_user()
            query = "UPDATE %s SET " % D.VERSUSSTATE[
                sid] + "user_id=%s, jguards1=%s, jpositions1=%s, formation1=%s, jguards2=%s, jpositions2=%s, formation2=%s WHERE id=%s RETURNING id"
            params = (uid, guards1, positions1, formation1, guards2, positions2, formation2, id)
            # print query % params
            for i in range(5):
                try:
                    yield self.sql.runQuery(query, params)
                    break
                except storage.IntegrityError:
                    log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                    continue
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_cache(self, key, value, timeout=2592000):  # default 30 days
        yield self.redis.setex("cache:%s" % key, timeout, pickle.dumps(value))

    @storage.databaseSafe
    @defer.inlineCallbacks
    def del_cache(self, key):
        yield self.redis.delete("cache:%s" % key)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_cache(self, key):
        value = yield self.redis.get("cache:%s" % key)
        if value:
            defer.returnValue(pickle.loads(value))
        else:
            defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_flush(self, key, value):
        yield self.redis.setex("flush:%s" % key, 36000, pickle.dumps(value))

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_flush(self, key):
        value = yield self.redis.get("flush:%s" % key)
        if value:
            yield self.redis.delete("flush:%s" % key)
            defer.returnValue(pickle.loads(value))
        else:
            defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_matchflush(self, key, value):
        yield self.redis.setex("matchflush:%s" % key, 36000, value)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_matchflush(self, key):
        value = yield self.redis.get("matchflush:%s" % key)
        if value:
            yield self.redis.delete("matchflush:%s" % key)
            defer.returnValue(value)
        else:
            defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_taxflush(self, key, value):
        yield self.redis.setex("taxflush:%s" % key, 36000, pickle.dumps(value))

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_taxflush(self, key):
        value = yield self.redis.get("taxflush:%s" % key)
        if value:
            yield self.redis.delete("taxflush:%s" % key)
            defer.returnValue(pickle.loads(value))
        else:
            defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_bootyflush(self, key, value):
        yield self.redis.setex("bootyflush:%s" % key, 36000, pickle.dumps(value))

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_bootyflush(self, key):
        value = yield self.redis.get("bootyflush:%s" % key)
        if value:
            yield self.redis.delete("bootyflush:%s" % key)
            defer.returnValue(pickle.loads(value))
        else:
            defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_expedflush(self, key, value):
        yield self.redis.setex("expedflush:%s" % key, 36000, pickle.dumps(value))

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_expedflush(self, key):
        value = yield self.redis.get("expedflush:%s" % key)
        if value:
            yield self.redis.delete("expedflush:%s" % key)
            defer.returnValue(pickle.loads(value))
        else:
            defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_versusflush(self, key, value):
        yield self.redis.setex("versusflush:%s" % key, 36000, value)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_versusflush(self, key):
        value = yield self.redis.get("versusflush:%s" % key)
        if value:
            yield self.redis.delete("versusflush:%s" % key)
            defer.returnValue(value)
        else:
            defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_uu(self, key, value):
        if key:
            yield self.redis.setex("uu:%s" % key, 60, pickle.dumps(value))
        else:
            defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_uu(self, key):
        if key:
            value = yield self.redis.get("uu:%s" % key)
            if value:
                defer.returnValue(pickle.loads(value))
            else:
                defer.returnValue(None)
        else:
            defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def get_channel_id(self, channel_slug):
        channels = yield self.sql.runQuery("SELECT id FROM core_channel WHERE slug=%s LIMIT 1", (channel_slug,))
        if not channels:
            raise web.HTTPError(400)
        defer.returnValue(channels[0][0])

    @storage.databaseSafe
    @defer.inlineCallbacks
    def create_guild(self, uid, name):
        query = "INSERT INTO core_guild (creator, name, notice, members, president, vice_presidents, timestamp) VALUES" \
                " (%s, %s, NULL, %s, %s, %s, %s) RETURNING id"
        params = (uid, name, escape.json_encode([uid]), uid, escape.json_encode([]), int(time.time()))
        for i in range(5):
            try:
                gid = yield self.sql.runQuery(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(gid[0][0])

    @storage.databaseSafe
    @defer.inlineCallbacks
    def update_guild_members(self, gid, president, vice_presidents, members):
        query = "UPDATE core_guild SET members=%s,  president=%s, vice_presidents=%s WHERE id=%s"
        params = (escape.json_encode(members), president, escape.json_encode(vice_presidents), gid)
        for i in range(5):
            try:
                yield self.sql.runOperation(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_president(self, pid, gid):
        query = "UPDATE core_guild SET president=%s WHERE id=%s"
        params = (pid, gid)
        for i in range(5):
            try:
                yield self.sql.runOperation(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(None)

    @storage.databaseSafe
    @defer.inlineCallbacks
    def set_vice_president(self, uid, gid, vice_presidents):
        vice_presidents = escape.json_decode(vice_presidents)
        vice_presidents.append(uid)
        query = "UPDATE core_guild SET vice_presidents=%s WHERE id=%s"
        params = (escape.json_encode(vice_presidents), gid)
        for i in range(5):
            try:
                yield self.sql.runOperation(query, params)
                break
            except storage.IntegrityError:
                log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                continue
        defer.returnValue(None)


class ApiHandler(BaseHandler):
    def _(self, message, plural_message=None, count=None):
        return self.locale.translate(message, plural_message, count)

    def auth_login(self, user):
        self.user_key = self.create_signed_value("user_id", str(user.id))
        self.set_cookie("user_id", self.user_key, expires_days=1)
        self._current_user = user

    def auth_logout(self):
        self.clear_cookie("user_id")
        self._current_user = None

    def has_arg(self, name):
        return self.request.arguments.has_key(name)

    def arg(self, name, default=web.RequestHandler._ARG_DEFAULT, strip=True):
        return self.get_argument(name, default, strip)

    def arg_bool(self, name):
        return self.arg(name, 'false') == 'true'

    def args(self, name, default=[], separator=','):
        value = self.get_argument(name, None)
        if value:
            return value.split(',')
        else:
            return ''

    def keyword_filte(self, content):
        return checkword.mark_filte(content)

    def out_content(self, content):
        return checkword.output(content)

    def static_media_url(self, url):
        return self.settings.get('static_url', '') + (url[0] == '/' and url[1:] or url)

    def file_url(self, f, tag='phone'):
        if f is None:
            return ''
        try:
            if hasattr(f, 'extra_thumbnails'):
                dpi = 1
                if dpi > 1 and f.extra_thumbnails.has_key('%dx%s' % (dpi, tag)):
                    f = f.extra_thumbnails['%dx%s' % (dpi, tag)]
                elif f.extra_thumbnails.has_key(tag):
                    f = f.extra_thumbnails[tag]

            if hasattr(f, 'url'):
                url = f.url
            else:
                url = unicode(f)
            return self.static_media_url(url)
        except Exception, e:
            print e
            return

    def get_cookie(self, name, default=None):
        if name == 'user_id' and self.has_arg('session_key'):
            return self.arg('session_key')
        return super(ApiHandler, self).get_cookie(name, default)

    @property
    def user(self):
        return self.current_user

    def send_error(self, status_code=403, **kwargs):
        if self.settings.get("debug", False):
            print kwargs
        if self._headers_written:
            logging.error("Cannot send error response after headers written")
            if not self._finished:
                self.finish()
            return
        self.clear()
        self.set_status(status_code)
        if status_code < 500:
            if kwargs.has_key('exception') and not kwargs.has_key('msg'):
                kwargs['msg'] = str(kwargs['exception'])
                del kwargs['exception']

            self.write(kwargs)
        self.finish()

    def write(self, chunk):
        assert not self._finished

        if type(chunk) in (QuerySet,):
            chunk = self.ps(chunk)

        if type(chunk) in (dict, list):
            chunk = json.dumps(chunk, cls=ApiJSONEncoder, ensure_ascii=False, indent=4)
            if self.arg('cb', False):
                chunk = '%s(%s)' % (self.arg('cb'), chunk)
            self.set_header("Content-Type", "text/javascript; charset=UTF-8")
            # self.set_header("Content-Encoding", "gzip")
            # self.set_header("Content-Type", "application/json; charset=UTF-8")
            chunk = web.utf8(chunk)
            self._write_buffer.append(chunk)
        else:
            super(ApiHandler, self).write(chunk)

    def ps(self, qs, convert_func=None, **kwargs):
        start = int(self.get_argument('start', 0))
        count = int(self.get_argument('count', 25))
        if (type(qs) in (list, set)):
            total_count = len(qs)
        else:
            total_count = qs.count()
            if type(qs) not in (QuerySet,):
                qs = qs.all()

        if total_count > start:
            if start == -1:
                import math
                start = (math.ceil(float(total_count) / count) - 1) * count
            items = convert_func is None and qs[start:start + count] or [convert_func(item, **kwargs) for item in
                                                                         qs[start:start + count]]
        else:
            items = []
        return {'total_count': total_count, 'items': items}

    def format_params(self, params, urlencode):
        slist = sorted(params)
        buff = []
        for k in slist:
            v = quote(params[k]) if urlencode else params[k]
            buff.append("{0}={1}".format(k, v))

        return "&".join(buff)

    def verify_sign(self, params, sign):
        md = EVP.MessageDigest('sha1')
        md.update(params.encode('utf-8'))
        digest = md.final()
        bio = BIO.MemoryBuffer(D.PUB_KEY)
        key = RSA.load_pub_key_bio(bio)
        try:
            result = key.verify(digest, base64.b64decode(sign))
        except Exception:
            result = None
        return result

    def create_sign(self, params):
        md = EVP.MessageDigest('sha1')
        md.update(params.encode('utf-8'))
        digest = md.final()
        bio = BIO.MemoryBuffer(D.PRI_KEY)
        key = RSA.load_key_bio(bio)
        try:
            result = base64.b64encode(key.sign(digest))
        except Exception:
            result = None
        return result

    def random_pick(self, some_list):
        x = random.uniform(0, 1)
        cumulative_probability = 0.0
        for item, item_probability in some_list:
            cumulative_probability += item_probability
            if x < cumulative_probability: break
        return item

    def random_prod(self, some_list):
        x = random.uniform(0, 1)
        cumulative_probability = 0.0
        for item, item_probability, num in some_list:
            cumulative_probability += item_probability
            if x < cumulative_probability: break
        return item, num

    def random_prods(self, start, end, mprods):
        # print start, end, mprods
        prods = {}
        if end <= len(mprods):
            for one in xrange(start, end):
                prod = mprods[one]
                if prod in prods:
                    prods[prod] += 1
                else:
                    prods[prod] = 1
        if end > len(mprods) and start > len(mprods):
            for one in xrange(start % len(mprods), end % len(mprods) + 1):
                prod = mprods[one]
                if prod in prods:
                    prods[prod] += 1
                else:
                    prods[prod] = 1
        if start <= len(mprods) and end >= len(mprods):
            for one in xrange(start, len(mprods)):
                prod = mprods[one]
                if prod in prods:
                    prods[prod] += 1
                else:
                    prods[prod] = 1
            for one in xrange(0, end % len(mprods)):
                prod = mprods[one]
                if prod in prods:
                    prods[prod] += 1
                else:
                    prods[prod] = 1
        return prods


class ApiJSONEncoder(DjangoJSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return str(o)
        # return dt2ut(o)
        elif isinstance(o, decimal.Decimal):
            return str(o)
        else:
            try:
                return super(ApiJSONEncoder, self).default(o)
            except Exception:
                return smart_unicode(o)
