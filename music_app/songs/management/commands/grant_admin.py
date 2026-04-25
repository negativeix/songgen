from django.core.management.base import BaseCommand, CommandError
from songs.models import User as SongsUser


class Command(BaseCommand):
    help = 'Grant app admin access to a user by email (sets is_admin=True on songs.User)'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email address of the user to promote')
        parser.add_argument(
            '--revoke',
            action='store_true',
            help='Remove admin access instead of granting it',
        )

    def handle(self, *args, **options):
        email = options['email']
        revoke = options['revoke']

        try:
            user = SongsUser.objects.get(email=email)
        except SongsUser.DoesNotExist:
            raise CommandError(f'No songs.User found with email: {email}')

        user.is_admin = not revoke
        user.save(update_fields=['is_admin'])

        action = 'Revoked admin from' if revoke else 'Granted admin to'
        self.stdout.write(self.style.SUCCESS(f'{action} {email} (is_admin={user.is_admin})'))
