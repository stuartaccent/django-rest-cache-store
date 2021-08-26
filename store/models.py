from django.db import models


class StoreHistory(models.Model):
    version = models.FloatField()
    cache_key = models.SlugField(
        max_length=100,
        null=True,
        blank=True,
    )
    item_id = models.IntegerField(
        null=True,
        blank=True,
    )
    state = models.CharField(
        max_length=1,
        null=True,
        blank=True,
    )
    added_on = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ['added_on']
        verbose_name_plural = 'store history'
