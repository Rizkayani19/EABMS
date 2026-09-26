from django.db import migrations, models
import django.db.models.deletion


SECTIONS = [
    ('PS-1', 'PS-1', "Officers' discipline, boards, clearance and related matters.", 10),
    ('PS-2', 'PS-2', "JCO/Soldier discipline, Ex-Pakistan leave and related personnel matters; JCO/Soldier matrimonial affairs.", 20),
    ('PS-3', 'PS-3', 'Parades, ceremonies, band, dress, uniform, investiture ceremonies, Mark-e-Haq and related matters; ASM affairs.', 30),
    ('PS-4', 'PS-4', 'Hajj, Umra and related administrative and financial matters.', 40),
    ('PS-5', 'PS-5', "Officers' Ex-Pakistan leave, representation cases, discipline, Mujahid Officers and related matters.", 50),
    ('PS-6', 'PS-6', 'Plans, policies, Army Officers Hand Book and Army publications.', 60),
    ('PS-COORD', 'PS Coord', "Coordination branch under Deputy Director Coordination: HR management; coordination across all Directorate sections; coordination of DG PS activities and programmes; private accounts; security; administration and related coordination matters.", 70),
    ('HQ-PM', 'HQ PM', 'Headquarters Provost Marshal — MP and related matters.', 80),
    ('MATRIMONIAL', 'Matrimonial Sec', 'Matrimonial Cell matters concerning officers and families; JCO/Soldier matrimonial affairs remain with PS-2.', 90),
    ('CMTF', 'CMTF', 'Cyber monitoring, including Information Operations/OPS AG Branch Cell and CMT expansion / 360-solution related matters.', 100),
    ('DMC', 'DMC', 'IT matters including computers, hardware, application development and related digital/technical support.', 110),
]

UNITS = [
    ('UNIT-45', 'Unit 45'),
    ('29-MP', '29 MP'),
    ('ASM', 'ASM'),
    ('SIB', 'SIB'),
    ('CMP', 'CMP'),
    ('CEN-SCHOOL', 'Cen & School'),
]

RESPONSIBILITIES = [
    ('ASM', 'PS-3', True, 'ASM-related affairs are managed by PS-3.'),
    ('29-MP', 'HQ-PM', True, 'MP-unit related affairs are managed by Headquarters Provost Marshal.'),
]


def seed_organisational_masters(apps, schema_editor):
    InternalSection = apps.get_model('masters', 'InternalSection')
    Unit = apps.get_model('core', 'Unit')
    Responsibility = apps.get_model('masters', 'UnitSectionResponsibility')

    sections = {}
    for code, name, description, order in SECTIONS:
        obj, _ = InternalSection.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'description': description,
                'is_active': True,
                'display_order': order,
            },
        )
        sections[code] = obj

    units = {}
    for code, name in UNITS:
        obj, _ = Unit.objects.get_or_create(
            code=code,
            defaults={'name': name, 'is_active': True},
        )
        units[code] = obj

    for unit_code, section_code, primary, notes in RESPONSIBILITIES:
        Responsibility.objects.update_or_create(
            unit=units[unit_code],
            section=sections[section_code],
            defaults={'is_primary': primary, 'is_active': True, 'notes': notes},
        )


def unseed_organisational_masters(apps, schema_editor):
    # Preserve master data on rollback; operational installations may have edited it.
    pass


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('core', '0010_alter_transaction_document_reference_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='InternalSection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(db_index=True, max_length=50, unique=True)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('display_order', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Internal Section',
                'verbose_name_plural': 'Internal Sections',
                'ordering': ['display_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='UnitSectionResponsibility',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_primary', models.BooleanField(default=False, help_text='Marks the normal/primary responsible section where one exists.')),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='unit_responsibilities', to='masters.internalsection')),
                ('unit', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='section_responsibilities', to='core.unit')),
            ],
            options={
                'verbose_name': 'Unit / Section Responsibility',
                'verbose_name_plural': 'Unit / Section Responsibilities',
                'ordering': ['unit__display_order', 'section__display_order', 'unit__name', 'section__name'],
            },
        ),
        migrations.AddConstraint(
            model_name='unitsectionresponsibility',
            constraint=models.UniqueConstraint(fields=('unit', 'section'), name='unique_unit_section_responsibility'),
        ),
        migrations.RunPython(seed_organisational_masters, unseed_organisational_masters),
    ]
