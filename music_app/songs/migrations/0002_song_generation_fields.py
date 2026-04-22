import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('songs', '0001_initial'),
    ]

    operations = [
        # Make artist / duration / genre tolerant of blank / null values
        migrations.AlterField(
            model_name='song',
            name='artist',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AlterField(
            model_name='song',
            name='duration',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='song',
            name='genre',
            field=models.CharField(
                blank=True,
                choices=[
                    ('POP', 'Pop'), ('JAZZ', 'Jazz'), ('ROCK', 'Rock'),
                    ('HIPHOP', 'HipHop'), ('CLASSICAL', 'Classical'), ('ROMANCE', 'Romance'),
                ],
                default='',
                max_length=20,
            ),
        ),

        # Generation workflow
        migrations.AddField(
            model_name='song',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'Pending'), ('TEXT_SUCCESS', 'Text Success'),
                    ('FIRST_SUCCESS', 'First Success'), ('SUCCESS', 'Success'),
                    ('FAILED', 'Failed'),
                ],
                default='PENDING',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='song',
            name='task_id',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='song',
            name='audio_url',
            field=models.URLField(blank=True, max_length=500, null=True),
        ),

        # Generation inputs
        migrations.AddField(
            model_name='song',
            name='prompt',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='song',
            name='mood',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='song',
            name='vocal_style',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='song',
            name='lyrics',
            field=models.TextField(blank=True, null=True),
        ),

        # Visibility / sharing
        migrations.AddField(
            model_name='song',
            name='visibility',
            field=models.CharField(
                choices=[('PRIVATE', 'Private'), ('PUBLIC', 'Public')],
                default='PRIVATE',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='song',
            name='public_token',
            field=models.UUIDField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='song',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
