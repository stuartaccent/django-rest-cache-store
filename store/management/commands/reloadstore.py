from django.core.management.base import BaseCommand

from store.bindings import BaseAppStore


class Command(BaseCommand):
    """ Django command that reloads all store cache """

    def handle(self, *args, **options):
        if BaseAppStore.NOCACHE:
            self.stdout.write(self.style.WARNING('Store not reloaded as BaseAppStore.NOCACHE is True!'))
            return

        for _, klass in BaseAppStore.INSTANCES.items():
            klass.cache_add_all(klass.get_initial_state())

        version = BaseAppStore.set_version()

        BaseAppStore.save_to_history(version=version, state='F')
        BaseAppStore.send_group_info()

        self.stdout.write(self.style.SUCCESS('Store reloaded!'))
