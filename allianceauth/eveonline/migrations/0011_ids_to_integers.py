# Generated by Django 2.2.12 on 2020-05-25 02:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eveonline', '0010_alliance_ticker'),
    ]

    operations = [
        migrations.AlterField(
            model_name='eveallianceinfo',
            name='alliance_id',
            field=models.PositiveIntegerField(unique=True),
        ),
        migrations.AlterField(
            model_name='eveallianceinfo',
            name='executor_corp_id',
            field=models.PositiveIntegerField(),
        ),
        migrations.AlterField(
            model_name='evecharacter',
            name='alliance_id',
            field=models.PositiveIntegerField(blank=True, default=None, null=True),
        ),
        migrations.AlterField(
            model_name='evecharacter',
            name='character_id',
            field=models.PositiveIntegerField(unique=True),
        ),
        migrations.AlterField(
            model_name='evecharacter',
            name='corporation_id',
            field=models.PositiveIntegerField(),
        ),
        migrations.AlterField(
            model_name='evecorporationinfo',
            name='corporation_id',
            field=models.PositiveIntegerField(unique=True),
        ),
    ]
