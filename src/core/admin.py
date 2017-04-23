from django.contrib import admin
import simplejson as json
from django.utils.translation import ugettext_lazy as _
from models import *


class ChannelAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug')
    search_fields = ('title',)
    fields = ('title', 'slug')


class NoticeshipInline(admin.TabularInline):
    classes = ('grp-collapse grp-open',)
    model = Noticeship
    fields = ('notice', 'position')
    sortable_field_name = 'position'
    raw_id_fields = ('notice',)
    related_lookup_fields = {
        'fk': ('notice',)
    }
    extra = 0


class UserAdmin(admin.ModelAdmin):
    list_display = ('nickname', 'avat', 'xp', 'gold', 'rock')
    search_fields = ('nickname',)


class AccountAdmin(admin.ModelAdmin):
    list_display = ('accountid', 'user', 'state', 'created')
    search_fields = ('accountid', 'user',)


class ZoneAdmin(admin.ModelAdmin):
    inlines = (NoticeshipInline,)
    list_display = ('zoneid', 'name')
    search_fields = ('name',)


class PropAdmin(admin.ModelAdmin):
    list_display = ('user', 'label', 'num', 'txt')
    search_fields = ('user', 'label',)


class MailAdmin(admin.ModelAdmin):
    list_display = ('sender', 'to', 'title', 'type', 'created_at')
    search_fields = ('title',)


class CardAdmin(admin.ModelAdmin):
    list_display = ('user', 'gid', 'created_at', 'ended_at')
    search_fields = ('title',)
    fields = ('user', 'gid', 'created_at', 'ended_at')


class DayLottAdmin(admin.ModelAdmin):
    list_display = ('user', 'times')
    # search_fields = ('title', )


class NoticeAdmin(admin.ModelAdmin):
    list_display = ('title', 'content', 'created_at', 'ended_at', 'sign', 'url')
    search_fields = ('title',)
    fields = ('title', 'content', 'screenshot', 'created_at', 'ended_at', 'sign', 'url')


class SoulBoxAdmin(admin.ModelAdmin):
    list_display = ('week', 'type', 'prod', 'num', 'proba', 'rock')
    search_fields = ('week',)
    fields = ('week', 'type', 'prod', 'num', 'proba', 'rock')


class SoulProbaAdmin(admin.ModelAdmin):
    list_display = ('week', 'proba', 'rock')
    search_fields = ('week',)
    fields = ('week', 'proba', 'rock', 'gold', 'feat', 'prods', 'nums')


class BeautyAdmin(admin.ModelAdmin):
    list_display = ('name', 'beautyid', 'level', 'gold', 'rock')
    search_fields = ('name',)
    fields = ('name', 'beautyid', 'level', 'gold', 'rock', 'prods', 'nums')


class SealAdmin(admin.ModelAdmin):
    list_display = ('month', 'day', 'gold', 'rock', 'feat', 'prods', 'nums', 'vip')
    search_fields = ('day',)
    fields = ('month', 'day', 'gold', 'rock', 'feat', 'prods', 'nums', 'vip')


class FourteenSealAdmin(admin.ModelAdmin):
    list_display = ('day', 'gold', 'rock', 'feat', 'prods', 'nums', 'vip')
    search_fields = ('day',)
    fields = ('day', 'gold', 'rock', 'feat', 'prods', 'nums', 'vip')


class DoubleEventAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'ended_at')
    search_fields = ('name',)
    fields = ('name', 'created_at', 'ended_at', 'channels')
    filter_vertical = ('channels',)


class ActivityAdmin(admin.ModelAdmin):
    list_display = ('aid', 'name', 'gold', 'rock', 'feat', 'hp', 'prods', 'nums', 'total', 'created_at', 'ended_at')
    search_fields = ('name',)
    fields = (
    'aid', 'name', 'gold', 'rock', 'feat', 'hp', 'prods', 'nums', 'total', 'created_at', 'ended_at', 'channels')
    filter_vertical = ('channels',)


