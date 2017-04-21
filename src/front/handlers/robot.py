# -*- coding: utf-8 -*-

import random
import time
import zlib
import uuid
import json
import datetime
import pickle
from twisted.internet import defer
from twisted.python import log
from cyclone import escape, web
from front import storage
from front import utils
from front.utils import E
from itertools import *
# from front.handlers.base import BaseHandler
from front.wiapi import *
from front.handlers.base import ApiHandler, ApiJSONEncoder
from local_settings import *

@handler
class GetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Robot search', '/robot/search/', [
        Param('level', True, int, 10, 10, 'level'),
        ], filters=[ps_filter], description="Robot search")
    def get(self):
        try:
            level = int(self.get_argument("level", 0))
        except Exception:
            raise web.HTTPError(400, "Argument error")
        users = []
        res = yield self.sql.runQuery("SELECT id, name, secret FROM core_user WHERE xp/100000=%s ORDER BY RANDOM() LIMIT 50", (level-1, ))
        if res:
            for r in res:
                user = yield self.get_user(r[0])
                users.append(user)
        
        self.write(dict(out=dict(users=users)))

@handler
class CreateHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Robot create', '/robot/create/', [
        Param('model', True, str, 'bigfish@hi3798mv100', 'bigfish@hi3798mv100', 'model'),
        Param('serial', True, str, '0066cf0456732122121', '0066cf0456732122121', 'serial'),
        Param('id', False, str, None, None, 'id'),
        Param('name', False, str, '刘健', '刘健', 'name'),
        Param('avat', False, str, '1', '1', 'avat'),
        ], filters=[ps_filter], description="Robot create")
    def get(self):
        try:
            model = self.get_argument("model")
            serial = self.get_argument("serial")
            cid = self.get_argument("id")
            idcard = self.get_argument("idcard", None)
            channel = self.get_argument("channel", None)
            name = self.get_argument("name", None)
        except Exception:
            raise web.HTTPError(400, "Argument error")

        res = yield self.sql.runQuery("SELECT * FROM core_user WHERE nickname=%s LIMIT 1", (name, ))
        if res:
            self.write(dict(err=E.ERR_USER_REPEAT, msg=E.errmsg(E.ERR_USER_REPEAT)))
            return            
        if not name:
            name = yield self.get_nickname()
            name = name[0]

        cuser = yield self.get_user(cid)
        if not cuser:
            self.write(dict(err=E.ERR_USER_NOTFOUND, msg=E.errmsg(E.ERR_USER_NOTFOUND)))
            return

        avat_list = ['daqiao', 'sunshi', 'zhangliao', 'zhaoyun', 'zhugeliang', 'zhujue']
        avat = random.choice(avat_list)

        nid = yield self.create_user()
        if nid:
            nuser = dict(name=name, nickname=name, xp=cuser['xp'], heros=cuser['heros'], gold=cuser['gold'],\
             feat=cuser['feat'], rock=cuser['rock'], avat=avat, book=cuser['book'], vrock=cuser['vrock'])
            user = yield self.set_user(nid, **nuser)
            access_token = 'pt' + uuid.uuid4().hex
            idcard = yield self.refresh_idcard(idcard, model, serial, channel, access_token)
            if idcard:
                ahex, aid = idcard.split('h', 1)
                res = yield self.sql.runQuery("SELECT accountid, user_id FROM core_account WHERE accountid=%s OR id=%s LIMIT 1", (aid, aid))
                if res:
                    query = "UPDATE core_account SET accountid=%s, timestamp=%s WHERE id=%s RETURNING id"
                    params = (aid, int(time.time()), aid)
                    for i in range(5):
                        try:
                            yield self.sql.runOperation(query, params)
                            break
                        except storage.IntegrityError:
                            log.msg("SQL integrity error, retry(%i): %s" % (i, (query % params)))
                            continue
            self.write(dict(out=dict(user=user)))
        else:
            raise web.HTTPError(500)


@handler
class CloneHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Robot clone', '/robot/clone/', [
        Param('id', False, str, None, None, 'id'),
        Param('cloneid', False, str, None, None, 'cloneid'),
        Param('name', False, str, '刘健', '刘健', 'name'),
        Param('avat', False, str, '1', '1', 'avat'),
        ], filters=[ps_filter], description="Robot clone")
    def get(self):
        try:
            uid = self.get_argument("id")
            cloneid = self.get_argument("cloneid")
            name = self.get_argument("name", None)
            avat = self.get_argument("avat", None)
        except Exception:
            raise web.HTTPError(400, "Argument error")

        user = yield self.get_user(uid)
        cloner = yield self.get_user(cloneid)
        name = yield self.get_nickname()
        avat_list = ['daqiao', 'sunshi', 'zhangliao', 'zhaoyun', 'zhugeliang', 'zhujue']
        avat = random.choice(avat_list)
        if uid == cloneid:
            raise web.HTTPError(400, "Argument error")

        if (not user) or (not cloner):
            self.write(dict(err=E.ERR_USER_NOTFOUND, msg=E.errmsg(E.ERR_USER_NOTFOUND)))
            return 
    
        cuser = dict(xp=cloner['xp'], heros=cloner['heros'], gold=cloner['gold'], feat=cloner['feat'],\
         rock=cloner['rock'], vrock=cloner['vrock'], book=cloner['book'], nickname=name[0], name=name[0],\
          avat=avat)
        user = yield self.set_user(uid, **cuser)
        self.write(dict(out=dict(user=user)))

@handler
class ResetHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Robot reset', '/robot/reset/', [
        Param('id', True, str, '9', '9', 'id'),
        ], filters=[ps_filter], description="Robot reset")
    def get(self):
        try:
            uid = self.get_argument("id")
        except Exception:
            raise web.HTTPError(400, "Argument error")

        user = yield self.get_user(uid)
        if not user:
            self.write(dict(err=E.ERR_USER_NOTFOUND, msg=E.errmsg(E.ERR_USER_NOTFOUND)))
            return 

        yield self.redis.set('arenatimes:%s' % uid, 0)
        self.write(dict(out=dict(user=user)))

@handler
class MessageHandler(ApiHandler):

    @storage.databaseSafe
    @defer.inlineCallbacks
    @api('Robot message', '/robot/message/', [
        Param('message', True, str, '#1张三1#在功勋商店中获得了:#2关羽2#。', '#1张三1#在功勋商店中获得了:#2关羽2#。', 'message'),
        ], filters=[ps_filter], description="Robot message")
    def get(self):
        try:
            message = self.get_argument("message")
        except Exception:
            raise web.HTTPError(400, "Argument error")
        from urllib import unquote
        #print 'message', unquote(message)
        yield self.redis.rpush("message", pickle.dumps([unquote(message), int(time.time())]))   
        ret = 1
        self.write(dict(ret=ret))

