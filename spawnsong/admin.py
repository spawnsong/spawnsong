from django.contrib import admin
from models import *
from sorl.thumbnail.admin import AdminImageMixin
from django.contrib import auth
from django.contrib.auth import admin as auth_admin
from django.db.models import Sum
from decimal import Decimal
from django.contrib.admin.filters import SimpleListFilter

site = admin.AdminSite()

class NullFilterSpec(SimpleListFilter):
    title = u''

    parameter_name = u''

    value_label = "Has value"

    no_value_label = "None"

    def lookups(self, request, model_admin):
        return (
            ('1', self.value_label),
            ('0', self.no_value_label)
        )

    def queryset(self, request, queryset):
        kwargs = {
        '%s'%self.parameter_name : None,
        }
        if self.value() == '0':
            return queryset.filter(**kwargs)
        if self.value() == '1':
            return queryset.exclude(**kwargs)
        return queryset

class SnippetInline(admin.StackedInline):
    model = Snippet
    extra = 0
    readonly_fields = ("state",'processing_error')
    fieldsets = (
       (None, {
           'fields': ('title', 'state', 'created_at', 'image', 'visualisation_effect','processing_error'),
       }),
       ('Audio Data', {
           'classes': ('collapse',),
           'fields': ('uploaded_audio','audio_mp3')
       }),
       ('Echonest', {
           'classes': ('collapse',),
           'fields': ('echonest_track_profile', 'echonest_track_analysis')
       }),
    )
    
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
        

class CompletedNullFilterSpec(NullFilterSpec):
    title = u'Completed'
    parameter_name = u'completed_at'
    value_label = "Completed"
    no_value_label = "Not Completed"
    
def retry_processing(modeladmin, request, queryset):
    for snippet in Snippet.objects.filter(state="processing_error", song__in=queryset.all()):
        snippet.process_uploaded_audio()
retry_processing.short_description = "Retry (failed) processing"

class SongAdmin(admin.ModelAdmin):
    inlines = [SnippetInline]
    list_display = ("title", "state", "artist", "completed")
    date_hierarchy = "created_at"
    search_fields = ("snippet__title", "snippet__state", "artist__user__username")
    list_filter = ("snippet__state", CompletedNullFilterSpec)
    actions = [retry_processing]

    
    fieldsets = (
       (None, {
           'fields': ('artist', 'created_at')
       }),
       ('Completed Song', {
           'fields': ('completed_at', 'complete_audio')
       }),
    )

    def completed(self, obj):
        return obj.is_complete()
    completed.boolean = True
    
    def has_add_permission(self, request):
        return False

    def state(self, obj):
        snippet = obj.snippet_set.first()
        if not snippet: return None
        return snippet.state

class CommentAdmin(admin.ModelAdmin):
    date_hierarchy = "created_at"
    search_fields = ("snippet__title", "user__username", "content", "ip_address")
    list_display = ("user", "snippet", "content", "created_at", "ip_address", "is_displayed")
    list_filter = ("is_displayed",)
    list_editable = ("is_displayed",)
    ordering = ("-created_at",)

def refund(modeladmin, request, queryset):
    for order in queryset.filter(refunded=False):
        order.refund()
refund.short_description = "Refund selected orders"
    
class OrderAdmin(admin.ModelAdmin):
    date_hierarchy = "created_at"
    readonly_fields = ("delivered", "refunded")
    search_fields = ("song__snippet__title", "purchaser_email", "price")
    list_display = ("song", "purchaser_email", "created_at", "price", "refunded", "delivered")
    list_filter = ("refunded", "delivered")
    ordering = ("-created_at",)
    actions = [refund]

    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    fieldsets = (
       (None, {
           'fields': ('song', 'price', 'created_at')
       }),
       ('Purchasher', {
           'fields': ('purchaser', 'purchaser_email')
       }),
       ('Order Status', {
           'fields': ('delivered', 'refunded')
       }),
       ('Transaction', {
           'classes': ('collapse',),
           'fields': ('stripe_transaction_id',)
       }),
    )

class OrderInline(admin.StackedInline):
    model = Order
    extra = 0
    
    readonly_fields = ("delivered", "refunded")
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    fieldsets = (
       (None, {
           'fields': ('song', 'price', 'created_at')
       }),
       ('Purchasher', {
           'fields': ('purchaser', 'purchaser_email')
       }),
       ('Order Status', {
           'fields': ('delivered', 'refunded')
       }),
       ('Transaction', {
           'classes': ('collapse',),
           'fields': ('stripe_transaction_id',)
       }),
    )

class ArtistPaymentAdmin(admin.ModelAdmin):
    date_hierarchy = "created_at"
    search_fields = ("artist__user__username", "artist__user__email")
    list_display = ("artist", "created_at", "order_count", "total_amount", "paid", "paid_at")
    list_filter = ("paid",)
    list_editable = ("paid",)
    readonly_fields = ("paid_at",)
    ordering = ("-created_at",)
    inlines = [OrderInline]
    
    def order_count(self, obj):
        return obj.order_set.count()
    
    def total_amount(self, obj):
        return "$%0.2f" % (obj.order_set.aggregate(Sum('price'))["price__sum"]/Decimal("100"))

    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
class UserAdmin(auth_admin.UserAdmin):
    pass
    
for _site in [site]:
    _site.register(Song, SongAdmin)
    _site.register(Order, OrderAdmin)
    _site.register(ArtistPayment, ArtistPaymentAdmin)
    _site.register(Comment, CommentAdmin)
    
site.register(auth.models.User, UserAdmin)
