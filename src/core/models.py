# -*- coding: utf-8 -*-

import datetime
import hashlib
from django.db import models
from django.utils.text import ugettext_lazy as _
from cyclone import escape
from signals import *
from positions import PositionField
from django.db.models.signals import post_save, post_delete
from django.core.exceptions import ValidationError
from filebrowser.fields import FileBrowseField, FileObject
from django.contrib.auth.models import User as AdminUser


class Channel(models.Model):
    title = models.CharField(_('Title'), max_length=20)
    slug = models.SlugField(_('Slug'))

    class Meta:
        verbose_name = _('Channel')
        verbose_name_plural = _('Channels')
        ordering = ('slug',)

    def __unicode__(self):
        return self.title


class User(models.Model):
    id = models.AutoField(primary_key=True)
    secret = models.CharField(_('Secret'), max_length=100, blank=True)
    name = models.CharField(_('Name'), max_length=20, unique=True)
    nickname = models.CharField(_('Nickname'), max_length=30, blank=True, db_index=True)
    avat = models.CharField(_('Avatar'), max_length=20, blank=True)
    xp = models.PositiveIntegerField(_('Experience'), default=0, db_index=True)
    gold = models.PositiveIntegerField(_('Gold'), default=0)
    rock = models.PositiveIntegerField(_('Rock'), default=0)
    feat = models.PositiveIntegerField(_('Feat'), default=0)
    book = models.PositiveIntegerField(_('Book'), default=0)
    vrock = models.PositiveIntegerField(_('Vrock'), default=0)
    jextra = models.TextField(_('JSON Extra'), blank=True)
    jheros = models.TextField(_('JSON Heros'), blank=True)
    jprods = models.TextField(_('JSON Prods'), blank=True)
    jbatts = models.TextField(_('JSON Batts'), blank=True)
    jseals = models.TextField(_('JSON Seals'), blank=True)
    jtasks = models.TextField(_('JSON Tasks'), blank=True)
    jworks = models.TextField(_('JSON Works'), blank=True)
    jmails = models.TextField(_('JSON Mails'), blank=True)
    jdoors = models.TextField(_('JSON Doors'), blank=True)
    jbeautys = models.TextField(_('JSON Beauty'), blank=True)
    jactivities = models.TextField(_('JSON Activities'), blank=True)
    jrecharge = models.TextField(_('JSON Recharge'), blank=True)
    jinsts = models.TextField(_('JSON Insts'), blank=True)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0, blank=True)

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')

    def __unicode__(self):
        return self.nickname


post_save.connect(syncdb_callback_function, sender=User)
post_delete.connect(syncdb_callback_function, sender=User)


class Guild(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(_('Name'), max_length=64, unique=True)
    notice = models.CharField(_('Notice'), max_length=128, blank=True, null=True)
    creator = models.CharField(_('Creator'), max_length=64, unique=True)
    president = models.CharField(_('President'), max_length=64, blank=True, null=True)
    vice_presidents = models.TextField(_('JSON Vice presidents'), blank=True)
    members = models.TextField(_('JSON Members'), blank=True)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0, blank=True)

    class Meta:
        verbose_name = _('Guild')
        verbose_name_plural = _('Guilds')

    def __unicode__(self):
        return self.name


post_save.connect(syncdb_callback_function, sender=Guild)
post_delete.connect(syncdb_callback_function, sender=Guild)


class Hp(models.Model):
    user = models.OneToOneField(User)
    hp = models.PositiveSmallIntegerField(_('Hp'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0, blank=True)

    class Meta:
        verbose_name = _('Hp')
        verbose_name_plural = _('Hps')

    def __unicode__(self):
        return self.user


# post_save.connect(syncdb_callback_function, sender=Hp)
# post_delete.connect(syncdb_callback_function, sender=Hp)


class Account(models.Model):
    id = models.AutoField(primary_key=True)
    hex = models.CharField(_('Hex'), max_length=64, blank=True)
    state = models.PositiveIntegerField(_('State'), default=0)  # 0: normal; 2: abnormal; 3: bebanked
    user = models.OneToOneField(User, null=True)
    model = models.CharField(_('Model'), max_length=50, blank=True)
    serial = models.CharField(_('Serial'), max_length=100, blank=True)
    authmode = models.CharField(_('AuthMode'), max_length=30, blank=True)
    authstring = models.CharField(_('AuthString'), max_length=200, blank=True)
    channel = models.ForeignKey(Channel, blank=True, null=True)
    created = models.PositiveIntegerField(_('Created'), default=0, blank=True)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0, blank=True)
    accountid = models.CharField(_('Accountid'), max_length=20, blank=True)

    class Meta:
        verbose_name = _('Account')
        verbose_name_plural = _('Accounts')

    def __unicode__(self):
        if self.user:
            return self.user.nickname
        else:
            return self.serial + '@' + self.model


class Zone(models.Model):
    zoneid = models.PositiveIntegerField(_('Zoneid'), default=0)
    name = models.CharField(_('Zone Name'), max_length=20, unique=True)

    class Meta:
        verbose_name = _('Zone')
        verbose_name_plural = _('Zones')

    def __unicode__(self):
        return ':'.join([self.name, str(self.zoneid)])


class Notice(models.Model):
    title = models.CharField(_('Title'), max_length=20, unique=True)
    content = models.TextField(blank=True)
    screenshot = FileBrowseField(_('Screenshot'), max_length=200, directory='img/screenshot', format='image',
                                 extensions=[".jpg"], blank=True)
    url = models.CharField(_('Url'), max_length=20, blank=True)
    sign = models.CharField(_('Sign'), max_length=20, blank=True)
    created_at = models.DateTimeField(_('Created_at'), default=datetime.datetime.now)
    ended_at = models.DateTimeField(_('Ended_at'), default=datetime.datetime.now)

    class Meta:
        verbose_name = _('Notice')
        verbose_name_plural = _('Notices')

    def __unicode__(self):
        return self.title


class Noticeship(models.Model):
    zone = models.ForeignKey(Zone)
    notice = models.ForeignKey(Notice)
    position = PositionField(_('Position'), collection='zone')

    class Meta:
        verbose_name = 'Noticeship'
        verbose_name_plural = _('Noticeships')
        ordering = ('position',)

    def __unicode__(self):
        return self.notice.title


class Door(models.Model):
    player = models.ForeignKey(User)
    jheros = models.TextField(_('JSON Heros'), blank=True)

    class Meta:
        verbose_name = _('Door')
        verbose_name_plural = _('Doors')

    def __unicode__(self):
        return self.user.name


class Prop(models.Model):
    user = models.ForeignKey(User)
    label = models.CharField(_('Label'), max_length=20, db_index=True)
    num = models.PositiveIntegerField(_('Num'), blank=True, null=True)
    txt = models.TextField(_('Txt'), blank=True, null=True)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0, blank=True)

    class Meta:
        verbose_name = _('Prop')
        verbose_name_plural = _('Props')
        unique_together = ('user', 'label')

    def __unicode__(self):
        return self.user.name