class CodeAdmin(admin.ModelAdmin):
    list_display = (
    'code', 'user', 'classify', 'type', 'valided_at', 'created_at', 'gold', 'rock', 'feat', 'hp', 'prods', 'nums')
    search_fields = ('code',)
    fields = (
    'code', 'user', 'classify', 'type', 'valided_at', 'created_at', 'gold', 'rock', 'feat', 'hp', 'prods', 'nums')


# filter_vertical = ('channels', )

class ProductAdmin(admin.ModelAdmin):
    list_display = ('pid', 'code', 'sequence', 'type', 'value', 'extra', 'times', 'price')
    search_fields = ('name',)
    fields = ('pid', 'code', 'sequence', 'type', 'value', 'extra', 'times', 'price', 'created_at', 'channels')
    filter_vertical = ('channels',)


class ProdProbaAdmin(admin.ModelAdmin):
    list_display = ('lotttype', 'times', 'proba')
    search_fields = ('lotttype',)
    fields = ('lotttype', 'times', 'proba')


class ProdRewardAdmin(admin.ModelAdmin):
    list_display = ('lotttype', 'times', 'prod', 'maxnum', 'minnum')
    search_fields = ('lotttype',)
    fields = ('lotttype', 'times', 'prod', 'maxnum', 'minnum')


class MatchAdmin(admin.ModelAdmin):
    list_display = ('mid', 'prod', 'maxnum', 'minnum')
    search_fields = ('mid',)
    fields = ('mid', 'prod', 'maxnum', 'minnum')


class ExpeditionAdmin(admin.ModelAdmin):
    list_display = ('eid', 'prod', 'maxnum', 'minnum', 'rock', 'feat', 'gold', 'exped_coin')
    search_fields = ('eid',)
    fields = ('eid', 'prod', 'maxnum', 'minnum', 'rock', 'feat', 'gold', 'exped_coin')


class BigEventAdmin(admin.ModelAdmin):
    list_display = ('bid', 'name', 'index', 'type', 'created_at', 'ended_at')
    search_fields = ('bid', 'name')
    fields = ('bid', 'name', 'index', 'type', 'channels', 'created_at', 'ended_at')
    filter_vertical = ('channels',)


class RechargeAdmin(admin.ModelAdmin):
    list_display = ('rid', 'bigevent', 'name', 'gold', 'rock', 'feat', 'hp', 'prods', 'nums', 'total', 'type')
    search_fields = ('name',)
    fields = ('rid', 'name', 'bigevent', 'gold', 'rock', 'feat', 'hp', 'prods', 'nums', 'total', 'type', 'channels')
    filter_vertical = ('channels',)


class DayRechargeAdmin(admin.ModelAdmin):
    list_display = (
    'rid', 'bigevent', 'name', 'gold', 'rock', 'feat', 'hp', 'prods', 'nums', 'total', 'type', 'created_at', 'ended_at')
    search_fields = ('name',)
    fields = (
    'rid', 'name', 'bigevent', 'gold', 'rock', 'feat', 'hp', 'prods', 'nums', 'total', 'type', 'channels', 'created_at',
    'ended_at')
    filter_vertical = ('channels',)


class ZhangfeiAdmin(admin.ModelAdmin):
    list_display = ('name', 'bigevent', 'rid', 'prod', 'num', 'total',)
    search_fields = ('name',)
    fields = ('name', 'bigevent', 'rid', 'prod', 'num', 'total')


class RechargeAdmin(admin.ModelAdmin):
    list_display = ('rid', 'bigevent', 'name', 'gold', 'rock', 'feat', 'hp', 'prods', 'nums', 'total', 'type')
    search_fields = ('name',)
    fields = ('rid', 'name', 'bigevent', 'gold', 'rock', 'feat', 'hp', 'prods', 'nums', 'total', 'type', 'channels')
    filter_vertical = ('channels',)


class InpourAdmin(admin.ModelAdmin):
    list_display = ('rid', 'name', 'gold', 'rock', 'feat', 'hp', 'prods', 'nums', 'total', 'type')
    search_fields = ('name', 'bigevent')
    fields = ('rid', 'name', 'bigevent', 'gold', 'rock', 'feat', 'hp', 'prods', 'nums', 'total', 'type')
    # filter_vertical = ('bigevent', )


