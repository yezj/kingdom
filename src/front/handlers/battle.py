# -*- coding: utf-8 -*-

import random
import time
import zlib
import uuid
from twisted.internet import defer
from cyclone import escape, web
from front import storage
from front import utils
from front.utils import E
from front import storage, D
from twisted.python import log
# from front.handlers.base import BaseHandler
from front.wiapi import *
from front.handlers.base import ApiHandler, ApiJSONEncoder
from local_settings import ZONE_ID


@handler
class GetHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    # @utils.signed
    @api('Battle get', '/battle/get/', [
        Param('stage_id', True, str, '010208_0', '010208_0', 'stage_id'),
        Param('opponent_Id_card', True, str, '', '', 'opponent_Id_card'),
        Param('access_token', True, str, '010208_0', '010208_0', 'access_token'),
        Param('idcard', True, str, '010208_0', '010208_0', 'idcard'),
        Param('user_id', True, str, '7', '7', 'user_id'),
        Param('formationList', True, str, '[5,1,2,4,8]', '[5,1,2,4,8]', 'formationList'),
    ], filters=[ps_filter], description="Battle get")
    def get(self):
        try:
            stage_id = self.get_argument("stage_id")
            opponent_Id_card = self.get_argument("opponent_Id_card", None)
            access_token = self.get_argument("access_token")
            user_id = self.get_argument("user_id")
            idcard = self.get_argument("idcard")
            formationList = self.get_argument("formationList")

        except Exception:
            self.write(dict(err=E.ERR_ARGUMENT, msg=E.errmsg(E.ERR_ARGUMENT)))
            return

        # // "battleId":"id20170608_023_65678",
        # // "rs1":456897635,
        # // "rs2":12345,
        # // "rs3":98765,
        # // "is1PLeft":false,
        #
        # // "name_1P":"我要霸占你你秀发",
        # // "name_2P":"浅时光Bonns",
        # // "level_1P":23,
        # // "level_2P":35,
        # // "icon_1P":301,
        # // "icon_2P":401,
        #
        # // "resource":500,
        # // "resourceLimit":1000,
        # // "resourceGrowSpeed":1,

        res = yield self.sql.runQuery(
            "SELECT playerLevel, avat, nickname, formations FROM core_user WHERE user_id=%s LIMIT 1",
            (user_id,))
        if res:
            playerLevel, avat, nickname, heros1P = res[0]
        else:
            self.write(dict(err=E.ERR_ARGUMENT, msg=E.errmsg(E.ERR_ARGUMENT)))
            return

        battleId = uuid.uuid4().hex

        res = yield self.sql.runQuery("SELECT jgates FROM core_gate WHERE gate_id=%s LIMIT 1", (stage_id,))
        if res:
            jgates, = res[0]
            jgates = escape.json_decode(jgates)
            jgates.update(dict(battleId=battleId,
                               level_1P=playerLevel,
                               icon_1P=avat,
                               name_1P=nickname,
                               heros1P=heros1P,
                               timestamp=int(time.time())))
        else:
            self.write(dict(err=E.ERR_ARGUMENT, msg=E.errmsg(E.ERR_ARGUMENT)))
            return

        yield self.set_flush(battleId, jgates)

        # ret = dict(result=jgates)
        # reb = zlib.compress(escape.json_encode(ret))
        self.write(jgates)


@handler
class SetHandler(ApiHandler):
    @storage.databaseSafe
    @defer.inlineCallbacks
    # @utils.signed
    @api('Battle set', '/battle/set/', [
        Param('battleId', True, str, '010208_0', '010208_0', 'stage_id'),
        Param('access_token', True, str, '010208_0', '010208_0', 'access_token'),
        Param('idcard', True, str, '010208_0', '010208_0', 'idcard'),
        Param('user_id', True, str, '7', '7', 'user_id'),
        Param('totalFrame', True, int, 23432, 23432, 'totalFrame'),
        Param('record', True, str, '-1', '-1', 'record'),
        Param('antiCheatCode', True, str, '2327e474291a71427e474291a725', '2327e474291a71427e474291a725',
              'antiCheatCode'),
    ], filters=[ps_filter], description="Battle set")
    def get(self):
        try:
            battleId = self.get_argument("battleId")
            access_token = self.get_argument("access_token")
            idcard = self.get_argument("idcard")
            user_id = self.get_argument("user_id")
            totalFrame = self.get_argument("totalFrame")
            record = self.get_argument("record")
            antiCheatCode = self.get_argument("antiCheatCode")
        except Exception:
            self.write(dict(err=E.ERR_ARGUMENT, msg=E.errmsg(E.ERR_ARGUMENT)))
            return
        batt = yield self.get_flush(battleId)
        if batt:
            heroLvl = [
                          "23", "24", "5", "4"
                      ],
            heroExp = [
                          2134, 2314, 213, 213
                      ],
            # 胜利时间
            timestamp = 2421432143,
            # 保存录像的话，录像ID，唯一，不保存则为空
            recordId = ""
            # 获得的金币
            goldCoin = 0,
            # 获得的钻石, 没有钻石则为0
            gem = 0,
            # 获得物品的话，物品列表
            item = [
                {"id": 214322, "num": 1},
                {"id": 214322, "num": 1},
                {"id": 214322, "num": 1}
            ]
            data = dict(heroLvl=heroLvl,
                        heroExp=heroExp,
                        timestamp=timestamp,
                        recordId=recordId,
                        goldCoin=goldCoin,
                        gem=gem,
                        item=item
                        )
        else:
            self.write(dict(err=E.ERR_ARGUMENT, msg=E.errmsg(E.ERR_ARGUMENT)))
            return
        #ret = dict(timestamp=int(time.time()), data=data)
        #reb = zlib.compress(escape.json_encode(ret))
        self.write(data)
