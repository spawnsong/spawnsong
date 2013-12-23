# Initial model outline, not tested yet

from django.db import models
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.conf import settings
import datetime
from jsonfield import JSONField
from django.db.models import Q
import uuid
import tasks

def upload_to(prefix="uploads"):
    def get_file_path(instance, filename):
        ext = filename.split('.')[-1]
        filename = "%s.%s" % (uuid.uuid4(), ext)
        return "%s/%s" % (prefix, filename)
    return get_file_path

class Artist(models.Model):
    user = models.OneToOneField(User)

    def get_absolute_url(self):
        return reverse("user", args=(self.user.username,))

    def get_display_name(self):
        return self.user.username

    def __unicode__(self):
        return unicode(self.user)
    
class Song(models.Model):
    """
    A song that a snippet comes from.

    In phase 1 each song has only one snippet, they're split out so we
    can add features later
    """
    artist = models.ForeignKey(Artist)
    
    created_at = models.DateTimeField(default=datetime.datetime.now)
    
    # TODO: Needs to be uploaded to a protected location. Maybe just
    # use a CharField with an S3 location in it?
    complete_audio = models.FileField(null=True, upload_to=upload_to("songs/complete"), blank=True)
    completed_at = models.DateTimeField(null=True, help_text="The time at which the completed audio file was uploaded", blank=True)

    def __unicode__(self):
        return u"Song id %d by %s" % (self.id, self.artist)

class SnippetManager(models.Manager):
    def visible_to(self, user):
        q = Q(state="published")
        if user and user.is_authenticated():
           q = q | Q(song__artist__user=user)
        return self.filter(q)
    
class Snippet(models.Model):
    """
    A snippet of a song on the site
    """
    song = models.ForeignKey(Song)
    title = models.CharField(max_length=255)
    state = models.CharField(max_length=20, choices=(("processing", "Processing"), ("ready", "Ready"), ("published", "Published")), default="processing")

    created_at = models.DateTimeField(default=datetime.datetime.now)

    image = models.ImageField(upload_to=upload_to("snippets/images"))
    uploaded_audio = models.FileField(upload_to=upload_to("snippets/audio/uploaded"), null=True, help_text="Original audio file as uploaded by user")
    
    audio_mp3 = models.FileField(upload_to=upload_to("snippets/audio/mp3"), null=True, help_text="Transcoded audio for streaming (mp3 format)")
    
    echonest_data = JSONField(blank=True, default=None, help_text="Data received from Echonest about the snippet, used to find the beat locations for the visualisation")

    visualisation_effect = models.CharField(max_length=20, choices=(("pulsate", "Pulsate"), ("none", "None")), default="pulsate")

    objects = SnippetManager()

    def is_complete(self):
        return self.song.completed_at is not None

    def order_count(self):
        return self.song.order_set.count()

    def audio_ready(self):
        return bool(self.audio_mp3)
    
    def mark_ready(self, commit=True):
       assert self.state == "processing" 
       assert self.audio_mp3, "Audio should be present before the snippet is marked as ready"
       assert self.echonest_data is not None, "Echonest data should be present before snippet is marked as ready"
       self.state = "ready"
       
       if commit:
           self.save()
           
    def publish(self, commit=True):
       assert self.state == "ready" 
       self.state = "published"
       if commit:
           self.save()

    def process_uploaded_audio(self):
        tasks.transcode_snippet_audio.delay(self.id)
        tasks.retireve_echonest_data.delay(self.id)

    @property
    def price(self):
        return settings.SONG_PRICE

    def __unicode__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("snippet", args=(self.id,))
    
class Order(models.Model):
    "A pre-order or order for a song"
    song = models.ForeignKey(Song)
    purchaser = models.ForeignKey(User)
    price = models.IntegerField(help_text="Purchase price in cents")
    refunded = models.BooleanField(default=False)
    delivered = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(default=datetime.datetime.now)

    stripe_transaction_id = models.CharField(max_length=255)

    def __unicode__(self):
        return "Order for %s by %s" % (self.song, self.purchaser)

class ArtistPayment(models.Model):
    "A payment that the system caluclated is owed to an artist"
    arist = models.ForeignKey(Artist)
    orders = models.ManyToManyField(Order)
    created_at = models.DateTimeField(default=datetime.datetime.now)
    paid = models.BooleanField(default=False)

    def __unicode__(self):
        return "Payment to %s" % (self.artist,)

class Comment(models.Model):
    """
    A comment on a snippet.
    """
    user = models.ForeignKey(User)
    snippet = models.ForeignKey(Snippet)
    created_at = models.DateTimeField(default=datetime.datetime.now)
    content = models.TextField()
    ip_address = models.GenericIPAddressField(('IP address'), unpack_ipv4=True, blank=True, null=True)

    is_displayed = models.BooleanField(default=True)

    class Meta:
        ordering = ("created_at",)
        
    def __unicode__(self):
        return u"%s: %s" % (self.user, self.content)
    