class ConsumeAdmin(admin.ModelAdmin):
    list_display = (
    'rid', 'bigevent', 'name', 'gold', 'rock', 'feat', 'hp', 'prods', 'nums', 'total', 'type', 'created_at', 'ended_at')
    search_fields = ('name',)
    fields = (
    'rid', 'name', 'bigevent', 'gold', 'rock', 'feat', 'hp', 'prods', 'nums', 'total', 'type', 'created_at', 'ended_at')


class SeckillTimeAdmin(admin.ModelAdmin):
    list_display = ('name', 'switch', 'created_at', 'ended_at')
    search_fields = ('name',)
    fields = ('name', 'switch', 'created_at', 'ended_at')


class SeckillAdmin(admin.ModelAdmin):
    list_display = ('index', 'groups', 'prod', 'num', 'gold', 'rock', 'total')
    search_fields = ('index',)
    fields = ('index', 'groups', 'prod', 'num', 'gold', 'rock', 'total', 'created_at', 'ended_at')
    # filter_vertical = ('channels', )


class VipPackageAdmin(admin.ModelAdmin):
    list_display = ('prods', 'nums', 'gold', 'rock', 'feat', 'hp', 'level')
    search_fields = ('vid',)
    fields = ('prods', 'nums', 'gold', 'rock', 'feat', 'hp', 'level')


class PropExchangeAdmin(admin.ModelAdmin):
    list_display = (
    'bigevent', 'rid', 'name', 'gold', 'rock', 'feat', 'hp', 'prods', 'nums', 'exgold', 'exrock', 'exfeat', 'exhp',
    'exprods', 'exnums', 'times')
    search_fields = ('name',)
    fields = (
    'bigevent', 'rid', 'name', 'gold', 'rock', 'feat', 'hp', 'prods', 'nums', 'exgold', 'exrock', 'exfeat', 'exhp',
    'exprods', 'exnums', 'times')


class ChestAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'key_id', 'key_num', 'chest_id', 'prods', 'nums')
    search_fields = ('name',)
    fields = ('name', 'type', 'key_id', 'key_num', 'chest_id', 'prods', 'nums')


class GmLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'content', 'created_at')
    search_fields = ('user__username',)
    fields = ('user', 'content', 'created_at')
    list_filter = ('user', 'content', 'created_at')


admin.site.register(Channel, ChannelAdmin)
admin.site.register(User, UserAdmin)
admin.site.register(Account, AccountAdmin)
admin.site.register(Prop, PropAdmin)
admin.site.register(Mail, MailAdmin)
admin.site.register(Card, CardAdmin)
admin.site.register(DayLott, DayLottAdmin)
admin.site.register(Zone, ZoneAdmin)
admin.site.register(Notice, NoticeAdmin)
admin.site.register(SoulBox, SoulBoxAdmin)
admin.site.register(SoulProba, SoulProbaAdmin)
admin.site.register(Beauty, BeautyAdmin)
admin.site.register(Seal, SealAdmin)
admin.site.register(FourteenSeal, FourteenSealAdmin)
admin.site.register(DoubleEvent, DoubleEventAdmin)
admin.site.register(Activity, ActivityAdmin)
admin.site.register(Code, CodeAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(ProdProba, ProdProbaAdmin)
admin.site.register(ProdReward, ProdRewardAdmin)
admin.site.register(Match, MatchAdmin)
admin.site.register(BigEvent, BigEventAdmin)
# admin.site.register(Recharge, RechargeAdmin)
admin.site.register(Consume, ConsumeAdmin)
# admin.site.register(DayRecharge, DayRechargeAdmin)
admin.site.register(Seckill, SeckillAdmin)
admin.site.register(SeckillTime, SeckillTimeAdmin)
admin.site.register(Zhangfei, ZhangfeiAdmin)
admin.site.register(VipPackage, VipPackageAdmin)
admin.site.register(Expedition, ExpeditionAdmin)
admin.site.register(PropExchange, PropExchangeAdmin)
admin.site.register(Chest, ChestAdmin)
admin.site.register(Inpour, InpourAdmin)
admin.site.register(GmLog, GmLogAdmin)
