from django.db import migrations, models
import django.db.models.deletion


def seed_organisation_masters(apps, schema_editor):
    InternalSection = apps.get_model('core', 'InternalSection')
    Unit = apps.get_model('core', 'Unit')

    sections = [
        ('PS-1', "PS-1", "Officers' discipline, boards, clearance and related matters."),
        ('PS-2', "PS-2", "JCO/Soldier discipline, Ex-Pakistan leave and related personnel matters; JCO/Soldier matrimonial affairs."),
        ('PS-3', "PS-3", "Parades, ceremonies, band, dress, uniform, investiture ceremonies, Mark-e-Haq and related matters; ASM affairs."),
        ('PS-4', "PS-4", "Hajj, Umra and related administrative/financial matters."),
        ('PS-5', "PS-5", "Officers' Ex-Pakistan leave, representation cases, discipline, Mujahid Officers and related matters."),
        ('PS-6', "PS-6", "Plans, policies, Army Officers Handbook and publications."),
        ('PS-COORD', "PS Coord", "HR management; management and coordination across Directorate sections; coordination of DG PS activities/programmes; private accounts; security; administration and related coordination."),
        ('HQ-PM', "HQ PM", "Headquarters Provost Marshal — MP and related matters."),
        ('MATRIMONIAL', "Matrimonial Sec", "Matrimonial Cell matters concerning officers and families; JCO/Soldier matrimonial matters remain with PS-2."),
        ('CMTF', "CMTF", "Cyber monitoring; OPs AG Br Cell, CMT expansion and 360 solution related matters."),
        ('DMC', "DMC", "IT matters including computers, hardware, application development and related digital/technical support."),
    ]
    for order, (code, name, description) in enumerate(sections, start=1):
        InternalSection.objects.update_or_create(
            code=code,
            defaults={'name': name, 'description': description, 'display_order': order, 'is_active': True},
        )

    units = [
        ('UNIT-45', 'Unit 45'),
        ('29-MP', '29 MP'),
        ('ASM', 'ASM'),
        ('SIB', 'SIB'),
        ('CMP', 'CMP'),
        ('CEN-SCHOOL', 'Cen & School'),
    ]
    for order, (code, name) in enumerate(units, start=1):
        Unit.objects.update_or_create(
            code=code,
            defaults={'name': name, 'display_order': order, 'is_active': True},
        )

    # Approved operational relationships.
    ps3 = InternalSection.objects.get(code='PS-3')
    hqpm = InternalSection.objects.get(code='HQ-PM')
    Unit.objects.get(code='ASM').managed_by_sections.add(ps3)
    Unit.objects.get(code='29-MP').managed_by_sections.add(hqpm)


def migrate_existing_unit_attribution(apps, schema_editor):
    Transaction = apps.get_model('core', 'Transaction')
    Unit = apps.get_model('core', 'Unit')
    for tx in Transaction.objects.exclude(unit__isnull=True).iterator():
        tx.transaction_units.add(tx.unit_id)


class Migration(migrations.Migration):
    dependencies = [('core', '0010_alter_transaction_document_reference_and_more')]

    operations = [
        migrations.CreateModel(
            name='InternalSection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(db_index=True, max_length=50, unique=True)),
                ('name', models.CharField(max_length=120, unique=True)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('display_order', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['display_order', 'name'], 'verbose_name': 'Internal Section', 'verbose_name_plural': 'Internal Sections'},
        ),
        migrations.AddField(
            model_name='unit', name='managed_by_sections',
            field=models.ManyToManyField(blank=True, help_text='Optional responsible Internal Sections; a Unit may have multiple managing Sections.', related_name='managed_units', to='core.internalsection'),
        ),
        migrations.AddField(
            model_name='transaction', name='internal_section',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='primary_transactions', to='core.internalsection'),
        ),
        migrations.AddField(
            model_name='transaction', name='transaction_sections',
            field=models.ManyToManyField(blank=True, related_name='attributed_transactions', to='core.internalsection'),
        ),
        migrations.AddField(
            model_name='transaction', name='transaction_units',
            field=models.ManyToManyField(blank=True, related_name='attributed_transactions', to='core.unit'),
        ),
        migrations.AddField(model_name='transaction', name='deleted_by', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='soft_deleted_transactions', to='auth.user')),
        migrations.AddField(model_name='transaction', name='deleted_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='transaction', name='deletion_reason', field=models.TextField(blank=True)),
        migrations.AlterField(
            model_name='transaction', name='status',
            field=models.CharField(choices=[('DRAFT', 'Draft'), ('ACTIVE', 'Active'), ('CANCELLED', 'Cancelled'), ('SOFT_DELETED', 'Soft Deleted')], db_index=True, default='DRAFT', max_length=20),
        ),
        migrations.RunPython(migrate_existing_unit_attribution, migrations.RunPython.noop),
        migrations.RunPython(seed_organisation_masters, migrations.RunPython.noop),
    ]