class Mail(models.Model):
    MAIL = 0
    NOTICE = 1
    TYPES = (
        (MAIL, _('Mail')),
        (NOTICE, _('Notice')),
    )
    sender = models.CharField(_('Sender'), max_length=20, db_index=True)
    to = models.ForeignKey(User, blank=True, null=True)
    title = models.CharField(_('Title'), max_length=50)
    content = models.TextField(_('Content'), blank=True)
    jawards = models.TextField(_('JSON Awards'), blank=True)
    comment = models.TextField(_('Comment'), blank=True)
    type = models.PositiveSmallIntegerField(
        _('types'), choices=TYPES, default=MAIL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Mail')
        verbose_name_plural = _('Mails')

    def save(self, *args, **kwargs):
        if self.jawards:
            try:
                escape.json_decode(self.jawards)
            except Exception:
                raise ValueError("JSON jawards format error")
        super(Mail, self).save(*args, **kwargs)

    def __unicode__(self):
        return self.title


class FirstLott(models.Model):
    user = models.ForeignKey(User)
    first = models.BooleanField(default=False)
    lotttype = models.PositiveIntegerField(_('Lotttype'), default=0)
    created_at = models.PositiveIntegerField(_('Created_at'), default=0, blank=True)

    class Meta:
        verbose_name = _('FirstLott')
        verbose_name_plural = _('FirstLotts')

    def __unicode__(self):
        return self.user.name


class DayLott(models.Model):
    user = models.ForeignKey(User)
    times = models.PositiveIntegerField(_('Times'), default=0)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('DayLott')
        verbose_name_plural = _('DayLotts')

    def __unicode__(self):
        return self.user.name


class FreeLott(models.Model):
    user = models.ForeignKey(User)
    lotttype = models.PositiveIntegerField(_('Lotttype'), default=0)
    times = models.PositiveIntegerField(_('Times'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0)
    free = models.BooleanField(default=False)

    class Meta:
        verbose_name = _('FreeLott')
        verbose_name_plural = _('FreeLotts')

    def __unicode__(self):
        return self.user.name + str(self.lotttype)


class Arena(models.Model):
    user = models.ForeignKey(User, unique=True)
    arena_coin = models.PositiveIntegerField(_('Arena coin'), default=0)
    before_rank = models.PositiveIntegerField(_('Before_rank'), default=0)
    last_rank = models.PositiveIntegerField(_('Last_rank'), default=0)
    now_rank = models.PositiveIntegerField(_('Now_rank'), default=0)
    jguards = models.TextField(_('JSON guards'), blank=True)
    jpositions = models.TextField(_('JSON positions'), blank=True)
    formation = models.PositiveIntegerField(_('Formation'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0)

    class Meta:
        verbose_name = _('Arena')
        verbose_name_plural = _('Arenas')

    def __unicode__(self):
        return self.user.name


class ArenaResult(models.Model):
    WIN = 1
    LOSE = 0
    RESULTS = (
        (WIN, _('Win')),
        (LOSE, _('Lose')),
    )
    user = models.ForeignKey(User, related_name='users')
    competitor = models.ForeignKey(User, related_name='competitors')
    result = models.PositiveSmallIntegerField(
        _('Result'), choices=RESULTS, default=WIN)
    ascend = models.IntegerField(_('Ascend'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0)

    class Meta:
        verbose_name = _('ArenaResult')
        verbose_name_plural = _('ArenaResults')

    def __unicode__(self):
        return self.user.name + ' : ' + self.competitor.name


class Hunt(models.Model):
    user = models.ForeignKey(User, related_name='hunts')
    jguards = models.TextField(_('JSON guards'), blank=True)
    formation = models.PositiveIntegerField(_('Formation'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0)

    class Meta:
        verbose_name = _('Hunt')
        verbose_name_plural = _('Hunts')

    def __unicode__(self):
        return self.user.name


class HuntResult(models.Model):
    winner = models.ForeignKey(User, related_name='winner')
    loser = models.ForeignKey(User, related_name='loser')
    jawards = models.TextField(_('JSON Awards'), blank=True)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0)

    class Meta:
        verbose_name = _('HuntResult')
        verbose_name_plural = _('HuntResults')

    def __unicode__(self):
        return self.user.name


class Mine(models.Model):
    ASSART = 0  # 开荒
    MINE = 1  # 挖矿
    TYPE = (
        (ASSART, _('Assart')),
        (MINE, _('Mine')),
    )
    SMALL = 0
    MEDIUM = 1
    LARGE = 2
    SIZE = (
        (SMALL, _('Small')),
        (MEDIUM, _('Medium')),
        (LARGE, _('Large')),
    )
    BUSY = 0
    DONE = 1
    STATUS = (
        (BUSY, _('Busy')),
        (DONE, _('Done')),
    )
    user = models.ForeignKey(User, related_name='Mines')
    jguards = models.TextField(_('JSON guards'), blank=True)
    formation = models.PositiveIntegerField(_('Formation'), default=0)
    sword = models.PositiveIntegerField(_('Sword'), default=0)
    type = models.PositiveSmallIntegerField(_('Type'), choices=TYPE, default=ASSART)
    size = models.PositiveSmallIntegerField(_('Size'), choices=SIZE, default=SMALL)
    status = models.PositiveSmallIntegerField(_('Status'), choices=STATUS, default=BUSY)
    jstocks = models.TextField(_('JSON stocks'), blank=True)
    jpositions = models.TextField(_('JSON positions'), blank=True)
    created_at = models.PositiveIntegerField(_('Created_at'), default=0)
    ended_at = models.PositiveIntegerField(_('Ended_at'), default=0)

    class Meta:
        verbose_name = _('Mine')
        verbose_name_plural = _('Mines')

    def __unicode__(self):
        return self.user.name


class Prison(models.Model):
    IDLE = 0
    RECLAIM = 1
    ASSART = 2
    STATUS = (
        (IDLE, _('Idle')),
        (RECLAIM, _('Reclaim')),
        (ASSART, _('Assart')),
    )
    user = models.ForeignKey(User, related_name='wardens')
    prisoner = models.ForeignKey(User, related_name='prisoners')
    status = models.PositiveSmallIntegerField(
        _('Status'), choices=STATUS, default=IDLE)
    position = models.PositiveIntegerField(_('Position'), default=0)
    created_at = models.PositiveIntegerField(_('Created_at'), default=0)
    ended_at = models.PositiveIntegerField(_('Ended_at'), default=0)

    class Meta:
        verbose_name = _('Prison')
        verbose_name_plural = _('Prisons')

    def __unicode__(self):
        return self.user.name + self.prisoner.name


class Release(models.Model):
    RESIST = 0
    EXPIRE = 1
    RELEASE = 2
    STATUS = (
        (RESIST, _('Resist')),
        (EXPIRE, _('Expire')),
        (RELEASE, _('Release')),
    )
    user = models.ForeignKey(User, related_name='slaveholders')
    prisoner = models.ForeignKey(User, related_name='slaves')
    status = models.PositiveSmallIntegerField(
        _('Status'), choices=STATUS, default=RELEASE)
    created_at = models.PositiveIntegerField(_('Created_at'), default=0)

    class Meta:
        verbose_name = _('Release')
        verbose_name_plural = _('Releases')

    def __unicode__(self):
        return self.user.name + self.prisoner.name


class Card(models.Model):
    user = models.ForeignKey(User)
    gid = models.CharField(_('Gid'), max_length=10)
    created_at = models.PositiveIntegerField(_('Created_at'), default=0)
    ended_at = models.PositiveIntegerField(_('Ended_at'), default=0)

    class Meta:
        verbose_name = _('Card')
        verbose_name_plural = _('Cards')

    def __unicode__(self):
        return self.user.name


class BuyRecord(models.Model):
    user = models.ForeignKey(User)
    gid = models.CharField(_('Gid'), max_length=10)
    created_at = models.PositiveIntegerField(_('Created_at'), default=0)

    class Meta:
        verbose_name = _('BuyRecord')
        verbose_name_plural = _('BuyRecords')

    def __unicode__(self):
        return self.user.name


class PayRecord(models.Model):
    SUCCESS = 'T'
    FAIL = 'F'
    CLOSE = 'C'
    STATUS = (
        (SUCCESS, _('Success')),
        (FAIL, _('Fail')),
        (CLOSE, _('Close')),
    )
    user = models.ForeignKey(User)
    pid = models.CharField(_('Pid'), max_length=10)
    trans_no = models.CharField(_('Trans_no'), max_length=60)
    result = models.CharField(_('Result'), choices=STATUS, default=CLOSE, max_length=10)
    trade_time = models.PositiveIntegerField(_('Trade_time'), default=0)
    amount = models.PositiveIntegerField(_('Amount'), default=0, blank=True)
    currency = models.CharField(_('CNY'), max_length=10)
    created_at = models.PositiveIntegerField(_('Created_at'), default=0)

    class Meta:
        verbose_name = _('PayRecord')
        verbose_name_plural = _('PayRecords')

    def __unicode__(self):
        return self.user.name


class AliOrder(models.Model):
    app_order_id = models.CharField(_('App_order_id'), max_length=100, blank=True)
    channel = models.ForeignKey(Channel)
    user = models.ForeignKey(User)
    pid = models.CharField(_('Pid'), max_length=10)
    amount = models.PositiveIntegerField(_('Amount'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0, blank=True)

    class Meta:
        verbose_name = _('AliOrder')
        verbose_name_plural = _('AliOrders')

    def __unicode__(self):
        return self.app_order_id


class AliPayRecord(models.Model):
    SUCCESS = 'T'
    FAIL = 'F'
    STATUS = (
        (SUCCESS, _('Success')),
        (FAIL, _('Fail')),
    )
    user = models.ForeignKey(User)
    pid = models.CharField(_('Pid'), max_length=10)
    app_order_id = models.CharField(_('App_order_id'), max_length=100, blank=True)
    coin_order_id = models.CharField(_('App_order_id'), max_length=100, blank=True)
    consume_amount = models.PositiveIntegerField(_('Consume_amount'), default=0, blank=True)
    credit_amount = models.PositiveIntegerField(_('Credit_amount'), default=0, blank=True)
    ts = models.BigIntegerField(_('Timestamp'), default=0)
    is_success = models.CharField(_('Is_success'), choices=STATUS, default=SUCCESS, max_length=10)
    error_code = models.CharField(_('Error_code'), max_length=100, blank=True)
    sign = models.CharField(_('Sign'), max_length=100)
    created_at = models.PositiveIntegerField(_('Created_at'), default=0)

    class Meta:
        verbose_name = _('AliPayRecord')
        verbose_name_plural = _('AliPayRecords')

    def __unicode__(self):
        return self.user.name


class XmOrder(models.Model):
    app_order_id = models.CharField(_('app_order_id'), max_length=100, blank=True)
    channel = models.ForeignKey(Channel)
    user = models.ForeignKey(User)
    pid = models.CharField(_('Pid'), max_length=10)
    amount = models.PositiveIntegerField(_('Amount'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0, blank=True)

    class Meta:
        verbose_name = _('XmOrder')
        verbose_name_plural = _('XmOrders')

    def __unicode__(self):
        return self.app_order_id


class XmPayRecord(models.Model):
    user = models.ForeignKey(User)
    pid = models.CharField(_('Pid'), max_length=10)
    app_order_id = models.CharField(_('App_order_id'), max_length=100, blank=True)
    orderstatus = models.CharField(_('Orderstatus'), max_length=100)
    payfee = models.PositiveIntegerField(_('Payfee'), default=0, blank=True)
    paytime = models.CharField(_('Paytime'), max_length=100, blank=True)
    created_at = models.PositiveIntegerField(_('Created_at'), default=0)

    class Meta:
        verbose_name = _('XmPayRecord')
        verbose_name_plural = _('XmPayRecords')

    def __unicode__(self):
        return self.user.name


class LetvOrder(models.Model):
    app_order_id = models.CharField(_('app_order_id'), max_length=100, blank=True)
    channel = models.ForeignKey(Channel)
    user = models.ForeignKey(User)
    pid = models.CharField(_('Pid'), max_length=10)
    amount = models.PositiveIntegerField(_('Amount'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0, blank=True)

    class Meta:
        verbose_name = _('LetvOrder')
        verbose_name_plural = _('LetvOrders')

    def __unicode__(self):
        return self.app_order_id


class LetvPayRecord(models.Model):
    user = models.ForeignKey(User)
    pid = models.CharField(_('Pid'), max_length=10)
    app_order_id = models.CharField(_('App_order_id'), max_length=100, blank=True)
    total = models.PositiveIntegerField(_('total'), default=0, blank=True)
    quantity = models.PositiveIntegerField(_('Quantity'), default=0, blank=True)
    created_at = models.PositiveIntegerField(_('Created_at'), default=0)

    class Meta:
        verbose_name = _('LetvPayRecord')
        verbose_name_plural = _('LetvPayRecords')

    def __unicode__(self):
        return self.user.name


class CmOrder(models.Model):
    app_order_id = models.CharField(_('app_order_id'), max_length=100, blank=True)
    channel = models.ForeignKey(Channel)
    user = models.ForeignKey(User)
    pid = models.CharField(_('Pid'), max_length=10)
    amount = models.PositiveIntegerField(_('Amount'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0, blank=True)

    class Meta:
        verbose_name = _('CmOrder')
        verbose_name_plural = _('CmOrders')

    def __unicode__(self):
        return self.app_order_id


class CmPayRecord(models.Model):
    user = models.ForeignKey(User)
    pid = models.CharField(_('Pid'), max_length=10)
    amount = models.PositiveIntegerField(_('Amount'), default=0)
    app_order_id = models.CharField(_('App_order_id'), max_length=100, blank=True)
    contentid = models.CharField(_('contentId'), max_length=100, blank=True)
    consumecode = models.CharField(_('consumeCode'), max_length=100, blank=True)
    cpid = models.CharField(_('cpid'), max_length=100, blank=True)
    hret = models.CharField(_('hret'), max_length=100, blank=True)
    created_at = models.PositiveIntegerField(_('Created_at'), default=0)

    class Meta:
        verbose_name = _('CmPayRecord')
        verbose_name_plural = _('CmPayRecords')

    def __unicode__(self):
        return self.user.name


class LgOrder(models.Model):
    app_order_id = models.CharField(_('app_order_id'), max_length=100, blank=True)
    channel = models.ForeignKey(Channel)
    user = models.ForeignKey(User)
    pid = models.CharField(_('Pid'), max_length=10)
    amount = models.PositiveIntegerField(_('Amount'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0, blank=True)

    class Meta:
        verbose_name = _('LgOrder')
        verbose_name_plural = _('LgOrders')

    def __unicode__(self):
        return self.app_order_id


class LgPayRecord(models.Model):
    user = models.ForeignKey(User)
    pid = models.CharField(_('Pid'), max_length=10)
    app_order_id = models.CharField(_('App_order_id'), max_length=100, blank=True)
    transaction_id = models.CharField(_('Transaction_id'), max_length=100, blank=True)
    fee = models.PositiveIntegerField(_('Fee'), default=0, blank=True)
    created_at = models.PositiveIntegerField(_('Created_at'), default=0)

    class Meta:
        verbose_name = _('XgPayRecord')
        verbose_name_plural = _('XgPayRecords')

    def __unicode__(self):
        return self.user.name


class DangbeiOrder(models.Model):
    app_order_id = models.CharField(_('app_order_id'), max_length=100, blank=True)
    user = models.ForeignKey(User)
    channel = models.ForeignKey(Channel)
    pid = models.CharField(_('Pid'), max_length=10)
    amount = models.PositiveIntegerField(_('Amount'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0, blank=True)

    class Meta:
        verbose_name = _('DangbeiOrder')
        verbose_name_plural = _('DangbeiOrders')

    def __unicode__(self):
        return self.app_order_id


class DangbeiPayRecord(models.Model):
    user = models.ForeignKey(User)
    pid = models.CharField(_('Pid'), max_length=10)
    app_order_id = models.CharField(_('App_order_id'), max_length=100, blank=True)
    state = models.CharField(_('State'), max_length=20)
    fee = models.PositiveIntegerField(_('Fee'))
    out_trade_no = models.CharField(_('Out trade no'), max_length=100)
    extra = models.TextField(_('Extra'))
    paied_at = models.PositiveIntegerField(_('Paid at'))

    class Meta:
        verbose_name = _('DangbeiPayRecord')
        verbose_name_plural = _('DangbeiPayRecords')

    def __unicode__(self):
        return self.user.name


class AtetOrder(models.Model):
    app_order_id = models.CharField(_('app_order_id'), max_length=100, blank=True)
    user = models.ForeignKey(User)
    channel = models.ForeignKey(Channel)
    pid = models.CharField(_('Pid'), max_length=10)
    amount = models.PositiveIntegerField(_('Amount'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0, blank=True)

    class Meta:
        verbose_name = _('AtetOrder')
        verbose_name_plural = _('AtetOrders')


class AtetPayRecord(models.Model):
    user = models.ForeignKey(User)
    pid = models.CharField(_('Pid'), max_length=10)
    app_order_id = models.CharField(_('App_order_id'), max_length=100, blank=True)
    amount = models.PositiveIntegerField(_('Amount'))
    counts = models.PositiveIntegerField(_('Counts'))
    paypoint = models.CharField(_('PayPoint'), max_length=32)
    exorderno = models.TextField(_('ExorderNo'))
    cpprivateinfo = models.CharField(_('cpPrivateInfo'), max_length=128)
    paytype = models.PositiveIntegerField(_('payType'))
    result = models.PositiveIntegerField(_('result'))
    paied_at = models.PositiveIntegerField(_('Paid at'))

    class Meta:
        verbose_name = _('AtetPayRecord')
        verbose_name_plural = _('AtetPayRecords')

    def __unicode__(self):
        return self.user.name


class SoulBox(models.Model):
    MON = 0
    TUE = 1
    WED = 2
    THU = 3
    FRI = 4
    SAT = 5
    SUN = 6
    WEEK = (
        (MON, _('Monday')),
        (TUE, _('Tuesday')),
        (WED, _('Wednesday')),
        (THU, _('thursday')),
        (FRI, _('Friday')),
        (SAT, _('Saturday')),
        (SUN, _('Sunday')),
    )
    PRIMARY = 0
    SECOND = 1
    TYPE = (
        (PRIMARY, _('Primary')),
        (SECOND, _('Second')),
    )
    week = models.PositiveIntegerField(_('Week'), choices=WEEK, default=MON)
    type = models.PositiveIntegerField(_('Type'), choices=TYPE, default=PRIMARY)
    prod = models.CharField(_('Prod'), max_length=10)
    num = models.PositiveIntegerField(_('Num'), default=0)
    proba = models.FloatField(_('Proba'), default=0.0)
    rock = models.PositiveIntegerField(_('Rock'), default=0)

    class Meta:
        verbose_name = _('SoulBox')
        verbose_name_plural = _('SoulBoxes')

    def __unicode__(self):
        return u'星期%s' % (int(self.week) + 1)


class SoulProba(models.Model):
    MON = 0
    TUE = 1
    WED = 2
    THU = 3
    FRI = 4
    SAT = 5
    SUN = 6
    WEEK = (
        (MON, _('Monday')),
        (TUE, _('Tuesday')),
        (WED, _('Wednesday')),
        (THU, _('thursday')),
        (FRI, _('Friday')),
        (SAT, _('Saturday')),
        (SUN, _('Sunday')),
    )
    week = models.PositiveIntegerField(_('Week'), choices=WEEK, default=MON)
    proba = models.TextField(_('Proba'), blank=False)
    rock = models.PositiveIntegerField(_('Rock'), default=400)
    gold = models.PositiveIntegerField(_('Gold'), default=100000)
    feat = models.PositiveIntegerField(_('Feat'), default=8000)
    prods = models.TextField(_('Prods'), blank=False)
    nums = models.TextField(_('Nums'), blank=False)

    class Meta:
        verbose_name = _('SoulProba')
        verbose_name_plural = _('SoulProbas')

    def __unicode__(self):
        return u'星期%s' % (int(self.week) + 1)


class Beauty(models.Model):
    name = models.CharField(_('Name'), max_length=20)
    beautyid = models.CharField(_('Beautyid'), max_length=10)
    level = models.PositiveIntegerField(_('Level'), default=1)
    gold = models.PositiveIntegerField(_('Gold'), default=0)
    rock = models.PositiveIntegerField(_('Rock'), default=0)
    prods = models.TextField(_('Prods'), blank=True)
    nums = models.TextField(_('Nums'), blank=True)

    class Meta:
        verbose_name = _('Beauty')
        verbose_name_plural = _('Beautys')
        unique_together = (('name', 'beautyid'),)

    def __unicode__(self):
        return self.name


class Seal(models.Model):
    JAN = 1
    FEB = 2
    MAR = 3
    APR = 4
    MAY = 5
    JUNE = 6
    JULY = 7
    AUG = 8
    SEPT = 9
    OCT = 10
    NOV = 11
    DEC = 12
    MONTH = (
        (JAN, _('January')),
        (FEB, _('February')),
        (MAR, _('March')),
        (APR, _('April')),
        (MAY, _('May')),
        (JUNE, _('June')),
        (JULY, _('July')),
        (AUG, _('August')),
        (SEPT, _('September')),
        (OCT, _('October')),
        (NOV, _('November')),
        (DEC, _('December')),
    )
    month = models.PositiveIntegerField(_('Month'), choices=MONTH, default=DEC)
    day = models.PositiveIntegerField(_('Day'), default=0)
    gold = models.PositiveIntegerField(_('Gold'), default=0)
    rock = models.PositiveIntegerField(_('Rock'), default=0)
    feat = models.PositiveIntegerField(_('Feat'), default=0)
    prods = models.TextField(_('Prods'), blank=True, null=True)
    nums = models.TextField(_('Nums'), blank=True, null=True)
    vip = models.PositiveIntegerField(_('Double condition'), default=0)

    class Meta:
        verbose_name = _('Seal')
        verbose_name_plural = _('Seals')

    def __unicode__(self):
        return '%s' % self.day


class FourteenSeal(models.Model):
    day = models.PositiveIntegerField(_('Day'), default=0)
    gold = models.PositiveIntegerField(_('Gold'), default=0)
    rock = models.PositiveIntegerField(_('Rock'), default=0)
    feat = models.PositiveIntegerField(_('Feat'), default=0)
    prods = models.TextField(_('Prods'), blank=True, null=True)
    nums = models.TextField(_('Nums'), blank=True, null=True)
    vip = models.PositiveIntegerField(_('Double condition'), default=0)

    class Meta:
        verbose_name = _('FourteenSeal')
        verbose_name_plural = _('FourteenSeal')

    def __unicode__(self):
        return '%s' % self.day


class FourteenSealSecond(models.Model):
    user = models.ForeignKey(User)
    seals = models.TextField(_('JSON Seals'), blank=True)

    class Meta:
        verbose_name = _('FourteenSealSecond')
        verbose_name_plural = _('FourteenSealSecond')

    def __unicode__(self):
        return self.seals


class DoubleEvent(models.Model):
    name = models.CharField(_('Name'), max_length=20)
    created_at = models.DateTimeField(_('Created_at'), default=datetime.datetime.now)
    ended_at = models.DateTimeField(_('Ended_at'), default=datetime.datetime.now)
    channels = models.ManyToManyField('Channel', blank=True)

    class Meta:
        verbose_name = _('DoubleEvent')
        verbose_name_plural = _('DoubleEvents')

    def __unicode__(self):
        return self.name


class Activity(models.Model):
    RECHARGE = 1
    TYPE = (
        (RECHARGE, _('Recharge')),
    )

    aid = models.CharField(_('Aid'), max_length=10)
    name = models.CharField(_('Name'), max_length=20)
    gold = models.PositiveIntegerField(_('Gold'), default=0)
    rock = models.PositiveIntegerField(_('Rock'), default=0)
    feat = models.PositiveIntegerField(_('Feat'), default=0)
    hp = models.PositiveIntegerField(_('Hp'), default=0)
    prods = models.TextField(_('Prods'), blank=True)
    nums = models.TextField(_('Nums'), blank=True)
    total = models.PositiveIntegerField(_('Total'), default=0, blank=True)
    type = models.PositiveIntegerField(_('Type'), choices=TYPE, default=RECHARGE)
    created_at = models.DateTimeField(_('Created_at'), default=datetime.datetime.now)
    ended_at = models.DateTimeField(_('Ended_at'), default=datetime.datetime.now)
    channels = models.ManyToManyField('Channel', blank=True)

    class Meta:
        verbose_name = _('Activity')
        verbose_name_plural = _('Activities')

    def __unicode__(self):
        return self.name


class Code(models.Model):
    UNUSED = 0
    USED = 1
    TYPE = (
        (UNUSED, _('Unused')),
        (USED, _('Used')),
    )
    user = models.ForeignKey(User, blank=True, null=True)
    code = models.CharField(_('Code'), max_length=64, unique=True)
    classify = models.CharField(_('Classify'), max_length=64)
    type = models.PositiveSmallIntegerField(
        _('Type'), choices=TYPE, default=UNUSED)
    valided_at = models.PositiveIntegerField(_('valided_at'), default=0)
    created_at = models.PositiveIntegerField(_('Created_at'), default=0)
    gold = models.PositiveIntegerField(_('Gold'), default=0)
    rock = models.PositiveIntegerField(_('Rock'), default=0)
    feat = models.PositiveIntegerField(_('Feat'), default=0)
    hp = models.PositiveIntegerField(_('Hp'), default=0)
    prods = models.TextField(_('Prods'), blank=True)
    nums = models.TextField(_('Nums'), blank=True)

    class Meta:
        verbose_name = _('Code')
        verbose_name_plural = _('Code')
        unique_together = ("user", "classify")

    def __unicode__(self):
        return self.code


class Product(models.Model):
    FIRST = 0
    SECOND = 1
    ORDER = (
        (FIRST, _('First')),
        (SECOND, _('Second')),
    )
    CARD = 1
    UNLIMIT = 2
    LIMIT = 3
    TYPE = (
        (CARD, _('Card')),
        (UNLIMIT, _('Unlimit')),
        (LIMIT, _('Limit')),
    )
    UNRESTRICT = 0
    RESTRICT = 1
    TIMES = (
        (UNRESTRICT, _('Unrestrict')),
        (RESTRICT, _('Restrict')),
    )
    pid = models.CharField(_('Pid'), max_length=64)
    code = models.CharField(_('Code'), max_length=64)
    sequence = models.PositiveSmallIntegerField(
        _('Sequence'), choices=ORDER, default=FIRST)
    type = models.PositiveSmallIntegerField(
        _('Type'), choices=TYPE, default=LIMIT)
    value = models.PositiveIntegerField(_('Value'), default=0)
    extra = models.PositiveIntegerField(_('Extra'), default=0)
    times = models.PositiveSmallIntegerField(
        _('Times'), choices=TIMES, default=UNRESTRICT)
    price = models.PositiveIntegerField(_('Price'), default=0)
    created_at = models.PositiveIntegerField(_('Created_at'), default=0)
    channels = models.ManyToManyField('Channel', blank=True)

    class Meta:
        verbose_name = _('Product')
        verbose_name_plural = _('Products')

    def __unicode__(self):
        return u'%s' % self.pid


class ProdProba(models.Model):
    GOLD = 1
    ROCK = 2
    TYPE = (
        (GOLD, _('Gold')),
        (ROCK, _('Rock')),
    )
    lotttype = models.PositiveIntegerField(_('Lotttype'), choices=TYPE, default=GOLD)
    times = models.PositiveIntegerField(_('Times'), default=1)
    proba = models.TextField(_('Proba'), blank=False)

    class Meta:
        verbose_name = _('ProdProba')
        verbose_name_plural = _('ProdProbas')

    def __unicode__(self):
        return u'%s@%s' % (self.lotttype, self.times)


class ProdReward(models.Model):
    REWARD0 = 0
    REWARD1 = 1
    REWARD2 = 2
    REWARD3 = 3
    REWARD4 = 4
    REWARD5 = 5
    REWARD6 = 6
    REWARD7 = 7
    REWARD8 = 8
    REWARD9 = 9
    REWARD10 = 10
    REWARD11 = 11
    REWARD12 = 12
    REWARD13 = 13
    REWARD14 = 14
    REWARD15 = 15
    REWARD16 = 16
    REWARD17 = 17
    TYPE = (
        (REWARD0, _('Reward0')),
        (REWARD1, _('Reward1')),
        (REWARD2, _('Reward2')),
        (REWARD3, _('Reward3')),
        (REWARD4, _('Reward4')),
        (REWARD5, _('Reward5')),
        (REWARD6, _('Reward6')),
        (REWARD7, _('Reward7')),
        (REWARD8, _('Reward8')),
        (REWARD9, _('Reward9')),
        (REWARD10, _('Reward10')),
        (REWARD11, _('Reward11')),
        (REWARD12, _('Reward12')),
        (REWARD13, _('Reward13')),
        (REWARD14, _('Reward14')),
        (REWARD15, _('Reward15')),
        (REWARD16, _('Reward16')),
        (REWARD17, _('Reward17')),

    )
    lotttype = models.PositiveIntegerField(_('Lotttype'), choices=TYPE, default=REWARD0)
    times = models.PositiveIntegerField(_('Times'), default=1)
    prod = models.TextField(_('Prod'), blank=True)
    maxnum = models.PositiveIntegerField(_('Maxnum'), default=0)
    minnum = models.PositiveIntegerField(_('Minnum'), default=0)

    class Meta:
        verbose_name = _('ProdReward')
        verbose_name_plural = _('ProdRewards')

    def __unicode__(self):
        return u'%s@%s' % (self.lotttype, self.times)


class Match(models.Model):
    mid = models.CharField(_('Mid'), max_length=64)
    prod = models.TextField(_('Prod'), blank=True)
    maxnum = models.PositiveIntegerField(_('Maxnum'), default=0)
    minnum = models.PositiveIntegerField(_('Minnum'), default=0)

    class Meta:
        verbose_name = _('Match')
        verbose_name_plural = _('Matches')

    def __unicode__(self):
        return self.mid


class Expedition(models.Model):
    eid = models.CharField(_('Eid'), max_length=64)
    prod = models.TextField(_('Prod'), blank=True)
    gold = models.PositiveIntegerField(_('Gold'), default=0)
    rock = models.PositiveIntegerField(_('Rock'), default=0)
    feat = models.PositiveIntegerField(_('Feat'), default=0)
    exped_coin = models.PositiveIntegerField(_('Expedition coin'), default=0)
    maxnum = models.PositiveIntegerField(_('Maxnum'), default=0)
    minnum = models.PositiveIntegerField(_('Minnum'), default=0)

    class Meta:
        verbose_name = _('Expedition')
        verbose_name_plural = _('Expeditions')

    def __unicode__(self):
        return self.eid


class UserExped(models.Model):
    user = models.ForeignKey(User)
    exped_coin = models.PositiveIntegerField(_('Expedition coin'), default=0)

    class Meta:
        verbose_name = _('UserExped')
        verbose_name_plural = _('UserExpeds')

    def __unicode__(self):
        return self.user.nickname


class BigEvent(models.Model):
    bid = models.CharField(_('Bid'), max_length=64)
    name = models.CharField(_('Name'), max_length=64)
    index = models.CharField(_('Index'), max_length=10)
    type = models.CharField(_('Type'), max_length=12, blank=True)
    channels = models.ManyToManyField('Channel', blank=True)
    created_at = models.DateTimeField(_('Created_at'), default=datetime.datetime.now)
    ended_at = models.DateTimeField(_('Ended_at'), default=datetime.datetime.now)

    class Meta:
        verbose_name = _('BigEvent')
        verbose_name_plural = _('BigEvents')

    def __unicode__(self):
        return self.bid


class Recharge(models.Model):
    RECHARGE = 1
    TYPE = (
        (RECHARGE, _('Recharge')),
    )
    bigevent = models.ForeignKey(BigEvent, blank=True, null=True)
    rid = models.CharField(_('Rid'), max_length=10)
    name = models.CharField(_('Name'), max_length=20)
    gold = models.PositiveIntegerField(_('Gold'), default=0)
    rock = models.PositiveIntegerField(_('Rock'), default=0)
    feat = models.PositiveIntegerField(_('Feat'), default=0)
    hp = models.PositiveIntegerField(_('Hp'), default=0)
    prods = models.TextField(_('Prods'), blank=True)
    nums = models.TextField(_('Nums'), blank=True)
    total = models.PositiveIntegerField(_('Total'), default=0, blank=True)
    type = models.PositiveIntegerField(_('Type'), choices=TYPE, default=RECHARGE)
    channels = models.ManyToManyField('Channel', blank=True)

    class Meta:
        verbose_name = _('Recharge')
        verbose_name_plural = _('Recharges')

    def __unicode__(self):
        return self.name


class Inpour(models.Model):
    INPOUR = 1
    TYPE = (
        (INPOUR, _('Inpour')),
    )
    bigevent = models.ForeignKey(BigEvent, blank=True, null=True)
    rid = models.CharField(_('Rid'), max_length=10)
    name = models.CharField(_('Name'), max_length=20)
    gold = models.PositiveIntegerField(_('Gold'), default=0)
    rock = models.PositiveIntegerField(_('Rock'), default=0)
    feat = models.PositiveIntegerField(_('Feat'), default=0)
    hp = models.PositiveIntegerField(_('Hp'), default=0)
    prods = models.TextField(_('Prods'), blank=True)
    nums = models.TextField(_('Nums'), blank=True)
    total = models.PositiveIntegerField(_('Total'), default=0, blank=True)
    type = models.PositiveIntegerField(_('Type'), choices=TYPE, default=INPOUR)

    class Meta:
        verbose_name = _('Inpour')
        verbose_name_plural = _('Inpours')

    def __unicode__(self):
        return self.name


class UserInpour(models.Model):
    user = models.ForeignKey(User)
    bid = models.CharField(_('Bid'), max_length=10)
    rock = models.PositiveIntegerField(_('Rock'), default=0)

    class Meta:
        verbose_name = _('UserInpour')
        verbose_name_plural = _('UserInpours')


class UserInpourRecord(models.Model):
    user = models.ForeignKey(User)
    bid = models.CharField(_('Bid'), max_length=10)
    rid = models.CharField(_('Rid'), max_length=10)

    class Meta:
        verbose_name = _('UserInpourRecord')
        verbose_name_plural = _('UserInpourRecords')

    def __unicode__(self):
        return self.user.nickname


class Consume(models.Model):
    CONSUME = 1
    TYPE = (
        (CONSUME, _('Consume')),
    )
    bigevent = models.ForeignKey(BigEvent, blank=True, null=True)
    rid = models.CharField(_('Rid'), max_length=10)
    name = models.CharField(_('Name'), max_length=20)
    gold = models.PositiveIntegerField(_('Gold'), default=0)
    rock = models.PositiveIntegerField(_('Rock'), default=0)
    feat = models.PositiveIntegerField(_('Feat'), default=0)
    hp = models.PositiveIntegerField(_('Hp'), default=0)
    prods = models.TextField(_('Prods'), blank=True)
    nums = models.TextField(_('Nums'), blank=True)
    total = models.PositiveIntegerField(_('Total'), default=0, blank=True)
    type = models.PositiveIntegerField(_('Type'), choices=TYPE, default=CONSUME)
    created_at = models.DateTimeField(_('Created_at'), default=datetime.datetime.now)
    ended_at = models.DateTimeField(_('Ended_at'), default=datetime.datetime.now)

    class Meta:
        verbose_name = _('Consume')
        verbose_name_plural = _('Consumes')

    def __unicode__(self):
        return self.name


class UserConsume(models.Model):
    user = models.ForeignKey(User)
    bid = models.CharField(_('Bid'), max_length=10)
    rock = models.PositiveIntegerField(_('Rock'), default=0)

    class Meta:
        verbose_name = _('UserConsume')
        verbose_name_plural = _('UserConsumes')

    def __unicode__(self):
        return self.user.nickname


class UserConsumeRecord(models.Model):
    user = models.ForeignKey(User)
    bid = models.CharField(_('Bid'), max_length=10)
    rid = models.CharField(_('Rid'), max_length=10)

    class Meta:
        verbose_name = _('UserConsumeRecord')
        verbose_name_plural = _('UserConsumeRecords')

    def __unicode__(self):
        return self.user.nickname


class DayRecharge(models.Model):
    DAYRECHARGE = 2
    TYPE = (
        (DAYRECHARGE, _('DayRecharge')),
    )
    bigevent = models.ForeignKey(BigEvent, blank=True, null=True)
    rid = models.CharField(_('Rid'), max_length=10)
    name = models.CharField(_('Name'), max_length=20)
    gold = models.PositiveIntegerField(_('Gold'), default=0)
    rock = models.PositiveIntegerField(_('Rock'), default=0)
    feat = models.PositiveIntegerField(_('Feat'), default=0)
    hp = models.PositiveIntegerField(_('Hp'), default=0)
    prods = models.TextField(_('Prods'), blank=True)
    nums = models.TextField(_('Nums'), blank=True)
    total = models.PositiveIntegerField(_('Total'), default=0, blank=True)
    type = models.PositiveIntegerField(_('Type'), choices=TYPE, default=DAYRECHARGE)
    channels = models.ManyToManyField('Channel', blank=True)
    created_at = models.DateTimeField(_('Created_at'), default=datetime.datetime.now)
    ended_at = models.DateTimeField(_('Ended_at'), default=datetime.datetime.now)

    class Meta:
        verbose_name = _('DayRecharge')
        verbose_name_plural = _('DayRecharges')

    def __unicode__(self):
        return self.name


class Gift(models.Model):
    bigevent = models.ForeignKey(BigEvent, blank=True, null=True)
    name = models.CharField(_('Name'), max_length=20)
    prod = models.CharField(_('Prod'), max_length=10)
    num = models.PositiveIntegerField(_('Num'), default=1)
    total = models.PositiveIntegerField(_('Total'), default=0)
    channels = models.ManyToManyField('Channel', blank=True)
    created_at = models.DateTimeField(_('Created_at'), default=datetime.datetime.now)
    ended_at = models.DateTimeField(_('Ended_at'), default=datetime.datetime.now)

    class Meta:
        verbose_name = _('Gift')
        verbose_name_plural = _('Gifts')

    def __unicode__(self):
        return self.name


class Zhangfei(models.Model):
    bigevent = models.ForeignKey(BigEvent, blank=True, null=True)
    name = models.CharField(_('Name'), max_length=20)
    rid = models.CharField(_('Rid'), max_length=10)
    prod = models.CharField(_('Prod'), max_length=10)
    num = models.PositiveIntegerField(_('Num'), default=1)
    total = models.PositiveIntegerField(_('Total'), default=0)

    class Meta:
        verbose_name = _('Zhangfei')
        verbose_name_plural = _('Zhangfei')

    def __unicode__(self):
        return self.name


class UserZhangfeiRecord(models.Model):
    user = models.ForeignKey(User)
    bid = models.CharField(_('Bid'), max_length=10)

    class Meta:
        verbose_name = _('UserZhangfeiRecord')
        verbose_name_plural = _('UserZhangfeiRecords')

    def __unicode__(self):
        return self.user.nickname


class SeckillTime(models.Model):
    name = models.CharField(_('Name'), max_length=20)
    switch = models.BooleanField(default=False)
    created_at = models.DateTimeField(_('Created_at'), default=datetime.datetime.now)
    ended_at = models.DateTimeField(_('Ended_at'), default=datetime.datetime.now)

    class Meta:
        verbose_name = _('SeckillTime')
        verbose_name_plural = _('SeckillTimes')

    def __unicode__(self):
        return u'%s' % self.name


class Seckill(models.Model):
    FIRSTGROUP = 1
    SECONDGROUP = 2
    THIRDGROUP = 3
    GROUPS = (
        (FIRSTGROUP, _('FirstGroup')),
        (SECONDGROUP, _('SecondGroup')),
        (THIRDGROUP, _('ThirdGroup')),
    )
    index = models.CharField(_('Index'), max_length=10)
    groups = models.PositiveIntegerField(_('Groups'), choices=GROUPS, default=FIRSTGROUP)
    prod = models.CharField(_('Prod'), max_length=10)
    num = models.PositiveIntegerField(_('Num'), default=1)
    gold = models.PositiveIntegerField(_('Gold'), default=0)
    rock = models.PositiveIntegerField(_('Rock'), default=0)
    total = models.PositiveIntegerField(_('Total'), default=0, blank=True)
    created_at = models.DateTimeField(_('Created_at'), default=datetime.datetime.now)
    ended_at = models.DateTimeField(_('Ended_at'), default=datetime.datetime.now)

    class Meta:
        verbose_name = _('Seckill')
        verbose_name_plural = _('Seckills')

    def __unicode__(self):
        return u'%s:%s' % (self.index, self.groups)


class VipPackage(models.Model):
    prods = models.TextField(_('Prods'), blank=True)
    nums = models.TextField(_('Nums'), blank=True)
    gold = models.PositiveIntegerField(_('Gold'), default=0)
    rock = models.PositiveIntegerField(_('Rock'), default=0)
    feat = models.PositiveIntegerField(_('Feat'), default=0)
    hp = models.PositiveIntegerField(_('Hp'), default=0)
    level = models.PositiveIntegerField(_('Vip Level'), default=0)

    class Meta:
        verbose_name = _('VipPackage')
        verbose_name_plural = _('VipPackages')

    def __unicode__(self):
        return self.level


class UserPackage(models.Model):
    user = models.ForeignKey(User)
    package = models.ForeignKey(VipPackage)

    class Meta:
        verbose_name = _('UserPackage')
        verbose_name_plural = _('UserPackages')

    def __unicode__(self):
        return self.user.name


class PropExchange(models.Model):
    bigevent = models.ForeignKey(BigEvent, blank=True, null=True)
    rid = models.CharField(_('Rid'), max_length=10)
    name = models.CharField(_('Name'), max_length=20)
    gold = models.PositiveIntegerField(_('Gold'), default=0)
    rock = models.PositiveIntegerField(_('Rock'), default=0)
    feat = models.PositiveIntegerField(_('Feat'), default=0)
    hp = models.PositiveIntegerField(_('Hp'), default=0)
    prods = models.TextField(_('Prods'), blank=True)
    nums = models.TextField(_('Nums'), blank=True)
    exgold = models.PositiveIntegerField(_('Exgold'), default=0)
    exrock = models.PositiveIntegerField(_('Exrock'), default=0)
    exfeat = models.PositiveIntegerField(_('Exfeat'), default=0)
    exhp = models.PositiveIntegerField(_('Exhp'), default=0)
    exprods = models.TextField(_('Exprods'), blank=True)
    exnums = models.TextField(_('Exnums'), blank=True)
    times = models.PositiveIntegerField(_('Times'), default=0)

    class Meta:
        verbose_name = _('PropExchange')
        verbose_name_plural = _('PropExchanges')

    def __unicode__(self):
        return self.name


class UserPropExchange(models.Model):
    user = models.ForeignKey(User)
    rid = models.CharField(_('Rid'), max_length=10)
    times = models.PositiveIntegerField(_('Times'), default=0)

    class Meta:
        verbose_name = _('UserPropExchange')
        verbose_name_plural = _('UserPropExchanges')

    def __unicode__(self):
        return self.user.nickname


class Chest(models.Model):
    OTHER = 0
    GOLD = 1
    TYPE = (
        (OTHER, _('Other')),
        (GOLD, _('Gold')),
    )
    name = models.CharField(_('Name'), max_length=20)
    type = models.PositiveIntegerField(_('Type'), choices=TYPE, default=OTHER)
    key_id = models.CharField(_('Key id'), max_length=10, blank=True)
    key_num = models.PositiveIntegerField(_('Key num'), default=0)
    chest_id = models.CharField(_('Chest id'), max_length=10)
    prods = models.TextField(_('Prods'), blank=True)
    nums = models.TextField(_('Nums'), blank=True)

    class Meta:
        verbose_name = _('Chest')
        verbose_name_plural = _('Chests')

    def __unicode__(self):
        return self.name


class UserState(models.Model):
    OTHER = -1
    LIANG = 1
    YI = 2
    JING = 3
    QING = 4
    STATE = (
        (LIANG, _('Liang')),
        (YI, _('Yi')),
        (JING, _('Jing')),
        (QING, _('Qing')),
        (OTHER, _('Other')),
    )

    user = models.ForeignKey(User, unique=True)
    state = models.IntegerField(_('State'), choices=STATE, default=OTHER)
    versus_coin = models.PositiveIntegerField(_('Versus coin'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0)

    class Meta:
        verbose_name = _('UserState')
        verbose_name_plural = _('UserStates')

    def __unicode__(self):
        return self.user.nickname + '@' + str(self.state)


class LiangState(models.Model):
    user = models.ForeignKey(User, unique=True)
    before_rank = models.PositiveIntegerField(_('Before_rank'), default=0)
    last_rank = models.PositiveIntegerField(_('Last_rank'), default=0)
    now_rank = models.PositiveIntegerField(_('Now_rank'), default=0, db_index=True)
    jguards1 = models.TextField(_('JSON guards1'), blank=True)
    jpositions1 = models.TextField(_('JSON positions1'), blank=True)
    formation1 = models.PositiveIntegerField(_('Formation1'), default=0)
    jguards2 = models.TextField(_('JSON guards2'), blank=True)
    jpositions2 = models.TextField(_('JSON positions2'), blank=True)
    formation2 = models.PositiveIntegerField(_('Formation2'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0)

    class Meta:
        verbose_name = _('LiangState')
        verbose_name_plural = _('LiangStates')

    def __unicode__(self):
        return self.user.name


class LiangStateResult(models.Model):
    WIN = 1
    LOSE = 0
    RESULTS = (
        (WIN, _('Win')),
        (LOSE, _('Lose')),
    )
    user = models.ForeignKey(User, related_name='liangstate_users')
    competitor = models.ForeignKey(User, related_name='liangstate_competitors')
    result = models.PositiveSmallIntegerField(
        _('Result'), choices=RESULTS, default=WIN)
    ascend = models.IntegerField(_('Ascend'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0)

    class Meta:
        verbose_name = _('LiangStateResult')
        verbose_name_plural = _('LiangStateResults')

    def __unicode__(self):
        return self.user.name + ' : ' + self.competitor.name


class YiState(models.Model):
    user = models.ForeignKey(User, unique=True)
    before_rank = models.PositiveIntegerField(_('Before_rank'), default=0)
    last_rank = models.PositiveIntegerField(_('Last_rank'), default=0)
    now_rank = models.PositiveIntegerField(_('Now_rank'), default=0, db_index=True)
    jguards1 = models.TextField(_('JSON guards1'), blank=True)
    jpositions1 = models.TextField(_('JSON positions1'), blank=True)
    formation1 = models.PositiveIntegerField(_('Formation1'), default=0)
    jguards2 = models.TextField(_('JSON guards2'), blank=True)
    jpositions2 = models.TextField(_('JSON positions2'), blank=True)
    formation2 = models.PositiveIntegerField(_('Formation2'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0)

    class Meta:
        verbose_name = _('YiState')
        verbose_name_plural = _('YiStates')

    def __unicode__(self):
        return self.user.name


class YiStateResult(models.Model):
    WIN = 1
    LOSE = 0
    RESULTS = (
        (WIN, _('Win')),
        (LOSE, _('Lose')),
    )
    user = models.ForeignKey(User, related_name='yistate_users')
    competitor = models.ForeignKey(User, related_name='yistate_competitors')
    result = models.PositiveSmallIntegerField(
        _('Result'), choices=RESULTS, default=WIN)
    ascend = models.IntegerField(_('Ascend'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0)

    class Meta:
        verbose_name = _('YiStateResult')
        verbose_name_plural = _('YiStateResults')

    def __unicode__(self):
        return self.user.name + ' : ' + self.competitor.name


class JingState(models.Model):
    user = models.ForeignKey(User, unique=True)
    before_rank = models.PositiveIntegerField(_('Before_rank'), default=0)
    last_rank = models.PositiveIntegerField(_('Last_rank'), default=0)
    now_rank = models.PositiveIntegerField(_('Now_rank'), default=0, db_index=True)
    jguards1 = models.TextField(_('JSON guards1'), blank=True)
    jpositions1 = models.TextField(_('JSON positions1'), blank=True)
    formation1 = models.PositiveIntegerField(_('Formation1'), default=0)
    jguards2 = models.TextField(_('JSON guards2'), blank=True)
    jpositions2 = models.TextField(_('JSON positions2'), blank=True)
    formation2 = models.PositiveIntegerField(_('Formation2'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0)

    class Meta:
        verbose_name = _('JingState')
        verbose_name_plural = _('JingStates')

    def __unicode__(self):
        return self.user.name


class JingStateResult(models.Model):
    WIN = 1
    LOSE = 0
    RESULTS = (
        (WIN, _('Win')),
        (LOSE, _('Lose')),
    )
    user = models.ForeignKey(User, related_name='jingstate_users')
    competitor = models.ForeignKey(User, related_name='jingstate_competitors')
    result = models.PositiveSmallIntegerField(
        _('Result'), choices=RESULTS, default=WIN)
    ascend = models.IntegerField(_('Ascend'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0)

    class Meta:
        verbose_name = _('JingStateResult')
        verbose_name_plural = _('JingStateResults')

    def __unicode__(self):
        return self.user.name + ' : ' + self.competitor.name


class QingState(models.Model):
    user = models.ForeignKey(User, unique=True)
    before_rank = models.PositiveIntegerField(_('Before_rank'), default=0)
    last_rank = models.PositiveIntegerField(_('Last_rank'), default=0)
    now_rank = models.PositiveIntegerField(_('Now_rank'), default=0)
    jguards1 = models.TextField(_('JSON guards1'), blank=True)
    jpositions1 = models.TextField(_('JSON positions1'), blank=True)
    formation1 = models.PositiveIntegerField(_('Formation1'), default=0)
    jguards2 = models.TextField(_('JSON guards2'), blank=True)
    jpositions2 = models.TextField(_('JSON positions2'), blank=True)
    formation2 = models.PositiveIntegerField(_('Formation2'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0)

    class Meta:
        verbose_name = _('QingState')
        verbose_name_plural = _('QingStates')

    def __unicode__(self):
        return self.user.name


class QingStateResult(models.Model):
    WIN = 1
    LOSE = 0
    RESULTS = (
        (WIN, _('Win')),
        (LOSE, _('Lose')),
    )
    user = models.ForeignKey(User, related_name='qingstate_users')
    competitor = models.ForeignKey(User, related_name='qingstate_competitors')
    result = models.PositiveSmallIntegerField(
        _('Result'), choices=RESULTS, default=WIN)
    ascend = models.IntegerField(_('Ascend'), default=0)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0)

    class Meta:
        verbose_name = _('QingStateResult')
        verbose_name_plural = _('QingStateResults')

    def __unicode__(self):
        return self.user.name + ' : ' + self.competitor.name


class GmLog(models.Model):
    user = models.ForeignKey(AdminUser)
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(default=datetime.datetime.now)

    class Meta:
        verbose_name = _('GmLog')
        verbose_name_plural = _('GmLogs')

    def __unicode__(self):
        return self.user


class Gate(models.Model):
    gate_id = models.CharField(_('Gate Id'), max_length=100, blank=True)
    jgates = models.TextField(_('JSON Gates'), blank=True)
    timestamp = models.PositiveIntegerField(_('Timestamp'), default=0, blank=True)

    class Meta:
        verbose_name = _('Gate')
        verbose_name_plural = _('Gate')

    def __unicode__(self):
        return self.gate_id
