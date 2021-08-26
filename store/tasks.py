from huey.contrib.djhuey import db_task

from store.bindings import BaseAppStore


@db_task()
def trigger_cache_rebuild(cache_key, pk=None):
    cache = BaseAppStore.get_instance(cache_key)
    cache.cache_rebuild(pk)
    cache.send_group_info()
