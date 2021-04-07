# Generated by Django 3.1.1 on 2021-01-05 14:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eveonline', '0013_evecorporationinfo_ceo_id'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='evecorporationinfo',
            index=models.Index(fields=['ceo_id'], name='eveonline_e_ceo_id_eea7b8_idx'),
        ),
    ]