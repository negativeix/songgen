from django.db import migrations, models


def seed_default_config(apps, schema_editor):
    SiteConfig = apps.get_model('songs', 'SiteConfig')
    SiteConfig.objects.get_or_create(
        key='max_songs_per_day',
        defaults={'value': '10', 'description': 'Max songs a single user can generate per calendar day (UTC). Set to 0 for unlimited.'},
    )


class Migration(migrations.Migration):

    dependencies = [
        ('songs', '0003_user_is_admin'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteConfig',
            fields=[
                ('key', models.CharField(max_length=100, primary_key=True, serialize=False)),
                ('value', models.CharField(max_length=500)),
                ('description', models.CharField(blank=True, max_length=300)),
            ],
            options={
                'verbose_name': 'Site Config',
                'verbose_name_plural': 'Site Config',
            },
        ),
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('user_email', models.CharField(db_index=True, max_length=254)),
                ('action', models.CharField(max_length=60)),
                ('song_id', models.UUIDField(blank=True, null=True)),
                ('task_id', models.CharField(blank=True, max_length=200)),
                ('strategy', models.CharField(blank=True, max_length=50)),
                ('detail', models.CharField(blank=True, max_length=500)),
            ],
            options={
                'verbose_name': 'Audit Log',
                'verbose_name_plural': 'Audit Logs',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.RunPython(seed_default_config, migrations.RunPython.noop),
    ]
